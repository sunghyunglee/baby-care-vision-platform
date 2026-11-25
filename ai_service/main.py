import json
from pathlib import Path

import joblib


MODEL_DIR = Path(__file__).resolve().parent / "models"


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


if __name__ == "__main__":
    model = load_rf_model()
    feature_columns = load_json("rf_feature_columns.json")
    training_info = load_json("rf_training_info.json")

    validate_model(model, feature_columns, training_info)

    print("RF model loaded successfully")
    print("Model metadata validation passed")
    print("Classes:", model.classes_)
    print("Feature count:", model.n_features_in_)
    print("Feature columns:", len(feature_columns))
    print("Model version:", training_info["model_version"])
    print("Danger threshold:", training_info["danger_threshold"])
    print("Repeat windows:", training_info["repeat_windows"])