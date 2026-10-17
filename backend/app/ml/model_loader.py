"""
Thread-safe singleton model loader.
Implements lazy deserialization, metadata verification, comprehensive exception handling,
and readiness check that never raises.
"""

import json
import logging
import threading
from pathlib import Path
from typing import Optional, Dict, Any
import joblib

from backend.app.ml.config import config
from backend.app.ml.exceptions import ModelNotFoundError, ModelLoadError

logger = logging.getLogger(__name__)


class ModelLoader:
    """Thread-safe singleton for caching and serving deserialized model artifacts."""

    _instance: Optional["ModelLoader"] = None
    _lock: threading.Lock = threading.Lock()
    _artifact: Optional[Dict[str, Any]] = None
    _metadata: Optional[Dict[str, Any]] = None

    def __new__(cls) -> "ModelLoader":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(ModelLoader, cls).__new__(cls)
        return cls._instance

    def load_model(
        self,
        model_path: Optional[Path] = None,
        force_reload: bool = False,
    ) -> Dict[str, Any]:
        """
        Load and cache the trained ML model artifact and verify associated metadata.

        Args:
            model_path: Optional custom path to model artifact .joblib file.
            force_reload: If True, bypass cache and reload from disk.

        Returns:
            Dict containing pipeline, classes, district coordinates, and metadata.

        Raises:
            ModelNotFoundError: If model artifact or metadata.json does not exist.
            ModelLoadError: If deserialization fails or metadata is corrupted.
        """
        target_path = model_path or config.model_path
        meta_path = target_path.parent / config.METADATA_FILENAME

        with self._lock:
            if self._artifact is None or force_reload:
                # 1. Verify model artifact exists
                if not target_path.exists():
                    error_msg = (
                        f"Model artifact not found at {target_path}. "
                        f"Please train the model using 'python -m backend.app.ml.train' before invoking inference."
                    )
                    logger.error(error_msg)
                    raise ModelNotFoundError(error_msg)

                # 2. Verify metadata.json exists
                if not meta_path.exists():
                    error_msg = (
                        f"Model metadata not found at {meta_path}. "
                        f"Please train the model using 'python -m backend.app.ml.train' to generate metadata.json."
                    )
                    logger.error(error_msg)
                    raise ModelNotFoundError(error_msg)

                # 3. Deserialize model artifact
                try:
                    logger.info(f"Deserializing model artifact from {target_path}")
                    self._artifact = joblib.load(target_path)
                except Exception as exc:
                    error_msg = f"Failed to deserialize model artifact at {target_path}: {exc}"
                    logger.error(error_msg)
                    raise ModelLoadError(error_msg) from exc

                # 4. Load and verify metadata.json
                try:
                    with open(meta_path, "r", encoding="utf-8") as f:
                        meta_content = json.load(f)
                    if not isinstance(meta_content, dict):
                        raise ValueError("Metadata root element must be a dictionary")
                    self._metadata = meta_content
                except Exception as meta_exc:
                    error_msg = f"Corrupted or invalid metadata.json at {meta_path}: {meta_exc}"
                    logger.error(error_msg)
                    raise ModelLoadError(error_msg) from meta_exc

            return self._artifact

    def load_metadata(self, metadata_path: Optional[Path] = None) -> Dict[str, Any]:
        """Retrieve cached metadata or load from disk, raising ModelNotFoundError if absent."""
        target_path = metadata_path or config.metadata_path

        with self._lock:
            if self._metadata is not None:
                return self._metadata

            if not target_path.exists():
                error_msg = (
                    f"Model metadata file not found at {target_path}. "
                    f"Please train the model using 'python -m backend.app.ml.train' before invoking inference."
                )
                logger.error(error_msg)
                raise ModelNotFoundError(error_msg)

            try:
                with open(target_path, "r", encoding="utf-8") as f:
                    self._metadata = json.load(f)
                return self._metadata
            except Exception as exc:
                error_msg = f"Failed to load metadata file at {target_path}: {exc}"
                logger.error(error_msg)
                raise ModelLoadError(error_msg) from exc

    def is_model_ready(self, model_path: Optional[Path] = None) -> bool:
        """
        Check if model artifacts exist and are ready for inference.
        Guaranteed to NEVER raise an exception.

        Returns:
            bool: True if model and metadata exist or are loaded; False otherwise.
        """
        try:
            if self._artifact is not None and self._metadata is not None:
                return True

            target_path = model_path or config.model_path
            meta_path = target_path.parent / config.METADATA_FILENAME

            return bool(target_path.is_file() and meta_path.is_file())
        except Exception:
            return False

    def is_model_loaded(self) -> bool:
        """Check if model artifact is currently in-memory."""
        return self._artifact is not None

    def clear_cache(self) -> None:
        """Clear cached artifact and metadata for test isolation."""
        with self._lock:
            self._artifact = None
            self._metadata = None


# Convenience singleton instance (lazy; does NOT perform disk I/O on import)
model_loader = ModelLoader()


def is_model_ready(model_path: Optional[Path] = None) -> bool:
    """Module-level helper to check if model artifacts are ready. Never raises."""
    return model_loader.is_model_ready(model_path=model_path)
