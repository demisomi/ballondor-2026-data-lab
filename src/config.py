"""Central settings, so no magic values are scattered through the code."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"

# Official Ballon d'Or window
WINDOW_START = "2025-08-03"
WINDOW_END = "2026-07-19"

# football-data.org
FD_BASE = "https://api.football-data.org/v4"
FD_SEASON = 2025                      # means the 2025-26 season
# (competition code, season) pairs to download
FD_TARGETS = [
    ("PL", 2025), ("PD", 2025), ("SA", 2025),
    ("BL1", 2025), ("FL1", 2025), ("CL", 2025),
    ("WC", 2026),
]

FD_SECONDS_BETWEEN_CALLS = 6.5        # 10 calls/min = 1 per 6s, plus a safety margin


def get_fd_key() -> str:
    key = os.environ.get("FOOTBALL_DATA_KEY")
    if not key:
        raise RuntimeError("Set the FOOTBALL_DATA_KEY environment variable first.")
    return key