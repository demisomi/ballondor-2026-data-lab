"""Build league rows automatically, plus a blank template for hand-collected competitions."""
from pathlib import Path
import pandas as pd

STATS_PATH = "data/raw/players_data-2025_2026.csv"
NOMINEES_PATH = "data/raw/nominees_2026.csv"
MAP_PATH = "data/interim/nominee_map.csv"
LEAGUE_OUT = "data/interim/league_rows.csv"
MANUAL_OUT = Path("data/raw/manual_competition_stats.csv")

COLUMNS = ["nominee", "competition", "competition_group", "squad", "matches",
           "minutes", "goals", "assists", "yellow", "red",
           "source_url", "date_checked", "notes"]

stats = pd.read_csv(STATS_PATH)
nominees = pd.read_csv(NOMINEES_PATH)
mapping = pd.read_csv(MAP_PATH)

# 1. League rows from the Kaggle file (validate= stops us if a row matches twice)
merged = mapping.merge(
    stats, left_on=["stats_player", "squad", "born"],
    right_on=["Player", "Squad", "Born"], how="left", validate="one_to_one")

league = pd.DataFrame({
    "nominee": merged["nominee"],
    "competition": merged["Comp"],
    "competition_group": "league",
    "squad": merged["Squad"],
    "matches": merged["MP"],
    "minutes": merged["Min"],
    "goals": merged["Gls"],
    "assists": merged["Ast"],
    "yellow": merged["CrdY"],
    "red": merged["CrdR"],
    "source_url": "Kaggle: players_data-2025_2026.csv",
    "date_checked": pd.Timestamp.today().date().isoformat(),
    "notes": "",
})[COLUMNS]
league.to_csv(LEAGUE_OUT, index=False)
print(f"Wrote {len(league)} league rows to {LEAGUE_OUT}")

# 2. Blank templates, one file per stage (never overwrite work in progress)
MANUAL_DIR = Path("data/raw/manual")
MANUAL_DIR.mkdir(parents=True, exist_ok=True)

in_top5 = set(mapping["nominee"])
club = dict(zip(nominees["player_name"], nominees["club_as_listed"]))
national_of = dict(zip(nominees["player_name"], nominees["national_team"]))
squad_of = dict(zip(mapping["nominee"], mapping["squad"]))
comp_of = dict(zip(mapping["nominee"], mapping["comp"]))


def rows_for(names, competition, group, national=False):
    return [{"nominee": n, "competition": competition, "competition_group": group,
             "squad": national_of[n] if national else squad_of.get(n, club[n])}
            for n in names]


def write_stage(filename, rows):
    path = MANUAL_DIR / filename
    if path.exists():
        print(f"{path.name} already exists, leaving it alone.")
        return
    pd.DataFrame(rows).reindex(columns=COLUMNS).to_csv(path, index=False)
    print(f"Wrote {path.name} with {len(rows)} rows")


all_names = list(nominees["player_name"])
outside = [n for n in all_names if n not in in_top5]

write_stage("stage1_league_outside.csv",
            rows_for(outside, "RENAME: domestic league", "league"))
write_stage("stage2_continental.csv",
            rows_for(all_names, "CONFIRM: continental competition", "continental"))
write_stage("stage3_world_cup.csv",
            rows_for(all_names, "World Cup", "international", national=True))

# Domestic cups by country, inferred from each nominee's league (defaults to confirm)
CUPS_BY_LEAGUE = {
    "eng Premier League": ["FA Cup", "EFL Cup", "Community Shield"],
    "es La Liga": ["Copa del Rey", "Supercopa de España"],
    "de Bundesliga": ["DFB-Pokal", "DFL-Supercup"],
    "it Serie A": ["Coppa Italia", "Supercoppa Italiana"],
    "fr Ligue 1": ["Coupe de France", "Trophée des Champions"],
}
cup_rows = []
for name in all_names:
    for cup in CUPS_BY_LEAGUE.get(comp_of.get(name), ["CONFIRM: domestic cup"]):
        cup_rows += rows_for([name], cup, "domestic_cup")
write_stage("stage4_domestic_cups.csv", cup_rows)

# Stage 5: official national-team games other than the World Cup (qualifiers, AFCON...)
write_stage("stage5_national_other.csv",
            rows_for(all_names, "CONFIRM: national-team competition", "international",
                     national=True))