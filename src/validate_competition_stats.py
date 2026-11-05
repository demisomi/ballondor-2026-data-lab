"""Phase 1, step 3: combine and validate every competition-stats table before
anything downstream reads it.

Reads data/interim/league_rows.csv (from build_competition_tables.py, Kaggle-
sourced) plus the five hand-filled data/raw/manual/stage*.csv files, checks
them, and writes the combined result to data/interim/player_competition_stats.csv.

Checks:
  - every nominee name matches data/raw/nominees_2026.csv exactly (catches a
    typo'd accent before it silently drops a player downstream)
  - no leftover "RENAME:" / "CONFIRM:" placeholder competition names (the
    blank templates build_competition_tables.py writes use these -- a row
    still carrying one means a stage file wasn't finished)
  - no duplicate (nominee, competition) row
  - minutes aren't impossible for the number of matches (reasonable cap:
    120 minutes/match, extra time allowed for knockout matches)
  - every row has a source_url and a date_checked
  - no negative counts

Run:  python src/validate_competition_stats.py
"""
import sys
from pathlib import Path

import pandas as pd

NOMINEES = "data/raw/nominees_2026.csv"
LEAGUE_ROWS = "data/interim/league_rows.csv"
MANUAL_DIR = Path("data/raw/manual")
STAGE_FILES = [
    "stage1_league_outside.csv",
    "stage2_continental.csv",
    "stage3_world_cup.csv",
    "stage4_domestic_cups.csv",
    "stage5_national_other.csv",
]
OUT = Path("data/interim/player_competition_stats.csv")

COLUMNS = ["nominee", "competition", "competition_group", "squad", "matches",
           "minutes", "goals", "assists", "yellow", "red",
           "source_url", "date_checked", "notes"]
COUNT_COLS = ["matches", "minutes", "goals", "assists", "yellow", "red"]
MINUTES_PER_MATCH_CAP = 120   # a knockout match can go to extra time, never more


def main():
    nominee_names = set(pd.read_csv(NOMINEES)["player_name"])

    frames = [pd.read_csv(LEAGUE_ROWS, dtype=str)]
    for name in STAGE_FILES:
        path = MANUAL_DIR / name
        if not path.exists():
            sys.exit(f"Missing {path} -- run build_competition_tables.py first.")
        frames.append(pd.read_csv(path, dtype=str))
    combined = pd.concat(frames, ignore_index=True).reindex(columns=COLUMNS)

    problems, notes = [], []

    unknown = sorted(set(combined["nominee"]) - nominee_names)
    if unknown:
        problems.append(f"unknown nominee name(s) not in {NOMINEES}: {', '.join(unknown)}")

    placeholder = combined[combined["competition"].str.startswith(("RENAME:", "CONFIRM:"), na=False)]
    for r in placeholder.itertuples():
        problems.append(f"{r.nominee}: placeholder competition name '{r.competition}' -- finish filling this row")

    dupes = combined[combined.duplicated(["nominee", "competition"], keep=False)]
    for (nominee, comp), g in dupes.groupby(["nominee", "competition"]):
        problems.append(f"duplicate row: {nominee} / {comp} ({len(g)} rows)")

    for col in COUNT_COLS:
        numeric = pd.to_numeric(combined[col], errors="coerce")
        bad_type = combined[col].notna() & numeric.isna()
        for r in combined[bad_type].itertuples():
            problems.append(f"{r.nominee} / {r.competition}: '{getattr(r, col)}' is not a number for {col}")

    matches = pd.to_numeric(combined["matches"], errors="coerce")
    minutes = pd.to_numeric(combined["minutes"], errors="coerce")
    impossible = minutes > matches * MINUTES_PER_MATCH_CAP
    for r in combined[impossible.fillna(False)].itertuples():
        problems.append(f"{r.nominee} / {r.competition}: {r.minutes} minutes in {r.matches} matches -- impossible")

    for col in COUNT_COLS:
        numeric = pd.to_numeric(combined[col], errors="coerce")
        negative = numeric < 0
        for r in combined[negative.fillna(False)].itertuples():
            problems.append(f"{r.nominee} / {r.competition}: negative {col}")

    missing_source = combined["source_url"].isna() | (combined["source_url"].str.strip() == "")
    for r in combined[missing_source].itertuples():
        problems.append(f"{r.nominee} / {r.competition}: missing source_url")
    missing_date = combined["date_checked"].isna() | (combined["date_checked"].str.strip() == "")
    for r in combined[missing_date].itertuples():
        notes.append(f"{r.nominee} / {r.competition}: missing date_checked")

    blank_rows = combined["matches"].isna() & combined["minutes"].isna()
    if blank_rows.any():
        notes.append(f"{blank_rows.sum()} row(s) have no matches/minutes filled in yet "
                      "(0 means checked and confirmed zero; blank means not filled in)")

    print(f"Combined {len(combined)} rows from {LEAGUE_ROWS} and {len(STAGE_FILES)} stage files.")
    for n in notes:
        print("  note:", n)
    if problems:
        print(f"\n{len(problems)} problem(s) found -- not writing {OUT}:")
        for p in problems:
            print(" -", p)
        sys.exit(1)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    combined.to_csv(OUT, index=False)
    print(f"\nAll checks passed. Saved {len(combined)} rows to {OUT}")


if __name__ == "__main__":
    main()
