"""Portable checkpoint and asset paths for this self-contained bundle."""

from __future__ import annotations

from pathlib import Path


def resolve_asset(path_or_spec: str | Path) -> Path:
    """Return a local asset path, optionally downloading an hf:// asset."""
    if isinstance(path_or_spec, str) and path_or_spec.startswith("hf://"):
        from huggingface_hub import hf_hub_download

        spec = path_or_spec[len("hf://") :]
        repo_id, filename = spec.rsplit("/", 1)
        return Path(hf_hub_download(repo_id=repo_id, filename=filename))

    path = Path(path_or_spec)
    if not path.exists():
        raise FileNotFoundError(f"Asset missing: {path}")
    return path

_BUNDLE_ROOT = Path(__file__).resolve().parents[1]
ASSET_DIR = _BUNDLE_ROOT / "assets"

# ---- MediaPipe Face Landmarker (Phase A) ----
LANDMARKER_PATH: str | Path = ASSET_DIR / "face_landmarker.task"

# ---- YOLO pose (Phase A2) ----
POSE_MODEL_PATH = ASSET_DIR / "best_pose_model.pt"

# ---- CNN (Phase B) ----
EYE_CKPT = ASSET_DIR / "best_eyes.pt"
MOUTH_CKPT = ASSET_DIR / "best_mouth.pt"

# ---- BiGRU temporal (Phase C) ----
TEMPORAL_MODEL_PATH = ASSET_DIR / "best_temporal.pt"
MODEL_CONFIG_PATH = ASSET_DIR / "model_config.json"
NORMALIZATION_PATH = ASSET_DIR / "normalization.json"
