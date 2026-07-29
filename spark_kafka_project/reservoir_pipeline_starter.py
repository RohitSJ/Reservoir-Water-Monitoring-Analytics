
"""
Reservoir Data Pipeline Starter
CSV -> profiling -> merge -> cleaning -> master table -> daily fact table -> exports

Input expected:
data/raw/2022_Reservoir_Data.csv
data/raw/2023_Reservoir_Data.csv
data/raw/2024 Data of Reservoir Level of Central Water Commission (CWC).csv
data/raw/2025 Data of Reservoir Level of Central Water Commission (CWC).csv.csv
"""

from __future__ import annotations

import os
from pathlib import Path
import json
import pandas as pd
import numpy as np

# -----------------------------
# 0) Paths
# -----------------------------
BASE_DIR = Path(__file__).resolve().parent
RAW_DIR = BASE_DIR / "data" / "raw"
OUT_DIR = BASE_DIR / "data" / "processed"
PROFILE_DIR = OUT_DIR / "profiles"
MERGED_DIR = OUT_DIR / "merged"
CLEAN_DIR = OUT_DIR / "clean"
MASTER_DIR = OUT_DIR / "master"
FACT_DIR = OUT_DIR / "fact"
EXPORT_DIR = BASE_DIR / "exports"

for d in [PROFILE_DIR, MERGED_DIR, CLEAN_DIR, MASTER_DIR, FACT_DIR, EXPORT_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# -----------------------------
# 1) File registry
# -----------------------------
FILES = {
    2022: RAW_DIR / "2022_Reservoir_Data.csv",
    2023: RAW_DIR / "2023_Reservoir_Data.csv",
    2024: RAW_DIR / "2024 Data of Reservoir Level of Central Water Commission (CWC).csv",
    2025: RAW_DIR / "2025 Data of Reservoir Level of Central Water Commission (CWC).csv.csv",
}

EXPECTED_COLS = [
    "Reservoir_name", "Basin", "subbasin", "Agency_name", "Lat", "Long",
    "Date", "Year", "Month", "Full_reservoir_level",
    "Live_capacity_FRL", "Storage", "Level"
]

# -----------------------------
# 2) Helpers
# -----------------------------
def read_year_file(path: Path, year: int) -> pd.DataFrame:
    df = pd.read_csv(path)
    # Standardize columns if needed
    df.columns = [c.strip() for c in df.columns]
    missing = [c for c in EXPECTED_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"{path.name} missing columns: {missing}")
    df["source_year"] = year
    return df

def clean_reservoir_name(s: pd.Series) -> pd.Series:
    return (
        s.astype(str)
         .str.strip()
         .str.replace(r"\s+", " ", regex=True)
    )

def profile_frame(df: pd.DataFrame, year_label: str = "all") -> dict:
    out = {}
    out["year_label"] = year_label
    out["rows"] = int(len(df))
    out["reservoir_count"] = int(df["Reservoir_name"].nunique(dropna=True))
    out["date_min"] = str(pd.to_datetime(df["Date"], errors="coerce").min().date())
    out["date_max"] = str(pd.to_datetime(df["Date"], errors="coerce").max().date())
    out["duplicate_reservoir_date_rows"] = int(df.duplicated(["Reservoir_name", "Date"]).sum())

    missing_pct = (df.isna().sum() / len(df) * 100).round(2).to_dict()
    out["missing_pct_by_column"] = missing_pct

    return out

def overlap_across_years(df_all: pd.DataFrame) -> pd.DataFrame:
    sets = (
        df_all.dropna(subset=["Reservoir_name"])
             .groupby("source_year")["Reservoir_name"]
             .apply(lambda s: set(s.astype(str).str.strip()))
    )

    years = sorted(sets.index.tolist())
    rows = []
    for i, y1 in enumerate(years):
        for y2 in years[i+1:]:
            inter = sets[y1].intersection(sets[y2])
            rows.append({
                "year_a": y1,
                "year_b": y2,
                "common_reservoirs": len(inter),
                "pct_of_year_a": round(len(inter) / len(sets[y1]) * 100, 2) if len(sets[y1]) else None,
                "pct_of_year_b": round(len(inter) / len(sets[y2]) * 100, 2) if len(sets[y2]) else None,
            })
    return pd.DataFrame(rows)

# -----------------------------
# 3) Step 1: Data profiling
# -----------------------------
def run_profiling() -> tuple[dict, pd.DataFrame]:
    yearly_frames = []
    profile_rows = []

    for year, path in FILES.items():
        df = read_year_file(path, year)
        yearly_frames.append(df)
        prof = profile_frame(df, str(year))
        profile_rows.append(prof)

    df_all_raw = pd.concat(yearly_frames, ignore_index=True)
    prof_all = profile_frame(df_all_raw, "all_years")

    # Save profile summary
    profile_summary = pd.DataFrame(profile_rows)
    profile_summary.to_csv(PROFILE_DIR / "yearly_profile_summary.csv", index=False)

    # Save missing percentage detail
    missing_detail = pd.DataFrame([
        {"scope": "all_years", **prof_all["missing_pct_by_column"]}
    ])
    missing_detail.to_csv(PROFILE_DIR / "missing_percentage_all_years.csv", index=False)

    # Save overlap report
    overlap_df = overlap_across_years(df_all_raw)
    overlap_df.to_csv(PROFILE_DIR / "reservoir_overlap_across_years.csv", index=False)

    # Save a JSON report too
    report = {
        "yearly": profile_rows,
        "all_years": prof_all,
    }
    with open(PROFILE_DIR / "profile_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    return report, overlap_df

# -----------------------------
# 4) Step 2: Merge all years
# -----------------------------
def merge_all_years() -> pd.DataFrame:
    frames = []
    for year, path in FILES.items():
        df = read_year_file(path, year)
        frames.append(df)

    merged = pd.concat(frames, ignore_index=True)
    merged.to_csv(MERGED_DIR / "reservoir_all_years_merged_raw.csv", index=False)
    return merged

# -----------------------------
# 5) Step 3: Standardize and clean
# -----------------------------
def clean_data(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # Parse date
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")

    # Clean reservoir names
    df["Reservoir_name"] = clean_reservoir_name(df["Reservoir_name"])

    # Remove subbasin (fully missing in your dataset)
    if "subbasin" in df.columns:
        df = df.drop(columns=["subbasin"])

    # Standardize text columns
    for col in ["Basin", "Agency_name"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip().replace({"nan": np.nan})

    # Sort
    df = df.sort_values(["Reservoir_name", "Date", "source_year"], kind="mergesort")

    # Drop exact duplicates based on reservoir-date
    # Keep the row with more non-null values
    df["_nonnull_count"] = df.notna().sum(axis=1)
    df = (
        df.sort_values(["Reservoir_name", "Date", "_nonnull_count"], ascending=[True, True, False], kind="mergesort")
          .drop_duplicates(subset=["Reservoir_name", "Date"], keep="first")
          .drop(columns=["_nonnull_count"])
    )

    # Optional: create date parts
    df["Year"] = df["Date"].dt.year
    df["Month"] = df["Date"].dt.month
    df["Day"] = df["Date"].dt.day

    # Reorder columns
    front = ["Reservoir_name", "Date", "Year", "Month", "Day", "source_year"]
    remaining = [c for c in df.columns if c not in front]
    df = df[front + remaining]

    df.to_csv(CLEAN_DIR / "reservoir_cleaned_daily.csv", index=False)
    return df

# -----------------------------
# 6) Step 4: Create master table
# -----------------------------
def create_master_table(df_clean: pd.DataFrame) -> pd.DataFrame:
    # Stable columns: use first non-null record per reservoir
    stable_cols = ["Reservoir_name", "Basin", "Agency_name", "Lat", "Long",
                   "Full_reservoir_level", "Live_capacity_FRL"]
    master = (
        df_clean[stable_cols]
        .sort_values("Reservoir_name")
        .groupby("Reservoir_name", as_index=False)
        .agg({
            "Basin": "first",
            "Agency_name": "first",
            "Lat": "first",
            "Long": "first",
            "Full_reservoir_level": "first",
            "Live_capacity_FRL": "first",
        })
    )

    master.to_csv(MASTER_DIR / "reservoir_master.csv", index=False)
    return master

# -----------------------------
# 7) Step 5: Create daily fact table
# -----------------------------
def create_fact_table(df_clean: pd.DataFrame) -> pd.DataFrame:
    fact_cols = [
        "Reservoir_name", "Date", "Year", "Month", "Day", "source_year",
        "Storage", "Level"
    ]
    fact = df_clean[fact_cols].copy()

    # Optional: sort for time series usage
    fact = fact.sort_values(["Reservoir_name", "Date"], kind="mergesort")

    fact.to_csv(FACT_DIR / "reservoir_daily_fact.csv", index=False)
    return fact

# -----------------------------
# 8) Step 6: Export cleaned files
# -----------------------------
def export_files(df_clean: pd.DataFrame, master: pd.DataFrame, fact: pd.DataFrame) -> None:
    # CSV backups
    df_clean.to_csv(EXPORT_DIR / "reservoir_cleaned_daily.csv", index=False)
    master.to_csv(EXPORT_DIR / "reservoir_master.csv", index=False)
    fact.to_csv(EXPORT_DIR / "reservoir_daily_fact.csv", index=False)

    # Parquet for Spark/Hive
    # Requires pyarrow or fastparquet
    df_clean.to_parquet(EXPORT_DIR / "reservoir_cleaned_daily.parquet", index=False)
    master.to_parquet(EXPORT_DIR / "reservoir_master.parquet", index=False)
    fact.to_parquet(EXPORT_DIR / "reservoir_daily_fact.parquet", index=False)

# -----------------------------
# Main
# -----------------------------
if __name__ == "__main__":
    report, overlap_df = run_profiling()
    merged = merge_all_years()
    cleaned = clean_data(merged)
    master = create_master_table(cleaned)
    fact = create_fact_table(cleaned)
    export_files(cleaned, master, fact)

    print("Done.")
    print("Profiles saved to:", PROFILE_DIR)
    print("Merged raw saved to:", MERGED_DIR)
    print("Cleaned data saved to:", CLEAN_DIR)
    print("Master table saved to:", MASTER_DIR)
    print("Fact table saved to:", FACT_DIR)
    print("Exports saved to:", EXPORT_DIR)
