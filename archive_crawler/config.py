"""User-defined "databases" (venues) the crawler can target.

A *database* is a named, reusable target: which backend to query and which
venue to scope to. Definitions live in a YAML (or JSON) file so you can add your
own without touching code. See ``databases.yaml`` for the shipped examples
(ACM CHI, UIST, CSCW, ...).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Optional

try:
    import yaml
except ImportError:  # pragma: no cover - yaml is listed in requirements.
    yaml = None  # type: ignore[assignment]

DEFAULT_CONFIG_PATH = os.path.join(os.path.dirname(__file__), os.pardir, "databases.yaml")


@dataclass
class Database:
    """A named crawl target."""

    key: str
    label: str
    source: str = "openalex"
    venue: Optional[str] = None
    # Optional per-database defaults.
    default_query: Optional[str] = None
    year_from: Optional[int] = None
    year_to: Optional[int] = None
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, key: str, data: dict[str, Any]) -> "Database":
        known = {"label", "source", "venue", "default_query", "year_from", "year_to"}
        return cls(
            key=key,
            label=data.get("label", key),
            source=data.get("source", "openalex"),
            venue=data.get("venue"),
            default_query=data.get("default_query"),
            year_from=data.get("year_from"),
            year_to=data.get("year_to"),
            extra={k: v for k, v in data.items() if k not in known},
        )


def _load_raw(path: str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as fh:
        if path.endswith(".json"):
            return json.load(fh)
        if yaml is None:
            raise RuntimeError(
                "PyYAML is required to read YAML config. Install with: pip install pyyaml"
            )
        return yaml.safe_load(fh) or {}


def load_databases(path: Optional[str] = None) -> dict[str, Database]:
    """Load all database definitions from ``path`` (defaults to databases.yaml)."""
    path = path or DEFAULT_CONFIG_PATH
    raw = _load_raw(path)
    entries = raw.get("databases", raw)  # allow a bare mapping too
    return {key: Database.from_dict(key, val) for key, val in entries.items()}


def get_database(name: str, path: Optional[str] = None) -> Database:
    """Resolve a database by its key or (case-insensitive) label."""
    dbs = load_databases(path)
    if name in dbs:
        return dbs[name]
    lowered = name.lower()
    for db in dbs.values():
        if db.label.lower() == lowered or db.key.lower() == lowered:
            return db
    available = ", ".join(sorted(dbs))
    raise KeyError(f"Unknown database {name!r}. Defined: {available}")
