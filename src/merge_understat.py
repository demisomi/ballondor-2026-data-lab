"""Attach Understat xG to each matched nominee, and flag suspicious matches."""
import json
import unicodedata
from pathlib import Path
import pandas as pd

MAP_PATH = "data/interim/nominee_map.csv"
OUT_PATH = "data/interim/understat_xg.csv"
RAW = Path("data/raw/understat")
SEASON = "2025"

# Kaggle's league label -> Understat's league name
COMP_TO_UNDERSTAT = {
    "eng Premier League": "EPL", "es La Liga": "La_liga",
    "de Bundesliga": "Bundesliga", "it Serie A": "Serie_A", "fr Ligue 1": "Ligue_1",
}
# Add entries here if a name differs between sources: nominee -> Understat spelling
NAME_OVERRIDES = {
    "Kylian Mbappé": "Kylian Mbappe-Lottin",
    "Willian Pacho": "William Pacho",
    "Dayot Upamecano": "Dayotchanculle Upamecano",
    "Fabián Ruiz": "Fabián",
}

NUMERIC = ["games", "time", "goals", "assists", "xG", "xA", "npxG", "shots", "key_passes"]


def normalise(name: str) -> str:
    text = unicodedata.normalize("NFKD", str(name))
    return "".join(c for c in text if not unicodedata.combining(c)).lower().strip()


frames = []
for league in COMP_TO_UNDERSTAT.values():
    df = pd.DataFrame(json.loads((RAW / f"{league}_{SEASON}_players.json").read_text("utf-8")))
    df["league"] = league
    frames.append(df)
us = pd.concat(frames, ignore_index=True)
for col in NUMERIC:
    us[col] = pd.to_numeric(us[col], errors="coerce")
us["key"] = us["player_name"].map(normalise)

mapping = pd.read_csv(MAP_PATH)
rows, problems = [], []
for _, m in mapping.iterrows():
    league = COMP_TO_UNDERSTAT[m["comp"]]
    wanted = {normalise(NAME_OVERRIDES.get(m["nominee"], m["nominee"])),
              normalise(m["stats_player"])}
    hits = us[(us["league"] == league) & (us["key"].isin(wanted))]

    if len(hits) != 1:
        problems.append(f"{m['nominee']}: {len(hits)} Understat matches in {league}")
        continue
    h = hits.iloc[0]
    gap = abs(h["time"] - m["minutes"]) / m["minutes"] * 100
    rows.append({
        "nominee": m["nominee"], "understat_team": h["team_title"],
        "xg_understat": h["xG"], "npxg_understat": h["npxG"], "xa_understat": h["xA"],
        "shots_understat": h["shots"], "key_passes_understat": h["key_passes"],
        "understat_minutes": h["time"], "kaggle_minutes": m["minutes"],
        "minutes_gap_pct": round(gap, 1),
        "check": "OK" if gap <= 5 else "CHECK MINUTES",
    })

result = pd.DataFrame(rows)
result.to_csv(OUT_PATH, index=False)
print(result.to_string(index=False))
print(f"\nMatched {len(result)} of {len(mapping)}. Saved to {OUT_PATH}")
if problems:
    print("\nNeeds attention:\n  " + "\n  ".join(problems))