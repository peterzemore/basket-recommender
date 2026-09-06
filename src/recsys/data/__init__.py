"""Data pipeline: pull (needs credentials) -> clean -> anonymize -> public snapshot.

Everything downstream of `pull` runs from `data/public/` with no credentials, which is
what lets a reviewer reproduce the evaluation from a clean clone.
"""
import json
from pathlib import Path
from typing import Iterable, Iterator

ROOT = Path(__file__).resolve().parents[3]
RAW_DIR = ROOT / "data" / "raw"
PUBLIC_DIR = ROOT / "data" / "public"


def read_jsonl(path: Path) -> Iterator[dict]:
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                yield json.loads(line)


def write_jsonl(path: Path, rows: Iterable[dict]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with open(path, "w") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            n += 1
    return n


def load_env_file(path: Path) -> dict[str, str]:
    """Minimal KEY=VALUE parser so `pull` doesn't need python-dotenv. Quotes stripped,
    blank lines and comments ignored. Values never get logged."""
    env: dict[str, str] = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip().strip("'\"")
    return env
