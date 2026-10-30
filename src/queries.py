"""Query compilation layer: config query_groups/events -> per-API query strings.

All three retrievers import from here so group membership tagging is applied
identically everywhere (mirrors the single-relevance-rule design decision).
"""
from datetime import date

from utils import epoch


def load_groups(cfg) -> dict[str, list[str]]:
    """{group_name: [canonical query strings]}."""
    return cfg["query_groups"]


def core_scope(cfg, category: str) -> list[str]:
    return cfg["reddit"]["group_scope"][category]


def extended_scope(cfg, category: str) -> list[str]:
    return cfg["reddit"]["extended_group_scope"][category]


def hn_query(q: str) -> str:
    """Algolia form: each word quoted for exact-token matching ('"AI" "layoffs"')."""
    return " ".join(f'"{w}"' for w in q.split())


def pullpush_query(q: str) -> str:
    """PullPush AND-matches whitespace-separated terms; canonical form is fine."""
    return q


def mediacloud_group_query(terms: list[str]) -> str:
    """OR of quoted phrases for one query group."""
    return "(" + " OR ".join(f'"{t}"' for t in terms) + ")"


def event_windows(cfg) -> list[dict]:
    """Events with parsed dates + epoch bounds: [{name, start, end, start_i, end_i, terms}]."""
    out = []
    for ev in cfg["events"]:
        start = date.fromisoformat(ev["window"][0])
        end = date.fromisoformat(ev["window"][1])
        out.append({
            "name": ev["name"],
            "start": start, "end": end,
            "start_i": epoch(start), "end_i": epoch(end) + 86400,
            "terms": ev["terms"],
        })
    return out
