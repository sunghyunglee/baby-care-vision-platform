import json
from collections import defaultdict
from contextlib import asynccontextmanager
from pathlib import Path

import cv2
import joblib
import torch
from fastapi import FastAPI
from ultralytics import YOLO


MODEL_DIR = Path(__file__).resolve().parent / "models"

IMAGE_SIZE = 640
PERSON_CONFIDENCE = 0.25
TRACKER = "bytetrack.yaml"


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