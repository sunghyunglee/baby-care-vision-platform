import json
import math
import shutil
import tempfile
from collections import defaultdict
from contextlib import asynccontextmanager
from pathlib import Path
from threading import Lock

import cv2
import joblib
import numpy as np
import torch
from fastapi import FastAPI, HTTPException, UploadFile
from ultralytics import YOLO


MODEL_DIR = Path(__file__).resolve().parent / "models"

IMAGE_SIZE = 640
PERSON_CONFIDENCE = 0.25
TRACKER = "bytetrack.yaml"

DANGER_CLASSES = ("shake", "drop", "look_away")


def load_json(filename):
    with (MODEL_DIR / filename).open("r", encoding="utf-8") as file:
        return json.load(file)


def validate_model(rf_model, training_info):
    # 학습 때와 특징 수·클래스가 다르면 틀린 판정을 내기 전에 서버 시작을 막는다
    if rf_model.n_features_in_ != training_info["feature_count"]:
        raise ValueError("Training feature count mismatch")

    if rf_model.classes_.tolist() != training_info["classes"]:
        raise ValueError("Model classes mismatch")


def load_models():
    rf_model = joblib.load(MODEL_DIR / "rf_action_baseline.joblib")
    training_info = load_json("rf_training_info.json")

    validate_model(rf_model, training_info)

    return {
        "rf_model": rf_model,
        "training_info": training_info,
        "pose_model": YOLO(str(MODEL_DIR / "yolo11n-pose.pt")),
    }


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 요청마다 모델 파일을 다시 읽지 않도록 서버 시작 때 한 번만 올려둔다
    app.state.models = load_models()
    # YOLO 추적기는 이전 프레임을 기억해서 두 영상이 동시에 들어오면 사람 번호가 섞인다
    app.state.pose_lock = Lock()
    yield


app = FastAPI(lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/predict")
def predict(file: UploadFile):
    suffix = Path(file.filename or "").suffix or ".mp4"

    # OpenCV는 메모리가 아니라 파일 경로로만 영상을 열 수 있어서 임시 파일로 저장한다
    with tempfile.NamedTemporaryFile(suffix=suffix) as temp_video:
        shutil.copyfileobj(file.file, temp_video)
        temp_video.flush()

        try:
            result = analyze_video(temp_video.name, app.state.models, app.state.pose_lock)
        except ValueError as error:
            # 분석할 수 없는 영상을 SAFE로 보내지 않고 이유와 함께 422로 알린다
            raise HTTPException(status_code=422, detail=str(error)) from error

    return {"result": result}


def track_video(video_path, pose_model):
    device = 0 if torch.cuda.is_available() else "cpu"
    capture = cv2.VideoCapture(str(video_path))
    frames = []

    try:
        if not capture.isOpened():
            raise ValueError("Cannot open video")

        fps = capture.get(cv2.CAP_PROP_FPS)
        # 일부 영상은 FPS 정보가 비어 있어서 일반적인 30으로 가정한다
        if not math.isfinite(fps) or fps <= 0:
            fps = 30.0

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

            if result.boxes is not None and result.boxes.id is not None and result.keypoints is not None:
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
    finally:
        capture.release()
        # 오류가 나도 다음 영상이 이전 영상의 사람 번호를 이어받지 않게 추적기를 비운다
        predictor = getattr(pose_model, "predictor", None)

        for tracker in getattr(predictor, "trackers", []):
            tracker.reset()

    if not frames:
        raise ValueError("No readable video frames")

    return frames


def select_main_track(frames):
    scores = defaultdict(float)

    for frame in frames:
        for person in frame["persons"]:
            if person["track_id"] < 0:
                continue

            x1, y1, x2, y2 = person["box"]
            scores[person["track_id"]] += max(x2 - x1, 0) * max(y2 - y1, 0)

    if not scores:
        raise ValueError("No main performer detected")

    return max(scores, key=scores.get)


def calculate_angle(point_a, point_b, point_c):
    vector_ba = point_a - point_b
    vector_bc = point_c - point_b
    norm_product = np.linalg.norm(vector_ba) * np.linalg.norm(vector_bc)

    if norm_product < 1e-8:
        return float("nan")

    cosine = np.dot(vector_ba, vector_bc) / norm_product
    return float(np.degrees(np.arccos(np.clip(cosine, -1.0, 1.0))))


def build_frame_feature(keypoints):
    scale = np.linalg.norm(keypoints[5] - keypoints[6])

    # 어깨가 안 잡혀 어깨너비로 정규화할 수 없는 프레임은 학습 때처럼 버린다
    if scale < 1e-8:
        return None

    # 카메라 거리·위치가 달라도 같은 동작이면 같은 숫자가 나오도록 골반 중심·어깨너비 기준으로 맞춘다
    center = (keypoints[11] + keypoints[12]) / 2
    normalized = (keypoints - center) / scale

    angles = [
        calculate_angle(keypoints[5], keypoints[7], keypoints[9]),
        calculate_angle(keypoints[6], keypoints[8], keypoints[10]),
        calculate_angle(keypoints[11], keypoints[13], keypoints[15]),
        calculate_angle(keypoints[12], keypoints[14], keypoints[16]),
    ]

    feature = np.concatenate([normalized.reshape(-1), angles])

    if not np.all(np.isfinite(feature)):
        return None

    return feature


def extract_frame_features(frames, main_track):
    features = []
    timestamps = []

    for frame in frames:
        for person in frame["persons"]:
            if person["track_id"] != main_track:
                continue

            feature = build_frame_feature(person["keypoints"])

            if feature is not None:
                features.append(feature)
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

    while start + window_seconds <= timestamps[-1] + 1e-6:
        mask = (timestamps >= start) & (timestamps < start + window_seconds)

        if mask.sum() < min_valid_frames:
            # 학습 때도 프레임이 부족한 창은 판정에 쓰지 않았다
            windows.append(None)
        else:
            windows.append(resample_sequence(features[mask], timestamps[mask], steps).reshape(-1))

        start += stride_seconds

    return windows


def decide_result(windows, rf_model, training_info):
    if not windows:
        raise ValueError("No analysis windows")

    threshold = training_info["danger_threshold"]
    repeat_windows = training_info["repeat_windows"]
    class_names = list(rf_model.classes_)
    streak_label = None
    streak = 0
    has_invalid_window = False

    for vector in windows:
        if vector is None:
            streak_label, streak = None, 0
            has_invalid_window = True
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

    # 분석 못 한 구간이 있으면 '확인 못 함'이 '안전'으로 보이지 않도록 SAFE 대신 오류로 처리한다
    if has_invalid_window:
        raise ValueError("Incomplete video analysis")

    return "SAFE"


def analyze_video(video_path, models, pose_lock):
    training_info = models["training_info"]

    with pose_lock:
        frames = track_video(video_path, models["pose_model"])

    main_track = select_main_track(frames)
    features, timestamps = extract_frame_features(frames, main_track)

    if len(features) < training_info["min_valid_frames"]:
        raise ValueError("Insufficient valid pose frames")

    windows = build_window_features(features, timestamps, training_info)
    return decide_result(windows, models["rf_model"], training_info)