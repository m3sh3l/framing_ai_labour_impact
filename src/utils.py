"""Shared helpers for corpus retrieval and cleaning."""
import hashlib
import json
import logging
import re
import time
from datetime import date, datetime, timezone
from pathlib import Path

import requests
import yaml

ROOT = Path(__file__).resolve().parent.parent

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(ROOT / "retrieval.log"),  # evidence for the logbook
    ],
)
log = logging.getLogger("corpus")


def load_config() -> dict:
    with open(ROOT / "config.yaml") as f:
        return yaml.safe_load(f)


def window(cfg) -> tuple[date, date]:
    w = cfg["window"]
    return date.fromisoformat(w["start"]), date.fromisoformat(w["end"])


def epoch(d: date) -> int:
    return int(datetime(d.year, d.month, d.day, tzinfo=timezone.utc).timestamp())


def half_year(ts: int) -> str:
    d = datetime.fromtimestamp(ts, tz=timezone.utc)
    return f"{d.year}H{1 if d.month <= 6 else 2}"


def quarter(ts: int) -> str:
    d = datetime.fromtimestamp(ts, tz=timezone.utc)
    return f"{d.year}Q{(d.month - 1) // 3 + 1}"


def hash_username(name: str, salt: str) -> str:
    """Pseudonymise usernames (proposal §8.1)."""
    if not name:
        return ""
    return hashlib.sha256((salt + name).encode()).hexdigest()[:16]


def is_relevant(text: str, cfg) -> bool:
    """Labour-relevance filter: requires an AI term AND a labour term (proposal §4.2)."""
    t = (text or "").lower()
    r = cfg["relevance"]
    return bool(re.search(r["ai_terms"], t)) and bool(re.search(r["labour_terms"], t))


def get_json(url: str, params: dict | None = None, retries: int = 4, pause: float = 1.0):
    """GET with retry/backoff; logs every call (auditability, proposal §4.7)."""
    for attempt in range(retries):
        try:
            resp = requests.get(url, params=params, timeout=60,
                                headers={"User-Agent": "MSc-research-corpus/1.0"})
            if resp.status_code == 200:
                return resp.json()
            log.warning("HTTP %s from %s (attempt %d)", resp.status_code, url, attempt + 1)
        except (requests.RequestException, json.JSONDecodeError) as e:
            log.warning("Request failed: %s (attempt %d)", e, attempt + 1)
        time.sleep(pause * (2 ** attempt))
    log.error("Giving up on %s", url)
    return None


def get_json_status(url: str, params: dict | None = None, timeout: int = 60):
    """Single GET attempt; returns (json_or_None, http_status_or_None).

    Unlike get_json, does NOT retry. Callers that need adaptive pacing
    (the PullPush crawler) own their retry loop and react to 429s.
    """
    try:
        resp = requests.get(url, params=params, timeout=timeout,
                            headers={"User-Agent": "MSc-research-corpus/1.0"})
        if resp.status_code == 200:
            try:
                return resp.json(), 200
            except json.JSONDecodeError:
                return None, 200
        return None, resp.status_code
    except requests.RequestException:
        return None, None


class Pacer:
    """Adaptive request pacing: doubles on 429 up to a ceiling, decays on success."""

    def __init__(self, base: float = 2.0, maximum: float = 60.0):
        self.base, self.maximum = base, maximum
        self.pause = base

    def wait(self):
        time.sleep(self.pause)

    def backoff(self):
        self.pause = min(self.pause * 2, self.maximum)
        log.info("Rate-limited; pause now %.1fs", self.pause)

    def success(self):
        # decay slowly: snapping straight back to base after a 429 streak
        # re-trips burst detectors and lands us back at the ceiling
        self.pause = max(self.base, self.pause * 0.9)


class Checkpoint:
    """Append-only log of completed crawl cells so interrupted runs resume."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.done: set[str] = set()
        if self.path.exists():
            self.done = set(self.path.read_text().splitlines())
        self._fh = open(self.path, "a")

    def is_done(self, key: str) -> bool:
        return key in self.done

    def mark(self, key: str):
        self.done.add(key)
        self._fh.write(key + "\n")
        self._fh.flush()


def append_jsonl(items: list[dict], path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")


def save_jsonl(items: list[dict], path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")
    log.info("Wrote %d items -> %s", len(items), path)
