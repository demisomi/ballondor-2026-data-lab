# Ballon d'Or 2026 Data Lab

Who deserves the 2026 Ballon d'Or, judged
by data instead of narrative? This project scores all 30 male nominees against the
award's own stated criteria, tests how sensitive the ranking is to the scoring method,
and checks the result against the real 2026 vote.

**Read the story first:** [Ballon d'Or Data Lab — the write-up](https://ballondor-datalab.netlify.app/)
is the human-readable version of everything below, with interactive charts.

---

## What this does

The Ballon d'Or jury is asked to weigh three things: individual performance, team
performance and titles, and class and fair play. This project turns that into a
reproducible scoring pipeline:

1. Collect every nominee's individual stats, club results and disciplinary record
   for the official window, **3 August 2025 to 19 July 2026**.
2. Build one feature row per nominee: per-90 numbers, team titles, league position,
   Champions League and World Cup results, and card counts.
3. Score each nominee three ways, because "individual performance" can fairly be
   measured two different ways and the choice changes the winner:
   - **Position groups** — each nominee is ranked only against players in his own
     position (forward / midfielder / defender). Fair to defenders, who rarely score.
   - **One yardstick** — every nominee is ranked on the same scale regardless of
     position. Simple, but favours goal-scorers.
   - **Blend** — the average of the two above, used as the headline method.
4. Stress-test the result by redrawing the 50/30/20 weighting 2,000 times and
   checking whether the winner changes.
5. Compare the result against the real 2026 Ballon d'Or vote (Harry Kane won).

## Result

Harry Kane wins on the "one yardstick" and "blend" methods, and also won the real
vote. The "position groups" method instead ranks Nuno Mendes first — a defender who
finishes 14th on the single shared yardstick and 23rd in the real vote. That gap is
the main finding of the project: a fair-looking choice about *who a player is
compared against* changes the Ballon d'Or winner. Full numbers and charts are in the
story page linked above and in `data/processed/scores.csv`.

## Method notes and honest limits

- **Class is measured by cards only.** The award's "class and fair play" criterion
  can't be scored from match data, so this project scores fair play (yellow/red
  cards, with a floor so a few cards can't decide the winner) and leaves class out.
- **Goals conceded are not included**, which likely understates elite defenders on
  dominant teams.
- **League-strength adjustments are assumed, not measured** (Saudi Pro League and
  MLS are discounted relative to the "big five" leagues).
- **A few position classifications are judgement calls** (e.g. Michael Olise, João
  Neves, Bruno Fernandes), made before any scores were computed.
- **The blend was adopted after seeing the defender effect** in the position-group
  method. It is a robustness check against that effect, not a method chosen
  independently of the result — the README says so rather than hiding it.
- **xG only exists for the 27 top-five-league players**, from Understat; it is never
  mixed with another provider for the same player.
- **One vote is thin evidence.** The real-vote comparison in the story page is
  informative, not a validation set the scoring was tuned to match.

## Project layout

```
.
├── data/
│   ├── raw/              Collected inputs (see "Data" below for what's tracked)
│   ├── interim/          Combined/validated tables between pipeline steps
│   └── processed/        Final feature table and scores — the pipeline's output
├── src/                  Pipeline scripts, run in the order below
├── notebooks/            Exploratory notebooks (none checked in yet)
├── tests/                Automated checks on the scoring logic
└── requirements.txt
```

## Data

**Tracked in Git** (small, hand-checked, not reproducible by re-running a script):
- `data/raw/nominees_2026.csv` — the 30 nominees, as published.
- `data/raw/manual/*.csv` — league/continental/cup/international stats per nominee,
  verified by hand against FBref and football-data.org, plus club titles and results.
- `data/interim/`, `data/processed/` — validated and scored outputs. Small, and
  useful as checked-in evidence of what the pipeline produced.

**Not tracked in Git** (large and/or re-fetchable — see `.gitignore`):
- `data/raw/matchlogs/*.html` — ~14 MB of hand-saved FBref match-log pages (FBref
  blocks scripted downloads, so these were saved by hand one at a time). **Back these
  up somewhere outside Git** (a zip in cloud storage is enough) — without them,
  `build_from_matchlogs.py`-style reprocessing can't be rerun from scratch.
- `data/raw/football_data/` and `data/raw/understat/` — JSON pulled from the
  football-data.org and Understat APIs. Re-fetchable with an API key.
- `data/raw/players_data-2025_2026.csv` — third-party Kaggle squad-mapping dataset,
  not this project's own data.

## Running the pipeline

Requires Python 3.10+ and a free [football-data.org](https://www.football-data.org/)
API key.

```bash
python -m venv .venv
source .venv/bin/activate          # .venv\Scripts\activate on Windows
pip install -r requirements.txt
export FOOTBALL_DATA_KEY=your_key_here   # set FOOTBALL_DATA_KEY=... on Windows
```

Scripts are run in this order. Steps marked **(manual)** require hand-filling or
hand-verifying a CSV before the next script will have complete data — this project
intentionally favours checked data over fully automated scraping.

| Step | Script | What it does |
|---|---|---|
| 1 | `src/build_competition_tables.py` | Creates the blank, hand-filled stage CSVs in `data/raw/manual/` |
| 2 | *(manual)* | Save FBref match-log pages to `data/raw/matchlogs/`, fill in cup/international rows |
| 3 | `src/build_from_matchlogs.py` | Sums saved match logs into `data/interim/matchlog_detail.csv` |
| 4 | `src/collect_understat.py` | Pulls xG/xA for the 27 top-five-league nominees |
| 5 | `src/merge_understat.py` | Merges Understat data into the interim table |
| 6 | `src/validate_competition_stats.py` | Checks and combines everything into `data/interim/player_competition_stats.csv` |
| 7 | `src/build_team_tables.py` | Pre-fills `data/raw/manual/team_results.csv` from football-data.org |
| 8 | `src/derive_team_results.py`, `src/write_team_trophies.py` | Derives league position/stage and titles |
| 9 | `src/validate_team_data.py` | Validates the team-level data |
| 10 | `src/build_player_features.py` | Builds `data/processed/player_features.csv` |
| 11 | `src/score_players.py` | Scores all three methods, runs the 2,000-draw stability test, writes `data/processed/scores.csv` |

`src/coverage_report.py` and `src/check_*.py` are standalone checks, not part of the
main sequence — run them any time to sanity-check coverage or cross-check against
the Kaggle CSV.

## Testing

```bash
python -m pytest tests/ -v
```

`tests/test_score_players.py` checks the scoring math directly (weights sum to 1,
blend formula, stage-to-points mapping) without needing the full data pipeline.

## Reproducibility

Every number on the story page can be traced back to a row in
`data/processed/scores.csv`, which in turn traces back to `data/raw/manual/*.csv` and
the match-log pages. `data/raw/manual/*.csv` carries a `source_url` and
`date_checked` column per row for exactly this reason.
