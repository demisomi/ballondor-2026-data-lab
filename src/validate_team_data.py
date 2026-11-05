"""Check team_results.csv and team_trophies.csv. Run:  python src/validate_team_data.py"""
import re
import sys
import pandas as pd

NOMINEES = "data/raw/nominees_2026.csv"
RESULTS = "data/raw/manual/team_results.csv"
TROPHIES = "data/raw/manual/team_trophies.csv"
ALLOWED = {"Winner", "Runner-up", "Semi-final", "Quarter-final", "Round of 16",
           "Round of 32", "Knockout playoff round", "Early round", "Group stage",
           "League phase", "Did not qualify", "Not entered"}
ORDINAL = re.compile(r"^\d{1,2}(st|nd|rd|th)$")

nom = pd.read_csv(NOMINEES)
clubs = {c.strip() for cell in nom["club_as_listed"] for c in cell.split("/")}
nations = set(nom["national_team"])
res = pd.read_csv(RESULTS, dtype=str)
tro = pd.read_csv(TROPHIES, dtype=str)
problems, notes = [], []

for r in res.itertuples():
    where = f"team_results: {r.team} / {r.competition}"
    if r.team_type == "club" and r.team not in clubs or r.team_type == "national" and r.team not in nations:
        problems.append(f"{where}: team not in the nominee file")
    if str(r.competition).startswith("CONFIRM"):
        problems.append(f"{where}: placeholder name, rename it or delete the row")
    if pd.isna(r.result):
        notes.append(f"{where}: result blank (allowed, but it will count as 'not recorded')")
    elif r.result not in ALLOWED and not ORDINAL.match(r.result):
        problems.append(f"{where}: '{r.result}' is not an allowed result word")
    if pd.isna(r.source_url) or pd.isna(r.date_checked):
        problems.append(f"{where}: missing source_url or date_checked")
for (t, c), g in res.groupby(["team", "competition"]):
    if len(g) > 1:
        problems.append(f"team_results: duplicate {t} / {c}")

for t in sorted(nations):
    if not ((res["team"] == t) & (res["competition"] == "World Cup")).any():
        problems.append(f"team_results: nation {t} has no World Cup row")
for t in sorted(clubs):
    has_league = ((res["team"] == t) & res["result"].fillna("").str.match(ORDINAL)).any()
    if not has_league:
        notes.append(f"team_results: club {t} has no league-position row (e.g. MLS is not ranked this way)")

for r in tro.itertuples():
    where = f"team_trophies: {r.competition} {r.edition}"
    if pd.isna(r.source_url):
        problems.append(f"{where}: missing source_url")
    if pd.isna(r.winner) and "not played" not in str(r.notes):
        problems.append(f"{where}: no winner and not marked as not played")
if tro.duplicated(["competition", "edition"]).any():
    problems.append("team_trophies: duplicate competition/edition rows")

print(f"team_results: {len(res)} rows | team_trophies: {len(tro)} rows")
for n in notes:
    print("  note:", n)
if problems:
    print(f"\n{len(problems)} problem(s) found:")
    for p in problems:
        print(" -", p)
    sys.exit(1)
print("\nAll team checks passed.")