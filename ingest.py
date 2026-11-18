"""Refresh the raw games file from nflverse. The repo ships a snapshot so it runs offline."""
import urllib.request
from pathlib import Path

URL = "https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv"
DEST = Path(__file__).parent / "data" / "raw" / "games.csv"

if __name__ == "__main__":
    DEST.parent.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(URL, DEST)
    print(f"saved {DEST} ({sum(1 for _ in DEST.open()) - 1} games)")
