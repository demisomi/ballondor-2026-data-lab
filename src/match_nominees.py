"""Match each nominee to exactly one row in the stats file, and save the mapping."""
import unicodedata
import pandas as pd

STATS_PATH = "data/raw/players_data-2025_2026.csv"
NOMINEES_PATH = "data/raw/nominees_2026.csv"
OUT_PATH = "data/interim/nominee_map.csv"

# Nominee name -> exact name in the stats file (spelling differences)
NAME_OVERRIDES = {
    "Fabián Ruiz": "Fabián Ruiz Peña",
    "Gabriel": "Gabriel Magalhães",
}

# Nominee name -> the club the stats file uses for them (namesake fixes)
SQUAD_OVERRIDES = {
    "Vitinha": "Paris Saint-Germain",
}

# Expected to be absent (leagues the file doesn't cover)
EXPECTED_ABSENT = {"Lionel Messi", "Sadio Mané", "Julián Quiñones"}

stats = pd.read_csv(STATS_PATH)
nominees = pd.read_csv(NOMINEES_PATH)


def normalise(name: str) -> str:
    text = unicodedata.normalize("NFKD", str(name))
    return "".join(c for c in text if not unicodedata.combining(c)).lower().strip()


stats["key"] = stats["Player"].map(normalise)

matched, problems = [], []
for _, nominee in nominees.iterrows():
    name = nominee["player_name"]
    rows = stats[stats["key"] == normalise(NAME_OVERRIDES.get(name, name))]

    # If we know which club the file uses, keep only that player's row
    if name in SQUAD_OVERRIDES:
        rows = rows[rows["Squad"] == SQUAD_OVERRIDES[name]]

    if rows.empty:
        if name not in EXPECTED_ABSENT:
            problems.append(f"{name}: no row found")
        continue
    if len(rows) > 1:
        problems.append(f"{name}: {len(rows)} rows ({', '.join(rows['Squad'])})")
        continue

    row = rows.iloc[0]
    matched.append({
        "nominee": name,
        "stats_player": row["Player"],
        "squad": row["Squad"],
        "comp": row["Comp"],
        "born": row["Born"],
        "minutes": row["Min"],
    })

if problems:
    raise SystemExit("Fix these before continuing:\n  " + "\n  ".join(problems))

result = pd.DataFrame(matched)
result.to_csv(OUT_PATH, index=False)
print(result.to_string(index=False))
print(f"\nMatched {len(result)} of {len(nominees)} nominees "
      f"({len(EXPECTED_ABSENT)} expected gaps). Saved to {OUT_PATH}")