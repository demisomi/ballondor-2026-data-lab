"""Download Understat league player stats once and keep the raw files."""
import json
import time
from pathlib import Path
from understatapi import UnderstatClient

OUT = Path("data/raw/understat")
OUT.mkdir(parents=True, exist_ok=True)
LEAGUES = ["EPL",  "La_Liga", "Bundesliga", "Serie_A", "Ligue_1"]
SEASON = "2025"

with UnderstatClient() as understat:
    for league in LEAGUES:
        path = OUT / f"{league}_{SEASON}_players.json"
        if path.exists():
            print("skip", path.name)
            continue
        data = understat.league(league=league).get_player_data(season=SEASON)
        path.write_text(json.dumps(data), encoding="utf-8")
        print("saved", path.name, len(data), "players")
        time.sleep(5)