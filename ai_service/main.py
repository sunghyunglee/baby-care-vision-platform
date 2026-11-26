import json
import math
from collections import defaultdict
from contextlib import asynccontextmanager
from pathlib import Path

import cv2
import joblib
import numpy as np
import torch
from fastapi import FastAPI
from ultralytics import YOLO


MODEL_DIR = Path(__file__).resolve().parent / "models"

IMAGE_SIZE = 640
PERSON_CONFIDENCE = 0.25
TRACKER = "bytetrack.yaml"

COCO_KEYPOINT_NAMES = (
    "nose",
    "left_eye",
    "right_eye",
    "left_ear",
    "right_ear",
    "left_shoulder",
    "right_shoulder",
    "left_elbow",
    "right_elbow",
    "left_wrist",
    "right_wrist",
    "left_hip",
    "right_hip",
    "left_knee",
    "right_knee",
    "left_ankle",
    "right_ankle",
)

FRAME_FEATURE_NAMES = [
    f"{name}_{axis}"
    for name in COCO_KEYPOINT_NAMES
    for axis in ("x", "y")
] + [
    "left_elbow_angle",
    "right_elbow_angle",
    "left_knee_angle",
    "right_knee_angle",
]


def load_rf_model():
    model_path = MODEL_DIR / "rf_action_baseline.joblib"
    return joblib.load(model_path)


def load_json(filename):
    file_path = MODEL_DIR / filename

    with file_path.open("r", encoding="utf-8") as file:
        return json.load(file)


def validate_model(model, feature_columns, training_info):
    if model.n_features_in_ != len(feature_columns):
        raise ValueError("Feature column count mismatch")

    if model.n_features_in_ != training_info["feature_count"]:
        raise ValueError("Training feature count mismatch")

    if model.classes_.tolist() != training_info["classes"]:
        raise ValueError("Model classes mismatch")

    if hasattr(model, "feature_names_in_"):
        if model.feature_names_in_.tolist() != feature_columns:
            raise ValueError("Feature column order mismatch")


def load_pose_model():
    model_path = MODEL_DIR / "yolo11n-pose.pt"
    return YOLO(str(model_path))


def resolve_device():
    if torch.cuda.is_available():
        return 0

    return "cpu"


def track_video(video_path, pose_model):
    device = resolve_device()
    cap = cv2.VideoCapture(str(video_path))

    frames = []
    frame_id = 0

    try:
        if not cap.isOpened():
            raise ValueError("Cannot open video")

        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0

        while True:
            ok, frame = cap.read()

            if not ok:
                break

            result = pose_model.track(
                frame,
                persist=True,
                tracker=TRACKER,
                imgsz=IMAGE_SIZE,
                conf=PERSON_CONFIDENCE,
                device=device,
                verbose=False,
            )[0]

            persons = []

            if (
                result.boxes is not None
                and result.boxes.id is not None
                and result.keypoints is not None
                and result.keypoints.conf is not None
            ):
                ids = result.boxes.id.cpu().numpy().astype(int)
                boxes = result.boxes.xyxy.cpu().numpy()
                keypoints = result.keypoints.xy.cpu().numpy()
                confidences = result.keypoints.conf.cpu().numpy()

                for i, track_id in enumerate(ids):
                    persons.append({
                        "track_id": int(track_id),
                        "box": boxes[i],
                        "kp": keypoints[i],
                        "kp_conf": confidences[i],
                    })

            frames.append({
                "frame_id": frame_id,
                "timestamp_sec": frame_id / fps,
                "persons": persons,
            })

            frame_id += 1

        if not frames:
            raise ValueError("No readable video frames")

    finally:
        cap.release()

        predictor = getattr(pose_model, "predictor", None)

        for tracker in getattr(predictor, "trackers", []):
            tracker.reset()

    return frames, fps

def box_area(box):
    width = max(box[2] - box[0], 0)
    height = max(box[3] - box[1], 0)

    return float(width * height)


def select_main_track(frames):
    scores = defaultdict(float)

    for frame in frames:
        for person in frame["persons"]:
            track_id = person["track_id"]

            if track_id < 0:
                continue

            scores[track_id] += box_area(person["box"])

    if not scores:
        return None

    return max(scores, key=scores.get)

def normalize_keypoints(keypoints):
    keypoints = np.asarray(keypoints, dtype=np.float32)

    center = (keypoints[11] + keypoints[12]) / 2.0
    scale = float(np.linalg.norm(keypoints[5] - keypoints[6]))

    if scale < 1e-8:
        raise ValueError("Invalid shoulder width")

    return (keypoints - center) / scale


def calculate_angle(point_a, point_b, point_c):
    a = np.asarray(point_a, dtype=np.float32)
    b = np.asarray(point_b, dtype=np.float32)
    c = np.asarray(point_c, dtype=np.float32)

    vector_ba = a - b
    vector_bc = c - b

    norm_ba = np.linalg.norm(vector_ba)
    norm_bc = np.linalg.norm(vector_bc)

    if norm_ba < 1e-8 or norm_bc < 1e-8:
        return float("nan")

    cosine = np.dot(vector_ba, vector_bc) / (norm_ba * norm_bc)
    cosine = np.clip(cosine, -1.0, 1.0)

    return float(math.degrees(math.acos(float(cosine))))


def selected_joint_angles(keypoints):
    return [
        calculate_angle(keypoints[5], keypoints[7], keypoints[9]),
        calculate_angle(keypoints[6], keypoints[8], keypoints[10]),
        calculate_angle(keypoints[11], keypoints[13], keypoints[15]),
        calculate_angle(keypoints[12], keypoints[14], keypoints[16]),
    ]


def build_frame_feature(keypoints):
    keypoints = np.asarray(keypoints, dtype=np.float32)

    if keypoints.shape != (17, 2):
        return None

    if not np.all(np.isfinite(keypoints)):
        return None

    try:
        normalized = normalize_keypoints(keypoints)
    except ValueError:
        return None

    angles = selected_joint_angles(keypoints)

    feature = np.concatenate([
        normalized.reshape(-1),
        np.asarray(angles, dtype=np.float32),
    ])

    if len(feature) != len(FRAME_FEATURE_NAMES):
        raise RuntimeError("Frame feature count mismatch")

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

            feature = build_frame_feature(person["kp"])

            if feature is not None:
                features.append(feature)
                timestamps.append(frame["timestamp_sec"])

            break

    if not features:
        return (
            np.empty((0, len(FRAME_FEATURE_NAMES)), dtype=np.float32),
            np.empty(0, dtype=np.float64),
        )

    return (
        np.stack(features),
        np.asarray(timestamps, dtype=np.float64),
    )

@asynccontextmanager
async def lifespan(app: FastAPI):
    model = load_rf_model()
    feature_columns = load_json("rf_feature_columns.json")
    training_info = load_json("rf_training_info.json")

    validate_model(model, feature_columns, training_info)

    app.state.rf_model = model
    app.state.feature_columns = feature_columns
    app.state.training_info = training_info
    app.state.pose_model = load_pose_model()

    yield


app = FastAPI(lifespan=lifespan)