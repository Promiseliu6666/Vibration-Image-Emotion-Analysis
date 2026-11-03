"""Verify that the portable FatigueSense bundle can load every model."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from fatigue_pipeline.constants import FEATURE_DIM, FEATURE_NAMES
from scripts.weights_path import (
    EYE_CKPT,
    LANDMARKER_PATH,
    MODEL_CONFIG_PATH,
    MOUTH_CKPT,
    NORMALIZATION_PATH,
    POSE_MODEL_PATH,
    TEMPORAL_MODEL_PATH,
)


EXPECTED_ASSETS = (
    EYE_CKPT,
    MOUTH_CKPT,
    POSE_MODEL_PATH,
    TEMPORAL_MODEL_PATH,
    MODEL_CONFIG_PATH,
    NORMALIZATION_PATH,
    LANDMARKER_PATH,
)


def _check_assets() -> None:
    missing = [path for path in EXPECTED_ASSETS if not Path(path).is_file()]
    if missing:
        details = "\n".join(f"  - {path}" for path in missing)
        raise FileNotFoundError(f"Missing bundle assets:\n{details}")

    empty = [path for path in EXPECTED_ASSETS if Path(path).stat().st_size == 0]
    if empty:
        details = "\n".join(f"  - {path}" for path in empty)
        raise ValueError(f"Empty bundle assets:\n{details}")


def _check_temporal_config() -> None:
    config = json.loads(Path(MODEL_CONFIG_PATH).read_text(encoding="utf-8"))
    required = {
        "hidden_dim",
        "num_layers",
        "gru_dropout",
        "head_dim",
        "head_dropout",
        "sequence_dropout",
        "pool",
    }
    missing = sorted(required - config.keys())
    if missing:
        raise ValueError(f"model_config.json is missing: {', '.join(missing)}")
    if config["pool"] not in {"last", "mean", "hidden"}:
        raise ValueError(f"Unsupported temporal pool: {config['pool']!r}")

    norm = json.loads(Path(NORMALIZATION_PATH).read_text(encoding="utf-8"))
    names = tuple(norm.get("feature_names", ()))
    mean = norm.get("mean", ())
    std = norm.get("std", ())
    if names != FEATURE_NAMES:
        raise ValueError("normalization.json feature order does not match constants.py")
    if len(mean) != FEATURE_DIM or len(std) != FEATURE_DIM:
        raise ValueError(
            f"normalization.json must contain {FEATURE_DIM} mean/std values"
        )

    print(
        "[config] "
        f"temporal pool={config['pool']} layers={config['num_layers']} "
        f"hidden={config['hidden_dim']} features={FEATURE_DIM}"
    )


def _check_model_loading() -> None:
    import torch
    from fatigue_pipeline.cnn_predictors import EyeStateClassifier, MouthStateClassifier
    from fatigue_pipeline.pose_estimator import PoseEstimator
    from fatigue_pipeline.region_cropper import RegionCropper
    from model_architecture.models.bigru_temporal import load_temporal_checkpoint

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"[runtime] torch={torch.__version__} device={device}")

    EyeStateClassifier(EYE_CKPT, device=device)
    print("[model] eye classifier loaded")

    MouthStateClassifier(MOUTH_CKPT, device=device)
    print("[model] mouth classifier loaded")

    temporal = load_temporal_checkpoint(
        TEMPORAL_MODEL_PATH,
        device,
        config_path=MODEL_CONFIG_PATH,
    )
    print(f"[model] temporal model loaded ({temporal.count_parameters():,} parameters)")

    pose = PoseEstimator(
        weights_path=POSE_MODEL_PATH,
        device=str(device) if device.type != "mps" else None,
    )
    pose.close()
    print("[model] pose model loaded")

    landmarker = RegionCropper(LANDMARKER_PATH)
    landmarker.close()
    print("[model] MediaPipe face landmarker loaded")


def main() -> int:
    bundled_root = Path(__file__).resolve().parent
    print(f"[bundle] {bundled_root}")
    try:
        _check_assets()
        print(f"[assets] {len(EXPECTED_ASSETS)} required files found")
        _check_temporal_config()
        _check_model_loading()
    except Exception as exc:
        print(f"[FAIL] {exc.__class__.__name__}: {exc}", file=sys.stderr)
        return 1

    print("[OK] All bundle models loaded successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
