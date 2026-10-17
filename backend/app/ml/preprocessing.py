"""
Data cleaning, normalization, and feature derivation module.
Enforces robust deduplication, missing value imputation, non-positive amount clipping,
outlier clipping, timestamp derivation, and text casing/spelling normalization.
Every preprocessing step logs the exact number of rows modified.
"""

import json
import logging
import re
from datetime import datetime, timezone
from typing import Dict, List, Any, Tuple, Optional, Set
import numpy as np
import pandas as pd

from backend.app.ml.config import config

logger = logging.getLogger(__name__)


def normalize_category_string(category: Any) -> str:
    """Normalize fraud category: lowercase, spaces/hyphens/slashes to underscores."""
    if category is None or pd.isna(category) or not isinstance(category, str):
        return "other"
    cleaned = re.sub(r"[\s\-/]+", "_", str(category).strip().lower())
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    return cleaned or "other"


def normalize_channel_string(channel: Any) -> str:
    """Normalize payment/source channel to uppercase."""
    if channel is None or pd.isna(channel) or not isinstance(channel, str):
        return "other"
    cleaned = str(channel).strip().upper()
    return cleaned or "other"


def normalize_location_string(location: Any) -> str:
    """Normalize district/state names to Title Case."""
    if location is None or pd.isna(location) or not isinstance(location, str):
        return "Unknown"
    cleaned = str(location).strip().title()
    return cleaned or "Unknown"


def parse_timestamp_features(
    timestamp_val: Optional[Any],
) -> Tuple[datetime, int, int, int, int, bool]:
    """
    Parse timestamp into datetime and derive hour, weekday, is_night, and is_weekend.
    Falls back to current UTC datetime if null, invalid, or unparseable.

    Returns:
        Tuple of (datetime, hour, weekday, is_night, is_weekend, was_imputed_bool)
    """
    dt: Optional[datetime] = None
    was_imputed = False

    if timestamp_val is not None and not pd.isna(timestamp_val):
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
        was_imputed = True

    # Ensure timezone awareness
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    # Derive calendar features
    hour = int(dt.hour)
    weekday = int(dt.weekday())  # 0=Monday, 6=Sunday
    is_night = 1 if (hour >= 22 or hour < 6) else 0
    is_weekend = 1 if weekday in (5, 6) else 0

    return dt, hour, weekday, is_night, is_weekend, was_imputed


def clean_and_normalize_record(
    payload: Dict[str, Any],
    known_categories: Optional[Set[str]] = None,
    known_channels: Optional[Set[str]] = None,
) -> Tuple[Dict[str, Any], List[str]]:
    """
    Clean and normalize a single inference payload or record dictionary.
    Guarantees that all inference-time features (hour, weekday, is_night, is_weekend,
    log_amount, mule_hop_count, category, victim_state, victim_district, source_channel)
    are properly formatted without data leakage.

    Returns:
        Tuple of (normalized_record_dict, mapping_risk_notes_list)
    """
    categories_set = known_categories or set(config.KNOWN_CATEGORIES)
    channels_set = known_channels or set(config.KNOWN_CHANNELS)
    mapping_notes: List[str] = []

    # 1. Category normalization & out-of-vocabulary mapping
    raw_category = payload.get(config.PAYLOAD_CATEGORY) or payload.get("fraud_category") or "other"
    norm_category = normalize_category_string(raw_category)
    if norm_category not in categories_set:
        mapping_notes.append(
            f"Category mapped to 'other' (unseen category: '{raw_category}')"
        )
        norm_category = "other"

    # 2. Source Channel normalization & out-of-vocabulary mapping
    raw_channel = payload.get(config.PAYLOAD_SOURCE_CHANNEL) or payload.get("payment_channel") or "UPI"
    norm_channel = normalize_channel_string(raw_channel)
    if norm_channel not in channels_set:
        mapping_notes.append(
            f"Source channel mapped to 'other' (unseen channel: '{raw_channel}')"
        )
        norm_channel = "other"

    # 3. Location normalization
    raw_state = payload.get(config.PAYLOAD_VICTIM_STATE) or "Unknown"
    norm_state = normalize_location_string(raw_state)

    raw_district = payload.get(config.PAYLOAD_VICTIM_DISTRICT) or "Unknown"
    norm_district = normalize_location_string(raw_district)

    # 4. Amount parsing, non-positive clipping (<=0), and outlier clipping
    raw_amount = payload.get(config.PAYLOAD_REPORTED_AMOUNT) or payload.get("amount_lost") or config.MIN_POSITIVE_AMOUNT
    try:
        amount_float = float(raw_amount)
    except (ValueError, TypeError):
        amount_float = config.MIN_POSITIVE_AMOUNT

    # Clip invalid amounts (<= 0) to MIN_POSITIVE_AMOUNT
    amount_clipped = max(config.MIN_POSITIVE_AMOUNT, amount_float)
    # Clip extreme outliers to MAX_AMOUNT_LIMIT
    amount_clipped = min(config.MAX_AMOUNT_LIMIT, amount_clipped)
    log_amount = float(np.log1p(amount_clipped))

    # 5. Mule Hop Count derivation: len(mule_accounts)
    mule_accounts = payload.get(config.PAYLOAD_MULE_ACCOUNTS)
    if isinstance(mule_accounts, list):
        mule_hop_count = len(mule_accounts)
    elif isinstance(mule_accounts, str) and mule_accounts.strip().startswith("["):
        try:
            mule_hop_count = len(json.loads(mule_accounts))
        except Exception:
            mule_hop_count = 0
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
    dt, hour, weekday, is_night, is_weekend, _ = parse_timestamp_features(ts_val)

    normalized_record = {
        config.COL_REPORTED_AMOUNT: amount_clipped,
        config.COL_AMOUNT_LOG: log_amount,
        config.COL_CATEGORY: norm_category,
        config.COL_VICTIM_STATE: norm_state,
        config.COL_VICTIM_DISTRICT: norm_district,
        config.COL_SOURCE_CHANNEL: norm_channel,
        config.COL_MULE_HOP_COUNT: mule_hop_count,
        config.COL_INCIDENT_TIME: dt.isoformat(),
        config.COL_HOUR: hour,
        config.COL_WEEKDAY: weekday,
        config.COL_IS_NIGHT: is_night,
        config.COL_IS_WEEKEND: is_weekend,
    }

    # Pass through target and ID columns if present (for training datasets)
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
    Batch preprocessing pipeline for cybercrime complaint DataFrames.
    Executes and logs row modifications for:
    1. Duplicate removal
    2. Missing value imputation
    3. Invalid amounts (<= 0) clipping
    4. Outlier amount clipping
    5. Invalid timestamp imputation & temporal feature derivation
    6. Inconsistent text casing and spelling normalization
    """
    df = df.copy()
    categories_set = known_categories or set(config.KNOWN_CATEGORIES)
    channels_set = known_channels or set(config.KNOWN_CHANNELS)

    # --------------------------------------------------------------------------
    # Step 1: Duplicate Removal
    # --------------------------------------------------------------------------
    initial_rows = len(df)
    subset_cols = [config.COL_COMPLAINT_ID] if config.COL_COMPLAINT_ID in df.columns else None
    df_dedup = df.drop_duplicates(subset=subset_cols, keep="first").copy()
    n_duplicates = initial_rows - len(df_dedup)
    logger.info(
        f"[Preprocessing] Step 1 (Deduplication): Removed {n_duplicates} duplicate rows "
        f"({initial_rows} -> {len(df_dedup)})."
    )
    df = df_dedup

    # --------------------------------------------------------------------------
    # Step 2: Missing Values Imputation
    # --------------------------------------------------------------------------
    n_missing_rows = 0
    feature_cols_to_check = [
        config.COL_REPORTED_AMOUNT,
        config.COL_CATEGORY,
        config.COL_VICTIM_STATE,
        config.COL_VICTIM_DISTRICT,
        config.COL_SOURCE_CHANNEL,
    ]
    existing_check_cols = [col for col in feature_cols_to_check if col in df.columns]
    if existing_check_cols:
        n_missing_rows = int(df[existing_check_cols].isna().any(axis=1).sum())

    # Impute missing categoricals
    if config.COL_CATEGORY in df.columns:
        df[config.COL_CATEGORY] = df[config.COL_CATEGORY].fillna("other")
    if config.COL_VICTIM_STATE in df.columns:
        df[config.COL_VICTIM_STATE] = df[config.COL_VICTIM_STATE].fillna("Unknown")
    if config.COL_VICTIM_DISTRICT in df.columns:
        df[config.COL_VICTIM_DISTRICT] = df[config.COL_VICTIM_DISTRICT].fillna("Unknown")
    if config.COL_SOURCE_CHANNEL in df.columns:
        df[config.COL_SOURCE_CHANNEL] = df[config.COL_SOURCE_CHANNEL].fillna("other")

    # Impute missing hop count
    if config.COL_MULE_HOP_COUNT in df.columns:
        df[config.COL_MULE_HOP_COUNT] = pd.to_numeric(
            df[config.COL_MULE_HOP_COUNT], errors="coerce"
        ).fillna(0).astype(int)
    elif "mule_accounts" in df.columns:
        # Try parsing from JSON list
        derived_hops = []
        for val in df["mule_accounts"]:
            if isinstance(val, list):
                derived_hops.append(len(val))
            elif isinstance(val, str) and val.strip().startswith("["):
                try:
                    derived_hops.append(len(json.loads(val)))
                except Exception:
                    derived_hops.append(0)
            else:
                derived_hops.append(0)
        df[config.COL_MULE_HOP_COUNT] = derived_hops
    else:
        df[config.COL_MULE_HOP_COUNT] = 0

    logger.info(
        f"[Preprocessing] Step 2 (Missing Values): Imputed missing fields across {n_missing_rows} rows."
    )

    # --------------------------------------------------------------------------
    # Step 3: Invalid Amounts (<= 0) Handling (Clip, don't drop)
    # --------------------------------------------------------------------------
    amount_col = config.COL_REPORTED_AMOUNT
    if amount_col in df.columns:
        numeric_amounts = pd.to_numeric(df[amount_col], errors="coerce").fillna(config.MIN_POSITIVE_AMOUNT)
        n_non_positive = int((numeric_amounts <= 0.0).sum())
        # Clip values <= 0 to MIN_POSITIVE_AMOUNT
        df[amount_col] = numeric_amounts.clip(lower=config.MIN_POSITIVE_AMOUNT)
        logger.info(
            f"[Preprocessing] Step 3 (Invalid Amounts): Clipped {n_non_positive} non-positive amounts "
            f"(<=0) to minimum floor {config.MIN_POSITIVE_AMOUNT}."
        )
    else:
        df[amount_col] = config.MIN_POSITIVE_AMOUNT

    # --------------------------------------------------------------------------
    # Step 4: Outlier Amount Clipping (Clip, don't drop)
    # --------------------------------------------------------------------------
    n_outliers = int((df[amount_col] > config.MAX_AMOUNT_LIMIT).sum())
    df[amount_col] = df[amount_col].clip(upper=config.MAX_AMOUNT_LIMIT)
    df[config.COL_AMOUNT_LOG] = np.log1p(df[amount_col])
    logger.info(
        f"[Preprocessing] Step 4 (Outliers): Clipped {n_outliers} amount outliers exceeding "
        f"{config.MAX_AMOUNT_LIMIT}."
    )

    # --------------------------------------------------------------------------
    # Step 5: Invalid Timestamps & Feature Derivation
    # --------------------------------------------------------------------------
    ts_col = config.COL_INCIDENT_TIME
    hours = []
    weekdays = []
    is_nights = []
    is_weekends = []
    iso_timestamps = []
    n_invalid_timestamps = 0

    raw_timestamps = df[ts_col] if ts_col in df.columns else [None] * len(df)
    for raw_ts in raw_timestamps:
        dt, hour, weekday, is_night, is_weekend, was_imputed = parse_timestamp_features(raw_ts)
        if was_imputed:
            n_invalid_timestamps += 1
        hours.append(hour)
        weekdays.append(weekday)
        is_nights.append(is_night)
        is_weekends.append(is_weekend)
        iso_timestamps.append(dt.isoformat())

    df[config.COL_INCIDENT_TIME] = iso_timestamps
    df[config.COL_HOUR] = hours
    df[config.COL_WEEKDAY] = weekdays
    df[config.COL_IS_NIGHT] = is_nights
    df[config.COL_IS_WEEKEND] = is_weekends

    logger.info(
        f"[Preprocessing] Step 5 (Timestamps): Imputed {n_invalid_timestamps} invalid/missing timestamps; "
        f"derived hour, weekday, is_night, is_weekend."
    )

    # --------------------------------------------------------------------------
    # Step 6: Inconsistent Text Casing, Spelling & OOV Normalization
    # --------------------------------------------------------------------------
    n_category_normalized = 0
    n_channel_normalized = 0
    n_oov_categories = 0
    n_oov_channels = 0

    normalized_cats = []
    for val in df[config.COL_CATEGORY]:
        orig = str(val)
        norm = normalize_category_string(val)
        if norm != orig:
            n_category_normalized += 1
        if norm not in categories_set:
            n_oov_categories += 1
            norm = "other"
        normalized_cats.append(norm)
    df[config.COL_CATEGORY] = normalized_cats

    normalized_channels = []
    for val in df[config.COL_SOURCE_CHANNEL]:
        orig = str(val)
        norm = normalize_channel_string(val)
        if norm != orig:
            n_channel_normalized += 1
        if norm not in channels_set:
            n_oov_channels += 1
            norm = "other"
        normalized_channels.append(norm)
    df[config.COL_SOURCE_CHANNEL] = normalized_channels

    # State and District Title-Casing
    df[config.COL_VICTIM_STATE] = df[config.COL_VICTIM_STATE].apply(normalize_location_string)
    df[config.COL_VICTIM_DISTRICT] = df[config.COL_VICTIM_DISTRICT].apply(normalize_location_string)

    logger.info(
        f"[Preprocessing] Step 6 (Casing & Spelling): Normalized categories ({n_category_normalized} variants, "
        f"{n_oov_categories} mapped to 'other'), channels ({n_channel_normalized} variants, "
        f"{n_oov_channels} mapped to 'other'), states and districts."
    )

    return df
