"""Fill team_results.csv blanks (cups, super cups, playoffs, qualifiers) from the
nominees' saved FBref match-log pages. No downloads: it only reads data/raw/matchlogs/.

How it decides (it will NOT guess):
  - Final: win = Winner, loss = Runner-up
  - Single-leg knockout round, last match lost = eliminated in that round
  - Won a non-final round, two-leg ties, series, group/qualifier phases = result left
    BLANK with the record in the notes, because the logs can't prove the outcome
Only players listed with ONE club in the nominee file are used for club results.
Re-running replaces earlier derived rows. Rows you edit (change the notes) are kept.
Run:  python src/derive_team_results.py
"""
import unicodedata
from pathlib import Path
import pandas as pd
from config import WINDOW_START, WINDOW_END

START, END = pd.Timestamp(WINDOW_START), pd.Timestamp(WINDOW_END)
NOMINEES = "data/raw/nominees_2026.csv"
LOG_DIR = Path("data/raw/matchlogs")
TEAM_RESULTS = Path("data/raw/manual/team_results.csv")
GEN = "derived from nominees' FBref match logs"
COLUMNS = ["team", "team_type", "competition", "result",
           "source_url", "date_checked", "notes"]
NEEDED = ["Date", "Comp", "Round", "Result", "Opponent", "Min"]

LEAGUES = {"premier league", "la liga", "bundesliga", "serie a", "ligue 1", "mls",
           "saudi pro league", "pro league", "liga mx", "eredivisie", "primeira liga"}
ALREADY_COVERED = {"champions lg", "champions league", "world cup"}   # filled from football-data.org
NATIONAL_WORDS = ["qualif", "nations league", "afcon", "africa cup", "copa am",
                  "gold cup", "asian cup", "uefa euro", "wcq"]
RENAME = {"supercoppa": "Supercoppa Italiana", "ccc": "Concacaf Champions Cup"}
ROUND_WORD = {"final": "Final", "mls cup": "Final",
              "semi-finals": "Semi-final", "semifinals": "Semi-final",
              "semi-final": "Semi-final", "conference finals": "Semi-final",
              "quarter-finals": "Quarter-final", "quarterfinals": "Quarter-final",
              "conference semifinals": "Quarter-final",
              "round of 16": "Round of 16", "round of 32": "Round of 32"}
GROUPISH = ("group", "qualif", "regular", "league", "phase", "matchweek")


def slugify(name):
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return "_".join(s.lower().replace("'", "").replace(".", "").split())


def load_log(path):
    for t in pd.read_html(path):
        if isinstance(t.columns, pd.MultiIndex):
            t.columns = [c[-1] for c in t.columns]
        if all(c in t.columns for c in NEEDED):
            rows = t[t["Date"].notna() & (t["Date"] != "Date")].copy()
            rows["Date"] = pd.to_datetime(rows["Date"], errors="coerce")
            return rows
    raise SystemExit(f"No match-log table found in {path.name}")


def comp_name(row):
    c = str(row["Comp"]).strip()
    low = c.lower()
    if low == "super cup":
        if row["Date"].year == 2025 and row["Date"].month == 8:
            return "UEFA Super Cup"
        return "Super Cup (check which)"
    return RENAME.get(low, c)


nominees = pd.read_csv(NOMINEES)
events = []   # one row per (team, competition, match)
used_files = {}
for r in nominees.itertuples():
    clubs = [c.strip() for c in r.club_as_listed.split("/")]
    slug = slugify(r.player_name)
    files = sorted(f for f in LOG_DIR.glob("*.html")
                   if slugify(f.stem) == slug or slugify(f.stem).startswith(slug + "_"))
    if not files:
        continue
    log = pd.concat([load_log(f) for f in files], ignore_index=True)
    log = log[log["Date"].between(START, END)].copy()
    low = log["Comp"].astype(str).str.strip().str.lower()
    log = log[~low.str.contains("friendl") & ~low.isin(ALREADY_COVERED)]
    low = log["Comp"].astype(str).str.strip().str.lower()
    is_nat = low.apply(lambda c: any(w in c for w in NATIONAL_WORDS))
    is_league = low.isin(LEAGUES)
    rnd = log["Round"].astype(str)
    playoffs = is_league & ~rnd.str.startswith("Matchweek") & (rnd != "Regular Season")
    log = log[~is_league | playoffs].copy()
    log["competition"] = [comp_name(x) + (" playoffs" if p else "")
                          for (_, x), p in zip(log.iterrows(), playoffs[log.index])]
    log["nat"] = is_nat[log.index]
    for x in log.itertuples():
        if x.nat:
            events.append((r.national_team, "national", x.competition, x.Date, x.Round, x.Result, x.Opponent))
        elif len(clubs) == 1:
            events.append((clubs[0], "club", x.competition, x.Date, x.Round, x.Result, x.Opponent))
    used_files.setdefault(r.national_team, set()).add(r.player_name)

ev = pd.DataFrame(events, columns=["team", "team_type", "competition", "Date", "Round", "Result", "Opponent"])
ev = ev.drop_duplicates(["team", "competition", "Date", "Opponent"])

derived = []
today = pd.Timestamp.today().date().isoformat()
for (team, ttype, comp), g in ev.groupby(["team", "team_type", "competition"]):
    g = g.sort_values("Date")
    last = g.iloc[-1]
    same_round = g[g["Round"] == last["Round"]]
    key = str(last["Round"]).strip().lower()
    res_text = str(last["Result"]).strip()
    letter = res_text[:1]
    pens = "pen" in res_text.lower()
    word = ROUND_WORD.get(key)
    result, why = "", ""
    if any(w in key for w in GROUPISH):
        why = "phase with no knockout round in the logs; fill the outcome by hand"
    elif len(same_round) > 1:
        why = f"{len(same_round)} matches in '{last['Round']}' (two legs or a series); decide by hand"
    elif pens or letter not in ("W", "L"):
        why = "decided on penalties or unclear result; decide by hand"
    elif word == "Final":
        result = "Winner" if letter == "W" else "Runner-up"
    elif letter == "L":
        result = word or "Early round"
    else:
        why = f"won '{last['Round']}'; later rounds are not in the logs, check by hand"
    note = f"{GEN}. {len(g)} match(es) seen; last: {last['Round']} {res_text} vs {last['Opponent']}"
    if why:
        note += f". {why}"
    derived.append({"team": team, "team_type": ttype, "competition": comp, "result": result or None,
                    "source_url": "FBref match logs (saved pages)", "date_checked": today, "notes": note})

tr = pd.read_csv(TEAM_RESULTS)
tr = tr[~tr["notes"].fillna("").str.startswith(GEN)]          # drop earlier derived rows
dtf = pd.DataFrame(derived, columns=COLUMNS)
for team in dtf["team"].unique():
    kind = dtf.loc[dtf["team"] == team, "team_type"].iloc[0]
    drop = (["CONFIRM: domestic cup", "CONFIRM: continental competition"] if kind == "club"
            else ["CONFIRM: other (qualifiers, continental cup)"])
    tr = tr[~((tr["team"] == team) & (tr["competition"].isin(drop)))]
out = pd.concat([tr, dtf], ignore_index=True).sort_values(["team_type", "team"], kind="stable")
out.reindex(columns=COLUMNS).to_csv(TEAM_RESULTS, index=False)

print(f"Added {len(dtf)} derived rows for {dtf['team'].nunique()} teams "
      f"({int(dtf['result'].notna().sum())} with a result, {int(dtf['result'].isna().sum())} left blank for you).")
print(dtf[["team", "competition", "result"]].to_string(index=False))