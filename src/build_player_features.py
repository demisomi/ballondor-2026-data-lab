"""Phase 2, step 1: one row per nominee with per-90 numbers and team context.

Reads the validated Phase 1 files and writes data/processed/player_features.csv.
Nothing is scored here; this only prepares clean, comparable numbers.
Run:  python src/build_player_features.py
"""
from pathlib import Path
import numpy as np
import pandas as pd

NOMINEES = "data/raw/nominees_2026.csv"
STATS = "data/interim/player_competition_stats.csv"
UNDERSTAT = "data/interim/understat_xg.csv"
DETAIL = "data/interim/matchlog_detail.csv"
RESULTS = "data/raw/manual/team_results.csv"
TROPHIES = "data/raw/manual/team_trophies.csv"
OUT = Path("data/processed/player_features.csv")
GROUPS = ["league", "continental", "international", "domestic_cup"]
MIN_MINUTES = 900     # below this, per-90 numbers are too noisy to trust (about 10 full matches)


def per90(count, minutes):
    return np.where(minutes > 0, count / minutes * 90, np.nan)


nom = pd.read_csv(NOMINEES)
stats = pd.read_csv(STATS)
us = pd.read_csv(UNDERSTAT)
detail = pd.read_csv(DETAIL)
res = pd.read_csv(RESULTS, dtype=str)
tro = pd.read_csv(TROPHIES, dtype=str)

# 1. totals and group splits from the validated competition table
tot = stats.groupby("nominee")[["matches", "minutes", "goals", "assists", "yellow", "red"]].sum(min_count=1)
tot.columns = [f"{c}_total" for c in tot.columns]
split = stats.pivot_table(index="nominee", columns="competition_group",
                          values=["minutes", "goals", "assists"], aggfunc="sum", fill_value=0)
split.columns = [f"{a}_{g}" for a, g in split.columns]
for g in GROUPS:                       # make sure every column exists
    for a in ("minutes", "goals", "assists"):
        split[f"{a}_{g}"] = split.get(f"{a}_{g}", 0)

f = nom.set_index("player_name")[["club_as_listed", "national_team", "position"]].join(tot).join(split)
f.index.name = "nominee"

# 2. extra match-log stats (shots, penalties, defending) summed over all competitions
extra_cols = ["PK", "PKatt", "Sh", "SoT", "Fls", "Fld", "Off", "Crs", "TklW", "Int", "OG"]
ex = detail.groupby("nominee")[extra_cols + ["minutes"]].sum(min_count=1).rename(columns={"minutes": "detail_minutes"})
f = f.join(ex)

# 3. per-90 numbers
m = f["minutes_total"]
f["goals_p90"] = per90(f["goals_total"], m)
f["assists_p90"] = per90(f["assists_total"], m)
f["ga_p90"] = per90(f["goals_total"] + f["assists_total"], m)
f["np_goals_total"] = f["goals_total"] - f["PK"]
f["np_goals_p90"] = per90(f["np_goals_total"], m)
dm = f["detail_minutes"]     # shots/defending come from the match-log detail, so divide by ITS minutes
f["shots_p90"] = per90(f["Sh"], dm)
f["sot_p90"] = per90(f["SoT"], dm)
f["tackles_won_p90"] = per90(f["TklW"], dm)
f["interceptions_p90"] = per90(f["Int"], dm)
f["defensive_actions_p90"] = per90(f["TklW"] + f["Int"], dm)
f["cards_p90"] = per90(f["yellow_total"] + 3 * f["red_total"], m)    # fair-play proxy; the 3x red weight is an ASSUMPTION to revisit
for g in GROUPS:
    f[f"ga_p90_{g}"] = per90(f[f"goals_{g}"] + f[f"assists_{g}"], f[f"minutes_{g}"])

# 4. xG (league games only, Understat). Never mixed with other sources.
u = us.set_index("nominee")
f["xg_league"] = u["xg_understat"]
f["npxg_league"] = u["npxg_understat"]
f["xa_league"] = u["xa_understat"]
def u_per90(col):
    return pd.Series(per90(u[col], u["understat_minutes"]), index=u.index)
f["npxg_p90_league"] = u_per90("npxg_understat")
f["xa_p90_league"] = u_per90("xa_understat")
f["key_passes_p90_league"] = u_per90("key_passes_understat")

# 5. team context: titles and progress for the player's club(s) and nation
clubs_of = {n: [c.strip() for c in cell.split("/")] for n, cell in zip(nom["player_name"], nom["club_as_listed"])}
# A title can appear in both team files (e.g. Saudi Pro League), so count each
# (team, competition) once. From team_results only league wins, the Champions League
# and the World Cup count; cups, super cups and playoffs come from the trophies file.
won_results = res[(res["result"] == "1st") |
                  ((res["result"] == "Winner") & res["competition"].isin(["Champions League", "World Cup"]))]
title_set = set(zip(won_results["team"], won_results["competition"]))
title_set |= set(zip(tro["winner"].dropna(), tro["competition"]))
def titles(team):
    return sum(1 for t, _ in title_set if t == team)
f["club_titles"] = [sum(titles(c) for c in clubs_of[n]) for n in f.index]
f["nation_titles"] = [titles(n) for n in f["national_team"]]
f["multi_club"] = [len(clubs_of[n]) > 1 for n in f.index]
wc = res[res["competition"] == "World Cup"].set_index("team")["result"]
f["world_cup_result"] = f["national_team"].map(wc)
cl = res[res["competition"] == "Champions League"].set_index("team")["result"]
f["champions_league_result"] = [next((cl[c] for c in clubs_of[n] if c in cl.index), None) for n in f.index]

# 6. quality flags
f["low_minutes"] = f["minutes_total"] < MIN_MINUTES
gap = (f["detail_minutes"] - f["minutes_total"]).abs() / f["minutes_total"] * 100
f["minutes_gap_pct"] = gap.round(1)
f["minutes_mismatch"] = gap > 5

OUT.parent.mkdir(parents=True, exist_ok=True)
f.reset_index().to_csv(OUT, index=False)
print(f"Saved {len(f)} players x {f.shape[1]} columns to {OUT}")
print("Low-minutes players (per-90 less reliable):", ", ".join(f.index[f["low_minutes"]]) or "none")
print("Minutes mismatch between sources:", ", ".join(f.index[f["minutes_mismatch"].fillna(False)]) or "none")
print("No match-log detail (shots, tackles missing):", ", ".join(f.index[f["Sh"].isna()]) or "none")
