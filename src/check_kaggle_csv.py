"""Health check: is this CSV complete, and how many of our 30 nominees are in it?"""
import difflib
import unicodedata
import pandas as pd

STATS_PATH = "data/raw/players_data-2025_2026.csv"
NOMINEES_PATH = "data/raw/nominees_2026.csv"

stats = pd.read_csv(STATS_PATH)
nominees = pd.read_csv(NOMINEES_PATH)
print("Nominee file columns:", list(nominees.columns))


def normalise(name: str) -> str:
    """Lowercase and strip accents so 'Mbappé' matches 'Mbappe'."""
    text = unicodedata.normalize("NFKD", str(name))
    return "".join(c for c in text if not unicodedata.combining(c)).lower().strip()


# --- Check 1: Is the season complete? ---
# Most games played by any player on each team approximates the team's games played.
team_games = stats.groupby(["Comp", "Squad"])["MP"].max()
print("\nTeam games played, per league (full season = 38, or 34 for Bundesliga/Ligue 1):")
print(team_games.groupby("Comp").agg(["min", "median", "max"]))

# --- Check 2: Duplicate player rows (players who moved clubs mid-season) ---
dupes = stats[stats.duplicated("Player", keep=False)]
print("\nPlayers appearing more than once:", dupes["Player"].nunique())

# --- Check 3: How many nominees are in the file? ---
name_col = next(c for c in nominees.columns if "name" in c.lower() or "player" in c.lower())
print("Nominee name column used:", name_col)

lookup = {normalise(p): p for p in stats["Player"]}
found, missing = [], []
for raw_name in nominees[name_col]:
    key = normalise(raw_name)
    if key in lookup:
        found.append(raw_name)
    else:
        close = difflib.get_close_matches(key, lookup.keys(), n=2, cutoff=0.7)
        missing.append((raw_name, [lookup[c] for c in close]))

print(f"\nFound {len(found)} of {len(nominees)} nominees")
for name, suggestions in missing:
    print(" MISSING:", name, "| possible matches:", suggestions or "none")