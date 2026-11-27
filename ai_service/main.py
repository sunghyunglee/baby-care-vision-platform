import json
import math
import shutil
import tempfile
from collections import defaultdict
from contextlib import asynccontextmanager, contextmanager
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

@asynccontextmanager
async def lifespan(app: FastAPI): # 한번만 실행, 모델을 app.state에 올려둠
    # 요청마다 모델 파일을 다시 읽지 않도록 서버 시작 때 한 번만 올려둔다
    app.state.models = load_models()
    # YOLO 추적기는 이전 프레임을 기억해서 두 영상이 동시에 들어오면 사람 번호가 섞인다
    app.state.pose_lock = Lock()
    yield

app = FastAPI(lifespan=lifespan)
@app.get("/health")
def health(): # 서버 키고 모델로딩까지 된건지 확인
    return {"status": "ok"}

# ===== 입력부 =====
@contextmanager
def receive_video(file): 
    suffix = Path(file.filename or "").suffix or ".mp4"

    # OpenCV는 메모리가 아니라 파일 경로로만 영상을 열 수 있어서 임시 파일로 저장한다
    with tempfile.NamedTemporaryFile(suffix=suffix) as temp_video:
        shutil.copyfileobj(file.file, temp_video)
        temp_video.flush()
        # 분석이 끝날 때까지 파일을 지우지 않도록 return 대신 yield로 경로를 넘긴다
        yield temp_video.name


# ===== 출력부 =====
def send_result(result): # result를 key : value 값으로 하는 함수
    return {"result": result}

def reject_video(error): # error 띄우는 함수
    # 분석할 수 없는 영상을 SAFE로 보내지 않고 이유와 함께 422로 알린다
    return HTTPException(status_code=422, detail=str(error))

@app.post("/predict")
def predict(file: UploadFile):
    with receive_video(file) as video_path:
        try:
            result = analyze_video(video_path, app.state.models, app.state.pose_lock)
        except ValueError as error:
            raise reject_video(error) from error

    return send_result(result)

# ===== 로직부 =====

# 1. load_json : models 폴더 안의 JSON 파일 하나를 읽어 파이썬 dict로 돌려준다

def load_json(filename): # models.py json파일 읽기
    with (MODEL_DIR / filename).open("r", encoding="utf-8") as file:
        return json.load(file)


# 2. load_models : RF 모델(joblib)·학습 설정(json)·YOLO 포즈 모델을 읽어 하나로 묶어 돌려준다

def load_models(): 
    rf_model = joblib.load(MODEL_DIR / "rf_action_baseline.joblib")
    training_info = load_json("rf_training_info.json")

    validate_model(rf_model, training_info)

    return {
        "rf_model": rf_model,
        "training_info": training_info,
        "pose_model": YOLO(str(MODEL_DIR / "yolo11n-pose.pt")),
    }


# 3. validate_model : RF 모델의 특징 수·클래스가 학습 설정과 같은지 확인하고, 다르면 서버 시작을 막는다

def validate_model(rf_model, training_info):
    # 학습 때와 특징 수·클래스가 다르면 틀린 판정을 내기 전에 서버 시작을 막는다
    if rf_model.n_features_in_ != training_info["feature_count"]:
        raise ValueError("Training feature count mismatch")

    if rf_model.classes_.tolist() != training_info["classes"]:
        raise ValueError("Model classes mismatch")
        

# 4. health : (중복) 위쪽 /health 와 같은 내용의 함수, 주소가 연결되지 않아 실행되지 않는다

def health(): # 서버 키고 모델로딩까지 된건지 확인
    return {"status": "ok"}


# 5. track_video : 영상을 프레임 단위로 읽어 프레임마다 사람별 번호·박스·관절 17개와 시각을 모은다

def track_video(video_path, pose_model): # 영상 -> 프레임별 사람 관절 좌표로 바꾸기
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


# 6. select_main_track : 영상 전체에서 박스 넓이 합이 가장 큰 사람을 분석 대상(주인공)으로 고른다

def select_main_track(frames): # 영상에 여러 사람이 등장할수 있어서, 분석할 사람 한명을 고름
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


# 7. calculate_angle : 세 점으로 가운데 관절(point_b)의 각도를 도(°) 단위로 구한다

def calculate_angle(point_a, point_b, point_c): # 관절각도 구하는 방식
    vector_ba = point_a - point_b
    vector_bc = point_c - point_b
    norm_product = np.linalg.norm(vector_ba) * np.linalg.norm(vector_bc)

    if norm_product < 1e-8:
        return float("nan")

    cosine = np.dot(vector_ba, vector_bc) / norm_product
    return float(np.degrees(np.arccos(np.clip(cosine, -1.0, 1.0))))


# 8. build_frame_feature : 프레임 하나의 관절 17개를 정규화 좌표 34개 + 팔꿈치·무릎 각도 4개 = 특징 38개로 바꾼다

def build_frame_feature(keypoints): # 프레임별 관절 17개를 -> keypoint 34개 + 관절각도 4개
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


# 9. extract_frame_features : 모든 프레임에서 주인공의 특징 38개와 그 시각만 모아 배열로 돌려준다

def extract_frame_features(frames, main_track): # 모든 프레임에서 주인공만 골라서 38개 특징과 시각 모으기 : 프레임수 x 38
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


# 10. resample_sequence : 2초 창 하나의 프레임들을 보간해서 정확히 30칸 × 38로 맞춘다

def resample_sequence(features, timestamps, steps): # 2초창 하나를 30칸으로 맞추기 
    # 창마다 프레임 수가 달라서 학습 때처럼 시간 간격을 고르게 30칸으로 맞춘다
    original_x = (timestamps - timestamps[0]) / (timestamps[-1] - timestamps[0])
    target_x = np.linspace(0.0, 1.0, steps)

    return np.stack(
        [np.interp(target_x, original_x, features[:, column]) for column in range(features.shape[1])],
        axis=1,
    )


# 11. build_window_features : 영상을 2초 창으로 0.5초씩 밀며 자르고, 창마다 RF 입력인 숫자 1140개(30 × 38) 한 줄을 만든다

def build_window_features(features, timestamps, training_info): # 영상을 2초씩 0.5초간격으로 겹치게 만들어서 창을 만들고 30 X 38 (1sec x 38 )
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


# 12. decide_result : 창마다 RF로 행동 확률을 내고, 위험 행동이 연속으로 나오는지 보고 SAFE / DANGER를 정한다

def decide_result(windows, rf_model, training_info): # 창마다 rf로 확률내고 위험행동이 0.35 이상으로 2창 연속이면 danger, 아니면 safe 기준
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


# 13. analyze_video : 5~12번 함수를 순서대로 실행해서 영상 하나의 최종 결과("SAFE"/"DANGER")를 돌려준다

def analyze_video(video_path, models, pose_lock): # 영상분석
    training_info = models["training_info"]

    with pose_lock:
        frames = track_video(video_path, models["pose_model"])

    main_track = select_main_track(frames)
    features, timestamps = extract_frame_features(frames, main_track)

    if len(features) < training_info["min_valid_frames"]:
        raise ValueError("Insufficient valid pose frames")

    windows = build_window_features(features, timestamps, training_info)
    return decide_result(windows, models["rf_model"], training_info)
