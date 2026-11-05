"""Phase 2, step 2: score the nominees and test how stable the ranking is.

Three criteria, as in the official Ballon d'Or rules:
  1. Individual performance  (compared WITHIN position group: forwards, midfielders, defenders)
  2. Team performance and titles
  3. Class and fair play     (class cannot be measured from our data; fair play only for now)
Every weight and rule is in the CONFIG block below so it can be changed and re-run.
Run:  python src/score_players.py
"""
import numpy as np
import pandas as pd

FEATURES = "data/processed/player_features.csv"
RESULTS = "data/raw/manual/team_results.csv"
TROPHIES = "data/raw/manual/team_trophies.csv"
NOMINEE_MAP = "data/interim/nominee_map.csv"      # which club each player actually played for (Kaggle)
OUT = "data/processed/scores.csv"

# ---------------- CONFIG ----------------
SCHEMES = {                                    # (individual, team, class_fair_play)
    "official_50_30_20": (0.50, 0.30, 0.20),
    "equal_33_33_33": (1 / 3, 1 / 3, 1 / 3),
    "individual_heavy_70_20_10": (0.70, 0.20, 0.10),
}
OFFICIAL = SCHEMES["official_50_30_20"]

# metric -> weight inside criterion 1, per position group (each group sums to 1.0)
POS_METRICS = {
    "FWD": {"np_goals_p90": .30, "assists_p90": .15, "npxg_p90_league": .10, "xa_p90_league": .05,
            "sot_p90": .10, "ga_p90_bigstage": .20, "minutes_total": .10},
    "MID": {"ga_p90": .20, "xa_p90_league": .10, "key_passes_p90_league": .15,
            "defensive_actions_p90": .20, "ga_p90_bigstage": .20, "np_goals_p90": .05, "minutes_total": .10},
    "DEF": {"defensive_actions_p90": .35, "ga_p90": .15, "xa_p90_league": .05,
            "key_passes_p90_league": .10, "ga_p90_bigstage": .20, "minutes_total": .15},
}
# Bracket check: ONE formula for all players, ranked against all 30 (no position groups).
# Defenders look weak on this yardstick, forwards look strong; the truth sits between the two methods.
COMMON_METRICS = {"ga_p90": .35, "ga_p90_bigstage": .25, "np_goals_p90": .15,
                  "defensive_actions_p90": .10, "minutes_total": .15}
MIN_WEIGHT_AVAILABLE = 0.6          # need at least 60% of a player's metric weight to score him
BIGSTAGE_MIN_MINUTES = 180          # continental + international minutes needed for the big-stage metric

STAGE_SCORE = {"Winner": 100, "Runner-up": 85, "Semi-final": 70, "Quarter-final": 55,
               "Round of 16": 40, "Round of 32": 25, "Knockout playoff round": 30,
               "League phase": 20, "Group stage": 10, "Did not qualify": 0}
TEAM_PARTS = {"trophies": .35, "continental": .20, "league_position": .15, "national": .30}
TROPHY_POINTS = 25                  # each title = 25 points, capped at 100
LEAGUE_POINTS_LOST_PER_PLACE = 12   # 1st = 100, 2nd = 88, 3rd = 76 ...
LEAGUE_STRENGTH = {"Premier League": 1, "La Liga": 1, "Serie A": 1, "Bundesliga": 1, "Ligue 1": 1,
                   "Saudi Pro League": 0.75}
OTHER_LEAGUE_STRENGTH = 0.70        # clubs with no ranked league row (e.g. MLS)
FAIR_PLAY_FLOOR = 50                 # 0 = card counts can cost up to 100 points. Try 50: cards then cost at most 50.
FULL_CONTRIBUTION_MINUTES = 3000    # team credit is scaled down for players with fewer minutes
N_DRAWS, SEED, DRAW_CONCENTRATION = 2000, 42, 20
# ----------------------------------------

f = pd.read_csv(FEATURES)
res = pd.read_csv(RESULTS, dtype=str)
tro = pd.read_csv(TROPHIES, dtype=str)
nmap = pd.read_csv(NOMINEE_MAP).set_index("nominee")["squad"].to_dict()

unknown = set(f["position"]) - set(POS_METRICS)
if unknown:
    raise SystemExit(f"Unknown position codes {unknown}; expected FWD, MID or DEF")

# derived big-stage metric: goals + assists per 90 in continental + international games
bs_min = f["minutes_continental"] + f["minutes_international"]
bs_ga = (f["goals_continental"] + f["goals_international"]
         + f["assists_continental"] + f["assists_international"])
f["ga_p90_bigstage"] = np.where(bs_min >= BIGSTAGE_MIN_MINUTES, bs_ga / bs_min * 90, np.nan)

# ---- criterion 1: individual, percentile within position group ----
def pct_within_group(col):
    return f.groupby("position")[col].rank(pct=True) * 100

c1 = pd.Series(np.nan, index=f.index)
c1_missing = pd.Series(0.0, index=f.index)
for pos, metrics in POS_METRICS.items():
    idx = f.index[f["position"] == pos]
    num = pd.Series(0.0, index=idx)
    den = pd.Series(0.0, index=idx)
    for col, w in metrics.items():
        p = pct_within_group(col).loc[idx]
        ok = p.notna()
        num[ok] += w * p[ok]
        den[ok] += w
    c1.loc[idx] = np.where(den >= MIN_WEIGHT_AVAILABLE, num / den.replace(0, np.nan), np.nan)
    c1_missing.loc[idx] = 1 - den
f["c1_individual"] = c1
f["c1_weight_missing"] = c1_missing.round(2)

# ---- criterion 1, bracket version: one formula, percentile across all players ----
num = pd.Series(0.0, index=f.index); den = pd.Series(0.0, index=f.index)
for col, w in COMMON_METRICS.items():
    p = f[col].rank(pct=True) * 100
    ok = p.notna()
    num[ok] += w * p[ok]; den[ok] += w
f["c1_common"] = np.where(den >= MIN_WEIGHT_AVAILABLE, num / den.replace(0, np.nan), np.nan)

# ---- criterion 3: fair play only (class is not measurable from our data) ----
raw_fair = 100 - pct_within_group("cards_p90") + 100 / f.groupby("position")["cards_p90"].transform("count")
f["c3_fair_play"] = FAIR_PLAY_FLOOR + (100 - FAIR_PLAY_FLOOR) * raw_fair / 100

# ---- criterion 2: team ----
ordinal = res["result"].fillna("").str.extract(r"^(\d+)(?:st|nd|rd|th)$")[0].astype(float)
league = res[ordinal.notna()].assign(pos=ordinal[ordinal.notna()])
league_by_team = {r.team: (r.pos, r.competition) for r in league.itertuples()}

def club_parts(club):
    pos, comp = league_by_team.get(club, (np.nan, None))
    strength = LEAGUE_STRENGTH.get(comp, OTHER_LEAGUE_STRENGTH)
    lp = max(0, 100 - LEAGUE_POINTS_LOST_PER_PLACE * (pos - 1)) * strength if pd.notna(pos) else 0
    return lp

won_results = res[(res["result"] == "1st") |
                  ((res["result"] == "Winner") & res["competition"].isin(["Champions League", "World Cup"]))]
title_set = set(zip(won_results["team"], won_results["competition"])) | set(zip(tro["winner"].dropna(), tro["competition"]))
def titles(team):
    return sum(1 for t, _ in title_set if t == team)
cl_result = res[res["competition"] == "Champions League"].set_index("team")["result"].to_dict()

def main_clubs(name, clubs):
    """The club(s) to credit. A player listed with two clubs is credited to the one
    his Kaggle/Understat record shows; if that cannot be matched, both are averaged."""
    if len(clubs) == 1:
        return clubs, False
    squad = str(nmap.get(name, "")).lower()
    hit = [c for c in clubs if squad and (c.lower() in squad or squad in c.lower())]
    return (hit[:1], False) if hit else (clubs, True)

team_scores, contributions, unresolved = [], [], []
for r in f.itertuples():
    clubs, ambiguous = main_clubs(r.nominee, [c.strip() for c in r.club_as_listed.split("/")])
    if ambiguous:
        unresolved.append(r.nominee)
    lp = np.mean([club_parts(c) for c in clubs])
    trophies = np.mean([min(100, TROPHY_POINTS * titles(c)) for c in clubs])
    cont = np.mean([STAGE_SCORE.get(cl_result.get(c), 0) for c in clubs])
    wc = STAGE_SCORE.get(r.world_cup_result, 0) if isinstance(r.world_cup_result, str) else 0
    extra_nat = max(0, r.nation_titles - (1 if r.world_cup_result == "Winner" else 0))
    national = min(100, wc + TROPHY_POINTS * extra_nat)
    parts = {"trophies": trophies, "continental": cont, "league_position": lp, "national": national}
    raw = sum(TEAM_PARTS[k] * v for k, v in parts.items())
    contrib = min(1.0, r.minutes_total / FULL_CONTRIBUTION_MINUTES)
    team_scores.append(raw * contrib)
    contributions.append(contrib)
f["c2_team"] = team_scores
f["team_contribution"] = np.round(contributions, 2)

# ---- final scores and ranks under each weighting ----
scored = f["c1_individual"].notna()
for name, (w1, w2, w3) in SCHEMES.items():
    f[f"score_{name}"] = np.where(scored, w1 * f["c1_individual"] + w2 * f["c2_team"] + w3 * f["c3_fair_play"], np.nan)
    f[f"rank_{name}"] = f[f"score_{name}"].rank(ascending=False, method="min")

w1, w2, w3 = OFFICIAL
f["score_common_yardstick_50_30_20"] = np.where(f["c1_common"].notna(),
    w1 * f["c1_common"] + w2 * f["c2_team"] + w3 * f["c3_fair_play"], np.nan)
f["rank_common_yardstick_50_30_20"] = f["score_common_yardstick_50_30_20"].rank(ascending=False, method="min")

# ---- stability: random weights centred on the official ones ----
rng = np.random.default_rng(SEED)
draws = rng.dirichlet(np.array(OFFICIAL) * DRAW_CONCENTRATION, size=N_DRAWS)
comp = f.loc[scored, ["c1_individual", "c2_team", "c3_fair_play"]].to_numpy()
totals = draws @ comp.T
order = (-totals).argsort(axis=1)
names = f.loc[scored, "nominee"].to_numpy()
first = pd.Series(names[order[:, 0]]).value_counts() / N_DRAWS * 100
top3 = pd.Series(names[order[:, :3].ravel()]).value_counts() / N_DRAWS * 100
f["pct_draws_rank1"] = f["nominee"].map(first).fillna(0).round(1)
f["pct_draws_top3"] = f["nominee"].map(top3).fillna(0).round(1)

keep = ["nominee", "position", "club_as_listed", "multi_club", "low_minutes", "c1_individual", "c1_common", "c1_weight_missing",
        "c2_team", "team_contribution", "c3_fair_play"] + \
       [c for n in SCHEMES for c in (f"score_{n}", f"rank_{n}")] + ["score_common_yardstick_50_30_20", "rank_common_yardstick_50_30_20", "pct_draws_rank1", "pct_draws_top3"]
out = f[keep].sort_values(f"rank_{list(SCHEMES)[0]}")
out.round(2).to_csv(OUT, index=False)

pd.set_option("display.width", 220)
show = ["nominee", "position", "c1_individual", "c1_common", "c2_team", "c3_fair_play"] + \
       [f"rank_{n}" for n in SCHEMES] + ["rank_common_yardstick_50_30_20", "pct_draws_rank1", "pct_draws_top3"]
print(f"Saved {len(out)} rows to {OUT}\n")
print("ALL PLAYERS, best first by the official 50/30/20 (position groups). Last-but-two column = one-formula bracket:\n")
print(out[show].round(1).to_string(index=False))
if (~scored).any():
    print("\nNot scored (too little data):", ", ".join(f.loc[~scored, "nominee"]))
print("\nTwo-club players whose club could not be matched (credited with the average of both):", ", ".join(unresolved) or "none")
print("Low minutes:", ", ".join(f.loc[f["low_minutes"], "nominee"]) or "none")