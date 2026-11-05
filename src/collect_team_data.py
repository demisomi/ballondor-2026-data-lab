import json
from config import RAW

data = json.loads((RAW / "football_data" / "WC_2026_matches.json").read_text("utf-8"))
final = data["matches"][-1]
print("Keys in a match:", list(final.keys()))
print("Stage:", final["stage"], "| Score:", final["score"])
print("Has scorers:", "goals" in final)