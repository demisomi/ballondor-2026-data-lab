"""Phase 1, step 2: sum the hand-saved FBref match-log pages into one detail
row per (nominee, competition).

FBref blocks scripted downloads (403), so each nominee's match-log page was
saved by hand as data/raw/matchlogs/<slug>_2025.html and <slug>_2026.html
(one page per football season; a few nominees only have one page because
their second season wasn't saved -- see the "FILES FOUND" line it prints).
This script never downloads anything itself.

What it does, per nominee:
  1. Reads both saved pages (if both exist) and takes the match-log table.
  2. Drops repeated header rows, the season-total footer row, and rows for
     matches the player was an unused substitute in ("On matchday squad,
     but did not play" -- zero minutes, not a real appearance).
  3. Keeps only matches inside the official window (config.WINDOW_START to
     config.WINDOW_END) and drops friendlies.
  4. Renames each competition to its canonical name and tags it with a
     competition_group (league / continental / domestic_cup / international)
     using the LABELS table below. A label not in that table is printed as
     "UNMAPPED" and skipped -- extend LABELS rather than silently guessing.
  5. Sums matches, minutes and every counting stat across the two seasons,
     per (nominee, competition), and writes one row per group to
     data/interim/matchlog_detail.csv.

This file is detail, not the final competition table: build_competition_tables.py
and the hand-verified data/raw/manual/*.csv stage files are what scoring reads
for matches/minutes/goals/assists. This script's output instead feeds the
*extra* per-match stats (shots, defensive actions, cards) in
build_player_features.py, so it keeps every classified competition rather
than only the ones judged worth a title or a league position.

Run:  python src/build_from_matchlogs.py
"""
import sys
import unicodedata
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import WINDOW_START, WINDOW_END  # noqa: E402

NOMINEES = "data/raw/nominees_2026.csv"
MATCHLOG_DIR = Path("data/raw/matchlogs")
OUT = Path("data/interim/matchlog_detail.csv")
TABLE_ID = "matchlogs_all"

# FBref label -> (canonical name written to the output, competition_group).
# A label that isn't here is reported as unmapped and dropped -- add it here
# instead of guessing, so every row in the output was a deliberate choice.
LABELS = {
    # leagues
    "Premier League": ("Premier League", "league"),
    "La Liga": ("La Liga", "league"),
    "Serie A": ("Serie A", "league"),
    "Bundesliga": ("Bundesliga", "league"),
    "Ligue 1": ("Ligue 1", "league"),
    "Pro League": ("Saudi Pro League", "league"),
    "MLS": ("MLS", "league"),
    # continental club competitions
    "Champions Lg": ("Champions Lg", "continental"),
    "CCC": ("CCC", "continental"),
    "Leagues Cup": ("Leagues Cup", "continental"),
    "Super Cup": ("UEFA Super Cup", "continental"),
    "Club World Cup": ("Club World Cup", "continental"),
    # domestic cups and super cups
    "FA Cup": ("FA Cup", "domestic_cup"),
    "EFL Cup": ("EFL Cup", "domestic_cup"),
    "Copa del Rey": ("Copa del Rey", "domestic_cup"),
    "Supercopa de España": ("Supercopa de España", "domestic_cup"),
    "DFB-Pokal": ("DFB-Pokal", "domestic_cup"),
    "DFL-Supercup": ("DFL-Supercup", "domestic_cup"),
    "Coppa Italia": ("Coppa Italia", "domestic_cup"),
    "Supercoppa": ("Supercoppa Italiana", "domestic_cup"),
    "Coupe de France": ("Coupe de France", "domestic_cup"),
    "Trophée des Champions": ("Trophée des Champions", "domestic_cup"),
    "FA Community Shield": ("FA Community Shield", "domestic_cup"),
    # international
    "World Cup": ("World Cup", "international"),
    "WCQ": ("WCQ", "international"),
    "Africa Cup of Nations": ("Africa Cup of Nations", "international"),
    "AFCON qual.": ("AFCON qual.", "international"),
    "UEFA Nations League": ("UEFA Nations League", "international"),
    "Gold Cup": ("Gold Cup", "international"),
}
# Labels classified here on purpose and always dropped (not a competitive match).
EXCLUDE = {"Friendlies (M)", "Friendlies (W)"}

EXTRA_COLS = ["PK", "PKatt", "Sh", "SoT", "Fls", "Fld", "Off", "Crs",
              "TklW", "Int", "OG", "PKwon", "PKcon"]
SUM_COLS = ["matches", "minutes"] + EXTRA_COLS


def _norm(s: str) -> str:
    """Normalise accents so 'í' (precomposed) and 'í' (decomposed) compare equal."""
    return unicodedata.normalize("NFC", s)


def _find_pages(slug: str) -> list[Path]:
    """Match <slug>_2025.html / <slug>_2026.html regardless of how the
    filename's accents are encoded on disk."""
    wanted = {_norm(f"{slug}_2025.html"), _norm(f"{slug}_2026.html")}
    found = []
    for p in sorted(MATCHLOG_DIR.glob("*.html")):
        if _norm(p.name) in wanted:
            found.append(p)
    return found


def _read_matchlog(path: Path) -> pd.DataFrame:
    t = pd.read_html(path, attrs={"id": TABLE_ID})[0]
    t.columns = [c[-1] if isinstance(c, tuple) else c for c in t.columns]
    # drop repeated header rows (FBref reprints the header mid-table on long seasons)
    t = t[t["Date"] != "Date"]
    # drop the season-total footer row (it has no real Date)
    t["Date"] = pd.to_datetime(t["Date"], errors="coerce")
    t = t[t["Date"].notna()]
    # drop unused-substitute rows: in the squad, but zero minutes played
    t = t[t["Min"] != "On matchday squad, but did not play"]
    t["Min"] = pd.to_numeric(t["Min"], errors="coerce").fillna(0)
    return t


def main():
    nominees = pd.read_csv(NOMINEES)["player_name"].tolist()
    window_start, window_end = pd.Timestamp(WINDOW_START), pd.Timestamp(WINDOW_END)
    unmapped = set()
    rows = []

    for nominee in nominees:
        slug = nominee.lower().replace(" ", "_")
        pages = _find_pages(slug)
        if not pages:
            print(f"NO MATCH-LOG PAGES FOUND for {nominee} (slug: {slug})")
            continue
        if len(pages) == 1:
            print(f"only one saved page for {nominee}: {pages[0].name}")

        frames = [_read_matchlog(p) for p in pages]
        t = pd.concat(frames, ignore_index=True)
        # National-team competitions (WCQ, World Cup, ...) are cumulative on FBref's
        # club pages, so the same international fixture can appear on BOTH saved
        # pages when a player's two seasons overlap in calendar time. Keep one row
        # per real match rather than double-counting it.
        t = t.drop_duplicates(subset=["Date", "Comp", "Squad", "Opponent"])
        t = t[(t["Date"] >= window_start) & (t["Date"] <= window_end)]

        for col in EXTRA_COLS:
            if col not in t.columns:
                t[col] = 0
        t[EXTRA_COLS] = t[EXTRA_COLS].apply(pd.to_numeric, errors="coerce")

        for raw_comp, g in t.groupby("Comp"):
            if raw_comp in EXCLUDE:
                continue
            if raw_comp not in LABELS:
                unmapped.add(raw_comp)
                continue
            comp, group = LABELS[raw_comp]
            row = {"nominee": nominee, "Comp": comp, "group": group,
                   "matches": len(g), "minutes": g["Min"].sum()}
            for col in EXTRA_COLS:
                row[col] = g[col].sum(min_count=1)
            rows.append(row)

    out = pd.DataFrame(rows, columns=["nominee", "Comp", "group"] + SUM_COLS)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT, index=False)
    print(f"\nSaved {len(out)} rows to {OUT}")

    if unmapped:
        print("\nUNMAPPED competition labels (add these to LABELS and rerun):")
        for u in sorted(unmapped):
            print(" -", u)
    else:
        print("\nNo unmapped competition labels.")

    # cross-check league minutes against the Kaggle CSV, where both exist
    kaggle_path = Path("data/raw/players_data-2025_2026.csv")
    if kaggle_path.exists():
        kag = pd.read_csv(kaggle_path)
        name_col = next((c for c in ("Player", "player_name", "name") if c in kag.columns), None)
        min_col = next((c for c in ("Min", "minutes", "Minutes") if c in kag.columns), None)
        if name_col and min_col:
            league_minutes = out[out["group"] == "league"].groupby("nominee")["minutes"].sum()
            kag_minutes = kag.groupby(name_col)[min_col].sum()
            print("\nLeague-minutes cross-check against the Kaggle CSV (where both have the player):")
            for nominee, mins in league_minutes.items():
                if nominee in kag_minutes.index:
                    diff = mins - kag_minutes[nominee]
                    flag = "  <-- check this" if abs(diff) > 90 else ""
                    print(f"  {nominee}: matchlogs={mins:.0f}  kaggle={kag_minutes[nominee]:.0f}  diff={diff:+.0f}{flag}")


if __name__ == "__main__":
    main()
