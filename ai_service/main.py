import json
import shutil
import tempfile
from collections import defaultdict
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, UploadFile

import cv2
import joblib
import numpy as np
import torch
from fastapi import FastAPI, HTTPException, UploadFile
from ultralytics import YOLO


# ===== 상수 =====
MODEL_DIR = Path(__file__).resolve().parent / "models"

IMAGE_SIZE = 640
PERSON_CONFIDENCE = 0.25
TRACKER = "bytetrack.yaml"

DANGER_CLASSES = ("shake", "drop", "look_away")


# ===== 모델 로딩 =====
def load_models():
    with (MODEL_DIR / "rf_training_info.json").open("r", encoding="utf-8") as file:
        training_info = json.load(file)

    return {
        "rf_model": joblib.load(MODEL_DIR / "rf_action_baseline.joblib"),
        "training_info": training_info,
        "pose_model": YOLO(str(MODEL_DIR / "yolo11n-pose.pt")),
    }


# ===== 앱·경로 =====
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 요청마다 모델 파일을 다시 읽지 않도록 서버 시작 때 한 번만 올려둔다
    app.state.models = load_models()
    yield


app = FastAPI(lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok"}


# ===== 로직부 =====
def track_video(video_path, pose_model):
    device = 0 if torch.cuda.is_available() else "cpu"
    capture = cv2.VideoCapture(str(video_path))
    fps = capture.get(cv2.CAP_PROP_FPS)
    frames = []
    frame_index = 0

    while True:
        ok, image = capture.read()

        if not ok:
            break

        result = pose_model.track(
            image,
            persist=True,
            tracker=TRACKER,
            imgsz=IMAGE_SIZE,
            conf=PERSON_CONFIDENCE,
            device=device,
            verbose=False,
        )[0]

        persons = []

        if result.boxes.id is not None:
            track_ids = result.boxes.id.cpu().numpy().astype(int)
            boxes = result.boxes.xyxy.cpu().numpy()
            keypoints = result.keypoints.xy.cpu().numpy()

            for index, track_id in enumerate(track_ids):
                persons.append({
                    "track_id": int(track_id),
                    "box": boxes[index],
                    "keypoints": keypoints[index],
                })

        frames.append({"timestamp_sec": frame_index / fps, "persons": persons})
        frame_index += 1

    capture.release()
    # 다음 영상이 이전 영상의 사람 번호를 이어받지 않게 추적기를 비운다
    for tracker in pose_model.predictor.trackers:
        tracker.reset()

    return frames


def select_main_track(frames):
    scores = defaultdict(float)

    for frame in frames:
        for person in frame["persons"]:
            x1, y1, x2, y2 = person["box"]
            scores[person["track_id"]] += (x2 - x1) * (y2 - y1)

    return max(scores, key=scores.get)

def calculate_angle(point_a, point_b, point_c):
    vector_ba = point_a - point_b
    vector_bc = point_c - point_b
    cosine = np.dot(vector_ba, vector_bc) / (np.linalg.norm(vector_ba) * np.linalg.norm(vector_bc))
    return float(np.degrees(np.arccos(np.clip(cosine, -1.0, 1.0))))


def build_frame_feature(keypoints):
    # 카메라 거리·위치가 달라도 같은 동작이면 같은 숫자가 나오도록 골반 중심·어깨너비 기준으로 맞춘다
    center = (keypoints[11] + keypoints[12]) / 2
    scale = np.linalg.norm(keypoints[5] - keypoints[6])
    normalized = (keypoints - center) / scale

    angles = [
        calculate_angle(keypoints[5], keypoints[7], keypoints[9]),
        calculate_angle(keypoints[6], keypoints[8], keypoints[10]),
        calculate_angle(keypoints[11], keypoints[13], keypoints[15]),
        calculate_angle(keypoints[12], keypoints[14], keypoints[16]),
    ]

    return np.concatenate([normalized.reshape(-1), angles])


def extract_frame_features(frames, main_track):
    features = []
    timestamps = []

    for frame in frames:
        for person in frame["persons"]:
            if person["track_id"] == main_track:
                features.append(build_frame_feature(person["keypoints"]))
                timestamps.append(frame["timestamp_sec"])

    return np.array(features), np.array(timestamps)

def resample_sequence(features, timestamps, steps):
    # 창마다 프레임 수가 달라서 학습 때처럼 시간 간격을 고르게 30칸으로 맞춘다
    original_x = (timestamps - timestamps[0]) / (timestamps[-1] - timestamps[0])
    target_x = np.linspace(0.0, 1.0, steps)

    return np.stack(
        [np.interp(target_x, original_x, features[:, column]) for column in range(features.shape[1])],
        axis=1,
    )


def build_window_features(features, timestamps, training_info):
    window_seconds = training_info["window_seconds"]
    stride_seconds = training_info["window_stride_seconds"]
    steps = training_info["sequence_steps"]
    min_valid_frames = training_info["min_valid_frames"]

    windows = []
    start = timestamps[0]

    while start + window_seconds <= timestamps[-1]:
        mask = (timestamps >= start) & (timestamps < start + window_seconds)

        if mask.sum() < min_valid_frames:
            # 학습 때도 프레임이 부족한 창은 판정에 쓰지 않았다
            windows.append(None)
        else:
            windows.append(resample_sequence(features[mask], timestamps[mask], steps).reshape(-1))

        start += stride_seconds

    return windows

def decide_result(windows, rf_model, training_info):
    threshold = training_info["danger_threshold"]
    repeat_windows = training_info["repeat_windows"]
    class_names = list(rf_model.classes_)
    streak_label = None
    streak = 0

    for vector in windows:
        if vector is None:
            streak_label, streak = None, 0
            continue

        probabilities = dict(zip(class_names, rf_model.predict_proba([vector])[0]))
        danger_label = max(DANGER_CLASSES, key=probabilities.get)

        if probabilities[danger_label] < threshold:
            streak_label, streak = None, 0
            continue

        # 한 창만 튀는 오탐을 줄이려고 같은 위험 행동이 연속으로 나와야 DANGER로 본다
        streak = streak + 1 if danger_label == streak_label else 1
        streak_label = danger_label

        if streak >= repeat_windows:
            return "DANGER"

    return "SAFE"

def analyze_video(video_path, models):
    frames = track_video(video_path, models["pose_model"])
    main_track = select_main_track(frames)
    features, timestamps = extract_frame_features(frames, main_track)
    windows = build_window_features(features, timestamps, models["training_info"])
    return decide_result(windows, models["rf_model"], models["training_info"])

@app.post("/predict")
def predict(file: UploadFile):
    suffix = Path(file.filename).suffix

    # OpenCV는 메모리가 아니라 파일 경로로만 영상을 열 수 있어서 임시 파일로 저장한다
    with tempfile.NamedTemporaryFile(suffix=suffix) as temp_video:
        shutil.copyfileobj(file.file, temp_video)
        temp_video.flush()
        result = analyze_video(temp_video.name, app.state.models)

    return {"result": result}