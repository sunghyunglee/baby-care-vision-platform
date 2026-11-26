import json
import math
from collections import defaultdict
from contextlib import asynccontextmanager
from pathlib import Path
from threading import Lock

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

DANGER_CLASSES = ("shake", "drop", "look_away")


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

        fps = cap.get(cv2.CAP_PROP_FPS)
        if not math.isfinite(fps) or fps <= 0:
            fps = 30.0

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
            ):
                ids = result.boxes.id.cpu().numpy().astype(int)
                boxes = result.boxes.xyxy.cpu().numpy()
                keypoints = result.keypoints.xy.cpu().numpy()

                for i, track_id in enumerate(ids):
                    persons.append({
                        "track_id": int(track_id),
                        "box": boxes[i],
                        "kp": keypoints[i],
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


def sliding_windows(timestamps, window_seconds, stride_seconds):
    if len(timestamps) == 0:
        return []

    start = float(timestamps.min())
    last = float(timestamps.max())

    windows = []

    while start + window_seconds <= last + 1e-6:
        end = start + window_seconds

        windows.append((start, end))
        start += stride_seconds

    return windows


def resample_sequence(features, timestamps, target_steps):
    features = np.asarray(features, dtype=np.float32)
    timestamps = np.asarray(timestamps, dtype=np.float32)

    if features.ndim != 2:
        raise ValueError("Invalid feature dimensions")

    if len(features) != len(timestamps):
        raise ValueError("Feature and timestamp count mismatch")

    if len(features) < 2:
        raise ValueError("At least two frames are required")

    if target_steps < 2:
        raise ValueError("At least two target steps are required")

    span = timestamps[-1] - timestamps[0]

    if span <= 0:
        raise ValueError("Invalid timestamp range")

    original_x = (timestamps - timestamps[0]) / span
    target_x = np.linspace(0.0, 1.0, target_steps)

    output = np.empty(
        (target_steps, features.shape[1]),
        dtype=np.float32,
    )

    for feature_index in range(features.shape[1]):
        output[:, feature_index] = np.interp(
            target_x,
            original_x,
            features[:, feature_index],
        )

    return output


def window_vector(
    timestamps,
    features,
    start,
    end,
    steps,
    min_valid_frames,
):
    mask = (timestamps >= start) & (timestamps < end)

    if mask.sum() < max(min_valid_frames, 2):
        return None

    sequence = resample_sequence(
        features[mask],
        timestamps[mask],
        steps,
    )

    return sequence.reshape(-1)


def build_window_features(features, timestamps, training_info):
    window_seconds = training_info["window_seconds"]
    stride_seconds = training_info["window_stride_seconds"]
    steps = training_info["sequence_steps"]
    min_valid_frames = training_info["min_valid_frames"]

    windows = sliding_windows(
        timestamps,
        window_seconds,
        stride_seconds,
    )

    results = []

    for start, end in windows:
        vector = window_vector(
            timestamps,
            features,
            start,
            end,
            steps,
            min_valid_frames,
        )

        results.append({
            "start": start,
            "end": end,
            "features": vector,
        })

    return results


def predict_windows(rf_model, windows, feature_columns):
    results = []

    for window in windows:
        vector = window["features"]

        if vector is None:
            results.append({
                "start": window["start"],
                "end": window["end"],
                "action": None,
                "confidence": None,
                "probabilities": None,
            })

            continue

        if vector.shape != (len(feature_columns),):
            raise ValueError("Invalid feature vector shape")

        probabilities = rf_model.predict_proba(
            vector.reshape(1, -1)
        )[0]

        best_index = int(np.argmax(probabilities))

        results.append({
            "start": window["start"],
            "end": window["end"],
            "action": str(rf_model.classes_[best_index]),
            "confidence": float(probabilities[best_index]),
            "probabilities": {
                str(label): float(probability)
                for label, probability in zip(
                    rf_model.classes_,
                    probabilities,
                )
            },
        })

    return results


def decide_video(predictions, training_info):
    threshold = training_info["danger_threshold"]
    repeat_windows = training_info["repeat_windows"]

    streak_label = None
    streak = 0
    has_invalid_window = False

    if not predictions:
        raise ValueError("No analysis windows")

    for prediction in predictions:
        probabilities = prediction["probabilities"]

        if probabilities is None:
            streak_label = None
            streak = 0
            has_invalid_window = True
            continue

        danger_label = max(
            DANGER_CLASSES,
            key=lambda label: probabilities[label],
        )

        danger_probability = probabilities[danger_label]

        if danger_probability >= threshold:
            if streak_label == danger_label:
                streak += 1
            else:
                streak_label = danger_label
                streak = 1
        else:
            streak_label = None
            streak = 0

        if streak >= repeat_windows:
            return "DANGER"

    if has_invalid_window:
        raise ValueError("Incomplete video analysis")

    return "SAFE"


def predict_video(video_path, app: FastAPI) -> str:
    pose_model = app.state.pose_model
    rf_model = app.state.rf_model
    feature_columns = app.state.feature_columns
    training_info = app.state.training_info

    expected_columns = [
        f"t{step:02d}_{name}"
        for step in range(training_info["sequence_steps"])
        for name in FRAME_FEATURE_NAMES
    ]

    if expected_columns != feature_columns:
        raise ValueError("Feature column order mismatch")

    with app.state.pose_lock:
        frames, _ = track_video(video_path, pose_model)

    main_track = select_main_track(frames)

    if main_track is None:
        raise ValueError("No main performer detected")

    features, timestamps = extract_frame_features(
        frames,
        main_track,
    )

    if len(features) < training_info["min_valid_frames"]:
        raise ValueError("Insufficient valid pose frames")

    windows = build_window_features(
        features,
        timestamps,
        training_info,
    )

    predictions = predict_windows(
        rf_model,
        windows,
        feature_columns,
    )

    return decide_video(predictions, training_info)


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
    app.state.pose_lock = Lock()

    yield


app = FastAPI(lifespan=lifespan)
