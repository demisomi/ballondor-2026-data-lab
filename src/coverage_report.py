"""Show, for every nominee, which competition groups they have rows in.

Reads data/interim/player_competition_stats.csv (made by the validator).
Run:  python src/coverage_report.py
"""
import pandas as pd

NOMINEES = "data/raw/nominees_2026.csv"
STATS = "data/interim/player_competition_stats.csv"
GROUPS = ["league", "continental", "international", "domestic_cup"]

nominees = pd.read_csv(NOMINEES)
stats = pd.read_csv(STATS)

rows = stats.pivot_table(index="nominee", columns="competition_group",
                         values="competition", aggfunc="count", fill_value=0)
rows = rows.reindex(columns=GROUPS, fill_value=0)
minutes = stats.groupby("nominee")["minutes"].sum().rename("total_minutes")
cover = (nominees[["player_name", "club_as_listed", "national_team"]]
         .set_index("player_name").join(rows).join(minutes).fillna(0))
for c in GROUPS + ["total_minutes"]:
    cover[c] = cover[c].astype(int)

pd.set_option("display.width", 200)
print(cover.drop(columns="national_team").to_string())

print("\n--- Things to eyeball (a missing group is not always wrong) ---")
for g, why in [("league", "no league row"),
               ("continental", "no continental row (club not in Europe/continental cup, or minutes missing?)"),
               ("international", "no international row (nation missed the World Cup and qualifiers?)")]:
    names = list(cover.index[cover[g] == 0])
    print(f"{why}: {', '.join(names) if names else 'none'}")

print("\nContinental competitions found, with player counts:")
print(stats[stats["competition_group"] == "continental"]
      .groupby("competition")["nominee"].nunique().sort_values(ascending=False).to_string())