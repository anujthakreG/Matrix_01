"""
Data cleaning, normalization, and feature derivation module.
Enforces text sanitation, out-of-vocabulary mapping to 'other', and robust datetime parsing.
"""

import logging
import re
from datetime import datetime, timezone
from typing import Dict, List, Any, Tuple, Optional, Set
import numpy as np
import pandas as pd

from backend.app.ml.config import config

logger = logging.getLogger(__name__)


def normalize_category_string(category: str) -> str:
    """Normalize fraud category: lowercase, spaces/hyphens/slashes to underscores."""
    if not category or not isinstance(category, str):
        return "other"
    cleaned = re.sub(r"[\s\-/]+", "_", category.strip().lower())
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    return cleaned or "other"


def normalize_channel_string(channel: str) -> str:
    """Normalize payment/source channel to uppercase."""
    if not channel or not isinstance(channel, str):
        return "other"
    cleaned = channel.strip().upper()
    return cleaned or "other"


def normalize_location_string(location: str) -> str:
    """Normalize district/state names to Title Case."""
    if not location or not isinstance(location, str):
        return "Unknown"
    cleaned = location.strip().title()
    return cleaned or "Unknown"


def parse_timestamp_features(
    timestamp_val: Optional[Any],
) -> Tuple[datetime, int, int, int]:
    """
    Parse timestamp into datetime and derive hour, dayofweek, and is_weekend.
    Falls back to current UTC datetime if null or unparseable.
    """
    dt: Optional[datetime] = None
    if timestamp_val is not None:
        if isinstance(timestamp_val, (pd.Timestamp, datetime)):
            dt = timestamp_val if isinstance(timestamp_val, datetime) else timestamp_val.to_pydatetime()
        elif isinstance(timestamp_val, str) and timestamp_val.strip():
            try:
                parsed = pd.to_datetime(timestamp_val, errors="coerce")
                if not pd.isna(parsed):
                    dt = parsed.to_pydatetime()
            except Exception:
                pass

    if dt is None:
        dt = datetime.now(timezone.utc)

    # Derive numerical calendar features
    hour = int(dt.hour)
    dayofweek = int(dt.weekday())  # 0=Monday, 6=Sunday
    is_weekend = 1 if dayofweek in (5, 6) else 0

    return dt, hour, dayofweek, is_weekend


def clean_and_normalize_record(
    payload: Dict[str, Any],
    known_categories: Optional[Set[str]] = None,
    known_channels: Optional[Set[str]] = None,
) -> Tuple[Dict[str, Any], List[str]]:
    """
    Clean and normalize a single inference payload or record dictionary.

    Returns:
        Tuple of (normalized_record_dict, mapping_risk_notes_list)
    """
    categories_set = known_categories or set(config.KNOWN_CATEGORIES)
    channels_set = known_channels or set(config.KNOWN_CHANNELS)
    mapping_notes: List[str] = []

    # 1. Category normalization & out-of-vocabulary mapping
    raw_category = payload.get(config.PAYLOAD_CATEGORY) or payload.get("fraud_category") or "other"
    norm_category = normalize_category_string(str(raw_category))
    if norm_category not in categories_set:
        mapping_notes.append(
            f"Category mapped to 'other' (unseen category: '{raw_category}')"
        )
        norm_category = "other"

    # 2. Source Channel normalization & out-of-vocabulary mapping
    raw_channel = payload.get(config.PAYLOAD_SOURCE_CHANNEL) or payload.get("payment_channel") or "UPI"
    norm_channel = normalize_channel_string(str(raw_channel))
    if norm_channel not in channels_set:
        mapping_notes.append(
            f"Source channel mapped to 'other' (unseen channel: '{raw_channel}')"
        )
        norm_channel = "other"

    # 3. Location normalization
    raw_state = payload.get(config.PAYLOAD_VICTIM_STATE) or "Unknown"
    norm_state = normalize_location_string(str(raw_state))

    raw_district = payload.get(config.PAYLOAD_VICTIM_DISTRICT) or "Unknown"
    norm_district = normalize_location_string(str(raw_district))

    # 4. Amount parsing & log transformation
    raw_amount = payload.get(config.PAYLOAD_REPORTED_AMOUNT) or payload.get("amount_lost") or 0.0
    try:
        amount_float = float(raw_amount)
    except (ValueError, TypeError):
        amount_float = 0.0
    amount_clipped = max(0.0, amount_float)
    amount_log = float(np.log1p(amount_clipped))

    # 5. Mule Hop Count derivation: len(mule_accounts)
    mule_accounts = payload.get(config.PAYLOAD_MULE_ACCOUNTS)
    if isinstance(mule_accounts, list):
        mule_hop_count = len(mule_accounts)
    elif config.COL_MULE_HOP_COUNT in payload:
        try:
            mule_hop_count = max(0, int(payload[config.COL_MULE_HOP_COUNT]))
        except (ValueError, TypeError):
            mule_hop_count = 0
    elif "hop_level" in payload:
        try:
            mule_hop_count = max(0, int(payload["hop_level"]))
        except (ValueError, TypeError):
            mule_hop_count = 0
    else:
        mule_hop_count = 0

    # 6. Timestamp resolution: incident_date > incident_time > reported_at > overrides > request-time now()
    overrides = payload.get(config.PAYLOAD_OVERRIDES) or {}
    ts_val = (
        payload.get(config.PAYLOAD_INCIDENT_DATE)
        or payload.get(config.COL_INCIDENT_TIME)
        or overrides.get("incident_timestamp")
        or payload.get(config.PAYLOAD_REPORTED_AT)
    )
    dt, hour, dayofweek, is_weekend = parse_timestamp_features(ts_val)

    normalized_record = {
        config.COL_REPORTED_AMOUNT: amount_clipped,
        config.COL_AMOUNT_LOG: amount_log,
        config.COL_CATEGORY: norm_category,
        config.COL_VICTIM_STATE: norm_state,
        config.COL_VICTIM_DISTRICT: norm_district,
        config.COL_SOURCE_CHANNEL: norm_channel,
        config.COL_MULE_HOP_COUNT: mule_hop_count,
        config.COL_INCIDENT_TIME: dt.isoformat(),
        config.COL_INCIDENT_HOUR: hour,
        config.COL_INCIDENT_DAYOFWEEK: dayofweek,
        config.COL_IS_WEEKEND: is_weekend,
    }

    # Pass through target columns if present in payload (for training / testing)
    if config.TARGET_COLUMN in payload:
        normalized_record[config.TARGET_COLUMN] = payload[config.TARGET_COLUMN]
    if config.COL_COMPLAINT_ID in payload:
        normalized_record[config.COL_COMPLAINT_ID] = payload[config.COL_COMPLAINT_ID]

    return normalized_record, mapping_notes


def clean_and_normalize_complaints(
    df: pd.DataFrame,
    known_categories: Optional[Set[str]] = None,
    known_channels: Optional[Set[str]] = None,
) -> pd.DataFrame:
    """
    Clean, sanitize, and normalize an entire DataFrame of complaint records.
    Maps out-of-vocabulary categories/channels to 'other'.
    """
    records = []
    for _, row in df.iterrows():
        record_dict = row.to_dict()
        normalized_row, _ = clean_and_normalize_record(
            record_dict,
            known_categories=known_categories,
            known_channels=known_channels,
        )
        records.append(normalized_row)

    normalized_df = pd.DataFrame(records)
    return normalized_df
