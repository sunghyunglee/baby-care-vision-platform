from pathlib import Path

import joblib


MODEL_DIR = Path(__file__).resolve().parent / "models"


def load_rf_model():
    model_path = MODEL_DIR / "rf_action_baseline.joblib"
    return joblib.load(model_path)


if __name__ == "__main__":
    model = load_rf_model()

    print("RF model loaded successfully")
    print("Classes:", model.classes_)
    print("Feature count:", model.n_features_in_)