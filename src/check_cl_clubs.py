"""Which nominee clubs actually appear in the 2025-26 Champions League?"""
import difflib
import json
import unicodedata
import pandas as pd
from config import RAW


def norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", str(text))
    return "".join(c for c in text if not unicodedata.combining(c)).lower().strip()


data = json.loads((RAW / "football_data" / "CL_2025_matches.json").read_text("utf-8"))

cl_teams = {}
for match in data["matches"]:
    for side in ("homeTeam", "awayTeam"):
        name = (match.get(side) or {}).get("name")   # some slots can be empty
        if name:
            cl_teams[norm(name)] = name

mapping = pd.read_csv("data/interim/nominee_map.csv")
print(f"{len(cl_teams)} clubs appear in the Champions League file\n")

for club in sorted(mapping["squad"].unique()):
    best = difflib.get_close_matches(norm(club), cl_teams.keys(), n=1, cutoff=0.0)[0]
    score = difflib.SequenceMatcher(None, norm(club), best).ratio()
    verdict = "likely in CL" if score >= 0.7 else "REVIEW: probably not in CL"
    print(f"{club:<24} best match: {cl_teams[best]:<32} ({score:.2f})  {verdict}")