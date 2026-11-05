"""A small, polite client for football-data.org."""
import time
import requests
from config import FD_BASE, FD_SECONDS_BETWEEN_CALLS, get_fd_key


class FootballDataClient:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers["X-Auth-Token"] = get_fd_key()

    def get(self, path: str, params: dict | None = None, retries: int = 3) -> dict:
        for attempt in range(retries):
            resp = self.session.get(f"{FD_BASE}{path}", params=params, timeout=30)
            time.sleep(FD_SECONDS_BETWEEN_CALLS)       # stay under the rate limit
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code == 429:                # "slow down" response
                time.sleep(30)
                continue
            # 403 usually means: your plan doesn't include this data
            raise RuntimeError(f"{resp.status_code} for {path}: {resp.text[:200]}")
        raise RuntimeError(f"Gave up on {path} after {retries} tries")