"""
Thread-safe singleton model loader.
Implements lazy deserialization, comprehensive exception handling,
and metadata configuration retrieval.
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
        Load and cache the trained ML model artifact and associated metadata.

        Args:
            model_path: Optional custom path to model artifact .joblib file.
            force_reload: If True, bypass cache and reload from disk.

        Returns:
            Dict containing pipeline, classes, district coordinates, and metadata.

        Raises:
            ModelNotFoundError: If the artifact file does not exist on disk.
            ModelLoadError: If deserialization fails.
        """
        target_path = model_path or config.model_path

        with self._lock:
            if self._artifact is None or force_reload:
                if not target_path.exists():
                    error_msg = (
                        f"Model artifact not found at {target_path}. "
                        f"Train the model using train_model() before invoking inference."
                    )
                    logger.error(error_msg)
                    raise ModelNotFoundError(error_msg)

                try:
                    logger.info(f"Deserializing model artifact from {target_path}")
                    self._artifact = joblib.load(target_path)
                except Exception as exc:
                    error_msg = f"Failed to deserialize model artifact at {target_path}: {exc}"
                    logger.error(error_msg)
                    raise ModelLoadError(error_msg) from exc

                # Attempt to load metadata.json
                meta_path = target_path.parent / config.METADATA_FILENAME
                if meta_path.exists():
                    try:
                        with open(meta_path, "r", encoding="utf-8") as f:
                            self._metadata = json.load(f)
                    except Exception as meta_exc:
                        logger.warning(f"Could not load metadata from {meta_path}: {meta_exc}")
                        self._metadata = self._artifact.get("metadata", {})
                else:
                    self._metadata = self._artifact.get("metadata", {})

            return self._artifact

    def load_metadata(self, metadata_path: Optional[Path] = None) -> Dict[str, Any]:
        """Retrieve cached metadata or load from disk."""
        target_path = metadata_path or config.metadata_path

        with self._lock:
            if self._metadata is not None:
                return self._metadata

            if target_path.exists():
                try:
                    with open(target_path, "r", encoding="utf-8") as f:
                        self._metadata = json.load(f)
                    return self._metadata
                except Exception as exc:
                    logger.warning(f"Failed to load metadata file at {target_path}: {exc}")

            if self._artifact and "metadata" in self._artifact:
                self._metadata = self._artifact["metadata"]
                return self._metadata

            return {}

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
