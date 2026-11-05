"""Create data/raw/manual/team_results.csv, prefilled from football-data.org.

Prefilled automatically:  league position (PL, La Liga, Serie A, Bundesliga, Ligue 1),
Champions League stage reached, World Cup stage reached.
Left blank for you to fill by hand: domestic cups, super cups, Saudi/MLS clubs,
and national teams' other competitions.
Never overwrites an existing file (delete the old blank one first if it has no work in it).
Run:  python src/build_team_tables.py
"""
import json
from pathlib import Path
import pandas as pd

NOMINEES = "data/raw/nominees_2026.csv"
FD_DIR = Path("data/raw/football_data")
OUT = Path("data/raw/manual/team_results.csv")
MAP_OUT = Path("data/interim/club_name_map.csv")
COLUMNS = ["team", "team_type", "competition", "result",
           "source_url", "date_checked", "notes"]
RESULT_WORDS = ("Winner, Runner-up, Semi-final, Quarter-final, Round of 16, Round of 32, "
                "Knockout playoff round, Group stage, League phase, Did not qualify, "
                "Not entered  (league rows: 1st, 2nd, 3rd ...)")

# nominee-file club name -> football-data.org name (clubs not listed need hand-collecting)
CLUB_NAMES = {
    "Real Madrid": "Real Madrid CF",
    "Barcelona": "FC Barcelona",
    "Chelsea": "Chelsea FC",
    "Paris Saint-Germain": "Paris Saint-Germain FC",
    "Manchester United": "Manchester United FC",
    "Manchester City": "Manchester City FC",
    "Arsenal": "Arsenal FC",
    "Bayern Munich": "FC Bayern München",
    "Inter Milan": "FC Internazionale Milano",
}
LEAGUES = {"PL": "Premier League", "PD": "La Liga", "SA": "Serie A",
           "BL1": "Bundesliga", "FL1": "Ligue 1"}
CL_ORDER = ["LEAGUE_STAGE", "PLAYOFFS", "LAST_16", "QUARTER_FINALS", "SEMI_FINALS", "FINAL"]
CL_WORD = {"LEAGUE_STAGE": "League phase", "PLAYOFFS": "Knockout playoff round",
           "LAST_16": "Round of 16", "QUARTER_FINALS": "Quarter-final",
           "SEMI_FINALS": "Semi-final"}
WC_ORDER = ["GROUP_STAGE", "LAST_32", "LAST_16", "QUARTER_FINALS", "SEMI_FINALS",
            "THIRD_PLACE", "FINAL"]
WC_WORD = {"GROUP_STAGE": "Group stage", "LAST_32": "Round of 32", "LAST_16": "Round of 16",
           "QUARTER_FINALS": "Quarter-final", "SEMI_FINALS": "Semi-final",
           "THIRD_PLACE": "Semi-final"}
today = pd.Timestamp.today().date().isoformat()


def load(name):
    path = FD_DIR / name
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def ordinal(n):
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def played(matches, team):
    return [m for m in matches if m.get("status") in ("FINISHED", "AWARDED")
            and team in (m["homeTeam"]["name"], m["awayTeam"]["name"])]


def furthest(matches, team, order):
    stages = {m["stage"] for m in played(matches, team)}
    known = [s for s in order if s in stages]
    return known[-1] if known else None


def won_final(matches, team):
    for m in played(matches, team):
        if m["stage"] == "FINAL":
            side = "HOME_TEAM" if m["homeTeam"]["name"] == team else "AWAY_TEAM"
            return m["score"].get("winner") == side
    return False


def knockout_result(matches, team, order, words, src):
    stage = furthest(matches, team, order)
    if stage is None:
        return None
    if stage == "FINAL":
        word = "Winner" if won_final(matches, team) else "Runner-up"
    else:
        word = words[stage]
    note = f"furthest stage played: {stage}"
    if stage == "THIRD_PLACE":
        note += " (lost semi-final, played third-place match)"
    return word, note, f"football-data.org: {src}"


def league_position(fd_name):
    for code in LEAGUES:
        d = load(f"{code}_2025_standings.json")
        if not d:
            continue
        total = next((t for t in d["standings"] if t.get("type") == "TOTAL"), None)
        for r in (total or {}).get("table", []):
            if r["team"]["name"] == fd_name:
                return code, r["position"], r["points"], r["playedGames"]
    return None


nominees = pd.read_csv(NOMINEES)
clubs = sorted({c.strip() for cell in nominees["club_as_listed"] for c in cell.split("/")})
nations = sorted(set(nominees["national_team"]))
cl = load("CL_2025_matches.json")
wc = load("WC_2026_matches.json")
wc_teams = {m[s]["name"] for m in (wc or {}).get("matches", []) for s in ("homeTeam", "awayTeam")}

rows, unmapped = [], []
for club in clubs:
    fd = CLUB_NAMES.get(club)
    lp = league_position(fd) if fd else None
    if lp:
        code, pos, pts, gp = lp
        rows.append({"team": club, "team_type": "club", "competition": LEAGUES[code],
                     "result": ordinal(pos), "source_url": f"football-data.org: {code}_2025_standings.json",
                     "date_checked": today, "notes": f"{pts} points from {gp} games"})
    else:
        rows.append({"team": club, "team_type": "club",
                     "competition": "CONFIRM: domestic league (final position)"})
        unmapped.append(club)
    res = knockout_result(cl["matches"], fd, CL_ORDER, CL_WORD, "CL_2025_matches.json") if (fd and cl) else None
    if res:
        rows.append({"team": club, "team_type": "club", "competition": "Champions League",
                     "result": res[0], "source_url": res[2], "date_checked": today, "notes": res[1]})
    else:
        rows.append({"team": club, "team_type": "club",
                     "competition": "CONFIRM: continental competition",
                     "notes": "not in Champions League data; check Europa/Conference/AFC and super cups"})
    rows.append({"team": club, "team_type": "club", "competition": "CONFIRM: domestic cup"})

for nation in nations:
    res = knockout_result(wc["matches"], nation, WC_ORDER, WC_WORD, "WC_2026_matches.json") if wc else None
    if res:
        rows.append({"team": nation, "team_type": "national", "competition": "World Cup",
                     "result": res[0], "source_url": res[2], "date_checked": today, "notes": res[1]})
    elif wc and nation not in wc_teams:
        rows.append({"team": nation, "team_type": "national", "competition": "World Cup",
                     "result": "Did not qualify", "source_url": "football-data.org: WC_2026_matches.json",
                     "date_checked": today, "notes": f"{nation} is not among the teams in the World Cup data"})
    else:
        rows.append({"team": nation, "team_type": "national", "competition": "World Cup"})
    rows.append({"team": nation, "team_type": "national",
                 "competition": "CONFIRM: other (qualifiers, continental cup)"})

MAP_OUT.parent.mkdir(parents=True, exist_ok=True)
pd.DataFrame([{"nominee_club": c, "football_data_name": CLUB_NAMES.get(c, "")} for c in clubs]).to_csv(MAP_OUT, index=False)

if OUT.exists():
    print(f"{OUT.name} already exists, leaving it alone. Delete it first if it is still blank.")
else:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows).reindex(columns=COLUMNS)
    df.to_csv(OUT, index=False)
    print(f"Wrote {OUT.name}: {len(df)} rows, {int(df['result'].notna().sum())} prefilled from football-data.org")
    print("Allowed results:", RESULT_WORDS)
    if unmapped:
        print("No football-data.org league data for (fill by hand):", ", ".join(unmapped))
print(f"Club name map saved to {MAP_OUT}")