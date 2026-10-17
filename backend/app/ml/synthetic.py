"""
Synthetic cybercrime complaint dataset generator for ML pipeline development and benchmarking.
Generates realistic, messy tabular data conforming to config.REQUIRED_DATASET_COLUMNS.
All district correlations and distributions are stylized heuristic ASSUMPTIONS, not real-world facts.

MANDATORY NOTICE:
SYNTHETIC DATA - NOT A REAL-WORLD PERFORMANCE CLAIM
No real citizen or police cybercrime data was used in constructing this generator.
"""

import argparse
import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Any, Optional
import numpy as np
import pandas as pd

from backend.app.ml.config import config

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------------------
# Geographic Catalog for Synthetic Victim Demographics
# ASSUMPTION: Synthetic victim locations are drawn from realistic state-district pairs.
# ------------------------------------------------------------------------------
STATE_DISTRICT_CATALOG: Dict[str, List[str]] = {
    "Delhi": ["South West Delhi", "Central Delhi", "North West Delhi", "New Delhi", "East Delhi"],
    "Haryana": ["Gurugram", "Faridabad", "Palwal", "Nuh", "Ambala", "Karnal", "Panipat"],
    "Maharashtra": ["Mumbai Suburban", "Pune", "Thane", "Nagpur", "Nashik", "Aurangabad"],
    "Karnataka": ["Bengaluru Urban", "Mysuru", "Hubballi-Dharwad", "Mangaluru", "Belagavi"],
    "Rajasthan": ["Jaipur", "Bharatpur", "Alwar", "Jodhpur", "Udaipur", "Kota", "Bikaner"],
    "Jharkhand": ["Jamtara", "Deoghar", "Giridih", "Ranchi", "Dhanbad", "Bokaro"],
    "Uttar Pradesh": ["Mathura", "Agra", "Lucknow", "Kanpur Nagar", "Noida", "Varanasi", "Ghaziabad"],
    "West Bengal": ["Kolkata", "Asansol", "Murshidabad", "North 24 Parganas", "Howrah"],
    "Gujarat": ["Ahmedabad", "Surat", "Vadodara", "Rajkot", "Gandhinagar"],
    "Telangana": ["Hyderabad", "Warangal", "Nizamabad", "Karimnagar"],
    "Bihar": ["Patna", "Gaya", "Nawada", "Nalanda", "Muzaffarpur", "Bhagalpur"],
    "Madhya Pradesh": ["Bhopal", "Indore", "Gwalior", "Jabalpur", "Ujjain"],
    "Tamil Nadu": ["Chennai", "Coimbatore", "Madurai", "Tiruchirappalli"],
    "Andhra Pradesh": ["Visakhapatnam", "Vijayawada", "Guntur", "Nellore"],
    "Chandigarh": ["Chandigarh"],
}

# ------------------------------------------------------------------------------
# Category Typologies & Messy Variant Mappings
# ASSUMPTION: API canonical types are augmented with task_scam, kyc_fraud, and other.
# ------------------------------------------------------------------------------
CANONICAL_CATEGORIES = [
    "phishing",
    "vishing",
    "investment_scam",
    "unauthorized_transfer",
    "task_scam",
    "kyc_fraud",
    "other",
]

MESSY_CATEGORY_VARIANTS = {
    "phishing": ["phishing", " UPI / QR Phishing ", "phishing_scam", "Phishing"],
    "vishing": ["vishing", "VISHING - Call Fraud", "vishing_call", "Vishing"],
    "investment_scam": ["investment_scam", "Investment / Crypto Scam", "investment scam", "Investment_Scam"],
    "unauthorized_transfer": ["unauthorized_transfer", "Unauthorized Transfer", "unauthorized_transfer_netbanking"],
    "task_scam": ["task_scam", "Part-Time Task Fraud", "Task_Scam", "part_time_task"],
    "kyc_fraud": ["kyc_fraud", "Credit Card / KYC Update", "kyc-update-fraud", "KYC_Fraud"],
    "other": ["other", "Online Marketplace Fraud", "unknown_modus", "Other"],
}

CANONICAL_CHANNELS = ["UPI", "IMPS", "NEFT", "ATM"]
MESSY_CHANNEL_VARIANTS = {
    "UPI": ["UPI", "upi", " UPI ", "Upi"],
    "IMPS": ["IMPS", "imps", " Imps "],
    "NEFT": ["NEFT", "neft", " NEFT "],
    "ATM": ["ATM", "atm", "Atm"],
}


def build_base_district_weights(districts: List[str]) -> np.ndarray:
    """
    Construct baseline sampling weights across the 38 registered districts.
    ASSUMPTION: Stylized distribution where the top district is < 20% and
    the top 6 together account for ~35-40%, with a long tail for rare classes.
    """
    n_districts = len(districts)
    weights = np.zeros(n_districts, dtype=float)

    # Top-6 anchor districts (~38% combined weight; top district ~9.5%)
    # ASSUMPTION: Stylized anchor hubs for benchmark variability
    top_6_anchors = {
        "Nuh": 0.085,
        "Jamtara": 0.075,
        "Bharatpur": 0.065,
        "Mumbai Suburban": 0.060,
        "South West Delhi": 0.050,
        "Mathura": 0.045,
    }

    # Moderate tier districts (~45% combined weight)
    moderate_anchors = {
        "Deoghar": 0.035,
        "Alwar": 0.035,
        "Bengaluru Urban": 0.035,
        "Kolkata": 0.030,
        "Gurugram": 0.030,
        "Jaipur": 0.030,
        "Hyderabad": 0.030,
        "Pune": 0.030,
        "Ahmedabad": 0.030,
        "Thane": 0.025,
        "Lucknow": 0.025,
        "Surat": 0.025,
        "Patna": 0.025,
        "Ranchi": 0.025,
    }

    # Long-tail districts (~18% combined weight, with rare ones having very low probability)
    tail_prob_pool = 0.18
    remaining_districts = [d for d in districts if d not in top_6_anchors and d not in moderate_anchors]
    n_tail = max(1, len(remaining_districts))

    # Skewed tail: earliest get ~0.015, tail-most get ~0.001 to guarantee < 5 occurrences for MIN_LOCATION_COUNT
    tail_weights = np.geomspace(0.018, 0.0008, num=n_tail)
    tail_weights = tail_weights * (tail_prob_pool / np.sum(tail_weights))

    for idx, d in enumerate(districts):
        if d in top_6_anchors:
            weights[idx] = top_6_anchors[d]
        elif d in moderate_anchors:
            weights[idx] = moderate_anchors[d]
        else:
            tail_idx = remaining_districts.index(d)
            weights[idx] = tail_weights[tail_idx]

    # Normalize baseline weights
    return weights / np.sum(weights)


def sample_withdrawal_district(
    districts: List[str],
    base_weights: np.ndarray,
    category: str,
    victim_state: str,
    mule_hop_count: int,
    time_progress_ratio: float,
    rng: np.random.RandomState,
) -> str:
    """
    Sample withdrawal district conditioned on category, victim state, mule hop count,
    noise injection (25-35%), and temporal drift over 18 months.
    ASSUMPTION: Conditional probability distributions represent synthetic modeling
    heuristics and not real-world cybercrime statistics.
    """
    # 25-35% random noise: draw from unconditioned baseline distribution
    noise_threshold = rng.uniform(0.25, 0.35)
    if rng.rand() < noise_threshold:
        return str(rng.choice(districts, p=base_weights))

    # Start with baseline weights
    adj_weights = base_weights.copy()

    # 1. Category-conditioned adjustments
    # ASSUMPTION: Heuristic shift where financial categories adjust relative district affinity
    if category in ["phishing", "task_scam"]:
        for d in ["Nuh", "Bharatpur", "Jamtara", "Alwar", "Palwal"]:
            if d in districts:
                adj_weights[districts.index(d)] *= 1.45
    elif category in ["investment_scam", "unauthorized_transfer"]:
        for d in ["Mumbai Suburban", "Bengaluru Urban", "South West Delhi", "Pune", "Hyderabad", "Thane"]:
            if d in districts:
                adj_weights[districts.index(d)] *= 1.45
    elif category in ["vishing", "kyc_fraud"]:
        for d in ["Jamtara", "Deoghar", "Giridih", "Mathura", "Agra"]:
            if d in districts:
                adj_weights[districts.index(d)] *= 1.45

    # 2. State & Hop conditioning
    # ASSUMPTION: Lower hops have higher local state bias; higher hops disperse into interstate metros
    for idx, d in enumerate(districts):
        dist_state = config.DISTRICT_COORDINATES[d]["state"]
        if mule_hop_count <= 1 and dist_state == victim_state:
            adj_weights[idx] *= 1.40
        elif mule_hop_count >= 3 and d in ["South West Delhi", "Mumbai Suburban", "Kolkata", "Bengaluru Urban"]:
            adj_weights[idx] *= 1.30

    # 3. 18-Month Temporal Drift
    # ASSUMPTION: Earlier records skew towards early clusters; later records drift slightly toward urban suburbs
    drift = time_progress_ratio  # 0.0 at start, 1.0 at 18 months
    for d in ["Jamtara", "Deoghar"]:
        if d in districts:
            adj_weights[districts.index(d)] *= (1.15 - 0.30 * drift)
    for d in ["Nuh", "Gurugram", "Pune", "Thane"]:
        if d in districts:
            adj_weights[districts.index(d)] *= (0.85 + 0.30 * drift)

    # Normalize conditioned probabilities
    probs = adj_weights / np.sum(adj_weights)
    return str(rng.choice(districts, p=probs))


def generate_synthetic_complaints(num_rows: int = 5000, seed: int = 42) -> pd.DataFrame:
    """
    Generate synthetic cybercrime complaint dataset conforming strictly to
    config.REQUIRED_DATASET_COLUMNS, with controlled messiness, noise, and drift.

    Args:
        num_rows: Target record count.
        seed: Random seed for deterministic generation.

    Returns:
        pd.DataFrame containing synthetic complaint records.
    """
    rng = np.random.RandomState(seed)
    districts = sorted(list(config.DISTRICT_COORDINATES.keys()))
    base_weights = build_base_district_weights(districts)

    # Incident time spanning ~18 months (~540 days)
    start_time = datetime(2025, 5, 1, 0, 0, 0, tzinfo=timezone.utc)
    total_span_days = 540.0

    states = list(STATE_DISTRICT_CATALOG.keys())
    records: List[Dict[str, Any]] = []

    # Reserve ~2% for exact duplicates
    n_unique = int(round(num_rows * 0.98))

    for i in range(n_unique):
        complaint_id = f"SYN-2026-{100000 + i}"

        # 1. Incident Timestamp & Drift Ratio
        day_offset = float(rng.uniform(0, total_span_days))
        sec_offset = int(rng.randint(0, 86400))
        incident_dt = start_time + timedelta(days=day_offset, seconds=sec_offset)
        time_ratio = day_offset / total_span_days

        # 2. Modus Operandi Category
        # ASSUMPTION: Relative frequency distribution across synthetic complaint typologies
        cat_weights = [0.26, 0.20, 0.16, 0.14, 0.12, 0.08, 0.04]
        canonical_cat = str(rng.choice(CANONICAL_CATEGORIES, p=cat_weights))

        # 3. Source Transfer Channel
        channel_weights = [0.60, 0.22, 0.12, 0.06]
        canonical_channel = str(rng.choice(CANONICAL_CHANNELS, p=channel_weights))

        # 4. Mule Hop Count & Mule Accounts
        # ASSUMPTION: Most cybercrime complaints report 1 or 2 hops before cashout
        hop_weights = [0.10, 0.45, 0.30, 0.10, 0.05]
        mule_hop_count = int(rng.choice([0, 1, 2, 3, 4], p=hop_weights))
        mule_accounts = [f"MULE-XXXX{rng.randint(1000, 9999)}" for _ in range(mule_hop_count)]

        # 5. Victim Jurisdiction
        victim_state = str(rng.choice(states))
        district_pool = STATE_DISTRICT_CATALOG.get(victim_state, ["Unknown District"])
        victim_district = str(rng.choice(district_pool))

        # 6. Financial Loss Amount
        # ASSUMPTION: Financial loss approximates a log-normal distribution conditioned on fraud category
        if canonical_cat in ["investment_scam"]:
            raw_amount = float(np.exp(rng.normal(12.2, 0.75)))  # INR ~100k - ~1M
        elif canonical_cat in ["task_scam", "kyc_fraud"]:
            raw_amount = float(np.exp(rng.normal(10.8, 0.65)))  # INR ~30k - ~150k
        else:
            raw_amount = float(np.exp(rng.normal(9.5, 0.70)))   # INR ~5k - ~40k
        reported_amount = float(round(raw_amount, 2))

        # 7. Ground Truth Withdrawal District (STRICTLY UNCORRUPTED)
        withdrawal_district = sample_withdrawal_district(
            districts=districts,
            base_weights=base_weights,
            category=canonical_cat,
            victim_state=victim_state,
            mule_hop_count=mule_hop_count,
            time_progress_ratio=time_ratio,
            rng=rng,
        )

        # ----------------------------------------------------------------------
        # Controlled Messiness Injection
        # ----------------------------------------------------------------------
        # Casing & spacing variants in category (~15% of records)
        if rng.rand() < 0.15:
            cat_val = str(rng.choice(MESSY_CATEGORY_VARIANTS[canonical_cat]))
        else:
            cat_val = canonical_cat

        # Casing & spacing variants in channel (~12% of records)
        if rng.rand() < 0.12:
            channel_val = str(rng.choice(MESSY_CHANNEL_VARIANTS[canonical_channel]))
        else:
            channel_val = canonical_channel

        # Casing variants in victim_state (~8% of records)
        if rng.rand() < 0.08:
            state_val = victim_state.upper() if rng.rand() < 0.5 else victim_state.lower()
        else:
            state_val = victim_state

        dist_val = victim_district

        # ~3% Missing values in non-target fields (never in withdrawal_district)
        if rng.rand() < 0.03:
            messy_target = rng.choice(["victim_district", "source_channel", "category"])
            if messy_target == "victim_district":
                dist_val = None
            elif messy_target == "source_channel":
                channel_val = None
            elif messy_target == "category":
                cat_val = None

        # ~1% Non-positive amounts to exercise preprocessing clipping
        if rng.rand() < 0.01:
            reported_amount = -100.0 if rng.rand() < 0.5 else 0.0

        records.append({
            "complaint_id": complaint_id,
            "incident_time": incident_dt.isoformat(),
            "reported_amount": reported_amount,
            "category": cat_val,
            "victim_state": state_val,
            "victim_district": dist_val,
            "source_channel": channel_val,
            "mule_hop_count": mule_hop_count,
            "withdrawal_district": withdrawal_district,  # STRICTLY VALID & UNCORRUPTED
            "data_source": "SYNTHETIC",
            "mule_accounts": json.dumps(mule_accounts),
        })

    # --------------------------------------------------------------------------
    # Re-inject ~2% exact duplicates (same complaint_id and all attributes)
    # --------------------------------------------------------------------------
    n_dups = num_rows - n_unique
    if n_dups > 0 and records:
        dup_indices = rng.choice(len(records), size=n_dups, replace=True)
        for idx in dup_indices:
            records.append(dict(records[idx]))

    # Deterministic chronological sort by incident timestamp
    df = pd.DataFrame(records)
    df["_dt"] = pd.to_datetime(df["incident_time"], errors="coerce")
    df = df.sort_values("_dt").drop(columns=["_dt"]).reset_index(drop=True)

    return df


def main(argv: Optional[List[str]] = None) -> int:
    """CLI entry point for synthetic dataset generation."""
    parser = argparse.ArgumentParser(
        description="Generate synthetic cybercrime complaints dataset for ML training & testing."
    )
    parser.add_argument(
        "--rows",
        type=int,
        default=5000,
        help="Number of complaint records to generate (default: 5000)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for deterministic generation (default: 42)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=str(config.DATA_RAW_DIR / "SYNTHETIC_DEVELOPMENT_ONLY_complaints.csv"),
        help="Destination path for generated CSV file",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite destination file if it already exists",
    )

    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    out_path = Path(args.output).resolve()

    if out_path.exists() and not args.force:
        logger.error(
            f"Destination file '{out_path}' already exists. Pass --force to overwrite."
        )
        return 1

    logger.info(
        f"[{config.SYNTHETIC_DATA_DISCLAIMER}] Generating {args.rows} synthetic records (seed={args.seed})..."
    )

    df = generate_synthetic_complaints(num_rows=args.rows, seed=args.seed)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False)

    logger.info(
        f"[{config.SYNTHETIC_DATA_DISCLAIMER}] Successfully wrote {len(df)} records to {out_path}"
    )
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
