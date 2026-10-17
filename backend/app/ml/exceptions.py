"""
Custom exceptions for the Cybercrime Cash-Withdrawal Prediction ML pipeline.
"""


class MLBaseException(Exception):
    """Base exception for all ML pipeline errors."""

    pass


class ModelNotFoundError(MLBaseException):
    """Raised when the requested model artifact or metadata is not found on disk."""

    pass


class ModelLoadError(MLBaseException):
    """Raised when the model artifact exists but cannot be deserialized or loaded."""

    pass


class InvalidInputError(MLBaseException):
    """Raised when the input prediction payload is malformed or invalid."""

    pass


class DatasetNotFoundError(MLBaseException):
    """Raised when the requested raw complaint dataset file is missing."""

    pass


class SchemaValidationError(MLBaseException):
    """Raised when an ingested complaint dataset fails required column schema validation."""

    pass
