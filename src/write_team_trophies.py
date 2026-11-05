"""Write data/raw/manual/team_trophies.csv (sourced, researched on the web on the
date below) and tidy data/raw/manual/team_results.csv.

team_trophies.csv  = winner (and runner-up where known) of every trophy in the window
                     that is not already covered by football-data.org.
team_results.csv   = placeholder rows ("CONFIRM: ...") with no result are removed,
                     and the Saudi league rows are filled in.
A backup is saved as team_results_before_tidy.csv. Safe to run once; it never
overwrites an existing team_trophies.csv.
Run:  python src/write_team_trophies.py
"""
import shutil
from pathlib import Path
import pandas as pd

MANUAL = Path("data/raw/manual")
TROPHIES = MANUAL / "team_trophies.csv"
RESULTS = MANUAL / "team_results.csv"
CHECKED = "2026-11-04"
COLS = ["competition", "edition", "date", "winner", "runner_up", "notes", "source_url", "date_checked"]

# competition, edition, date, winner, runner_up, notes, source_url
ROWS = [
 ("FA Cup", "2025-26", "2026-05-16", "Manchester City", "Chelsea", "1-0", "https://www.mykhel.com/football/fa-cup-winners-full-list-of-champions-runners-up-scoreline-as-man-city-beat-chelsea-for-2025-26-f-433077.html"),
 ("EFL Cup", "2025-26", "", "Manchester City", "Arsenal", "2-0", "https://www.outlookindia.com/sports/football/arsenal-vs-manchester-city-match-report-efl-cup-2025-26-final-wembley-stadium"),
 ("Community Shield", "2025", "2025-08-10", "Crystal Palace", "Liverpool", "2-2, won on penalties", "https://www.thenationalnews.com/sport/football/2025/08/10/crystal-palace-spot-on-after-beating-liverpool-on-penalties-to-win-community-shield-at-first-attempt"),
 ("Copa del Rey", "2025-26", "2026-04-18", "Real Sociedad", "Atletico Madrid", "won on penalties", "https://emisorasunidas.com/deportes/2026/04/18/real-sociedad-campeon-de-la-copa-del-rey-2025-26/"),
 ("Supercopa de Espana", "2026", "2026-01-11", "Barcelona", "Real Madrid", "five-goal final", "https://www.sportsmole.co.uk/football/barcelona/result/el-classico-raphina-leads-barca-triumph-in-five-goal-supercopa-de-espana-final_589657.html"),
 ("DFB-Pokal", "2025-26", "2026-05-23", "Bayern Munich", "VfB Stuttgart", "3-0", "https://www.beinsports.com/en-us/soccer/dfb-pokal/articles/bayern-munich-3-0-stuttgart-kane-hat-trick-delivers-domestic-double-with-dfb-pokal-success-2026-05-23"),
 ("DFL-Supercup", "2025", "2025-08-16", "Bayern Munich", "VfB Stuttgart", "", "https://www.thestar.com.my/sport/football/2025/08/17/soccer-kane-diaz-score-as-bayern-outclass-stuttgart-to-lift-german-supercup"),
 ("Coppa Italia", "2025-26", "2026-05-13", "Inter Milan", "Lazio", "2-0", "https://www.outlookindia.com/sports/football/lazio-vs-inter-milan-coppa-italia-2025-26-final-match-report-stadio-olimpico"),
 ("Supercoppa Italiana", "2025-26", "2025-12", "Napoli", "Bologna", "2-0", "https://www.thestar.com.my/sport/football/2025/12/23/soccer-neres-double-as-napoli-outclass-bologna-to-win-italian-super-cup"),
 ("Coupe de France", "2025-26", "2026-05-22", "Lens", "Nice", "", "https://wtop.com/sports/2026/05/lens-lift-the-french-cup-for-the-first-time-after-beating-nice-in-the-final/"),
 ("Trophee des Champions", "2026", "2026-01-08", "Paris Saint-Germain", "Marseille", "won on penalties", "https://www.flashscore.com/news/psg-marseille-report-2026-01-08/QD8Eib36"),
 ("UEFA Super Cup", "2025", "2025-08-13", "Paris Saint-Germain", "Tottenham Hotspur", "2-2, won 4-3 on penalties", "https://www.cbssports.com/soccer/news/uefa-super-cup-score-highlights-takeaways-psg-beat-tottenham-after-dramatic-comeback-penalty-shootout"),
 ("FIFA Intercontinental Cup", "2025", "2025-12", "Paris Saint-Germain", "Flamengo", "won on penalties", "https://www.arabnews.pk/node/2626638/sport"),
 ("Saudi Pro League", "2025-26", "", "Al Nassr", "", "86 points; runner-up not confirmed", "https://worldsoccertalk.com/news/cristiano-ronaldos-al-nassr-crowned-champions-updated-2025-26-saudi-pro-league-standings-after-the-final-round/"),
 ("Saudi King's Cup", "2025-26", "", "Al Hilal", "Al Kholood", "", "https://alhilal.com/en/news/al-hilal-crowned-kings-cup-champions-for-the-10th-time-in-club-history-after-defeating-al-kholood-in-the-final-match"),
 ("Saudi Super Cup", "2025", "2025-08-23", "Al Ahli", "Al Nassr", "won on penalties", "https://www.arabnews.pk/node/2612770/sport"),
 ("AFC Champions League Two", "2025-26", "2026-05-16", "Gamba Osaka", "Al Nassr", "winner inferred from a headline saying Al Nassr lost the final to Gamba Osaka", "https://www.pulsesports.ng/story/al-nassr-vs-gamba-osaka-cristiano-ronaldo-struggles-as-faris-najd-lose-champions-league-two-final-2026051622480326702"),
 ("MLS Cup", "2025", "2025-12-06", "Inter Miami", "Vancouver Whitecaps", "3-1", "https://www.irishexaminer.com/sport/soccer/arid-41755710.html"),
 ("Leagues Cup", "2025", "2025-08-31", "Seattle Sounders", "Inter Miami", "3-0, from Messi's FBref match log", "FBref match log (saved page)"),
 ("MLS Supporters' Shield", "2025", "", "Philadelphia Union", "", "", "https://www.nbcbayarea.com/news/sports/soccer/philadelphia-union-2025-mls-supporters-shield/"),
 ("Africa Cup of Nations", "2025", "2026-01-18", "Senegal", "Morocco", "1-0 after extra time", "https://www.africanews.com/2026/01/19/senegal-stun-morocco-in-afcon-2025-final-to-retain-continental-crown-football-now/"),
 ("Finalissima", "2026", "", "", "", "postponed and not played in the window; no winner", "https://www.minuto60.com/deportes/espana-argentina-finalissima-que-no-fue-definira-mundial/12040"),
]

if TROPHIES.exists():
    print(f"{TROPHIES.name} already exists, leaving it alone.")
else:
    pd.DataFrame([r + (CHECKED,) for r in ROWS], columns=COLS).to_csv(TROPHIES, index=False)
    print(f"Wrote {TROPHIES.name} with {len(ROWS)} rows")

if RESULTS.exists():
    backup = MANUAL / "team_results_before_tidy.csv"
    if not backup.exists():          # keep the first backup only
        shutil.copy(RESULTS, backup)
    tr = pd.read_csv(RESULTS, dtype=str)
    before = len(tr)
    placeholder = tr["competition"].astype(str).str.startswith("CONFIRM") & tr["result"].isna()
    # the Saudi clubs' league rows are researched, so fill them instead of dropping them
    saudi = {"Al Nassr": ("1st", "86 points; champions", "https://worldsoccertalk.com/news/cristiano-ronaldos-al-nassr-crowned-champions-updated-2025-26-saudi-pro-league-standings-after-the-final-round/"),
             "Al Qadsiah": ("4th", "77 points per a Wikipedia season page; VERIFY, page may predate the final table", "https://en.wikipedia.org/wiki/2025%E2%80%9326_Al-Qadsiah_FC_season")}
    is_league_ph = tr["competition"].astype(str).str.startswith("CONFIRM: domestic league")
    for team, (pos, note, url) in saudi.items():
        m = is_league_ph & (tr["team"] == team)
        if m.any():
            tr.loc[m, ["competition", "result", "source_url", "date_checked", "notes"]] = ["Saudi Pro League", pos, url, CHECKED, note]
            placeholder &= ~m
    tr = tr[~placeholder]
    tr.to_csv(RESULTS, index=False)
    print(f"team_results.csv: removed {int(placeholder.sum())} empty placeholder rows ({before} -> {len(tr)}). Backup: team_results_before_tidy.csv")