#!/usr/bin/env python3

import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TERMS_DIR = ROOT / "data" / "terms"
OUTPUT_FILE = ROOT / "docs" / "glossary.csv"

FIELDNAMES = [
    "term",
    "jurisdiction",
    "category",
    "definition",
    "status",
    "source_url",
]

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n(.*)$", re.DOTALL)


def parse_front_matter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    match = FRONTMATTER_RE.match(text)

    data = {
        "term": path.stem.replace("-", " ").title(),
        "jurisdiction": "",
        "category": "",
        "definition": "",
        "status": "",
        "source_url": "",
    }

    if not match:
        return data

    frontmatter = match.group(1)
    body = match.group(2).strip()

    for line in frontmatter.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        data[key.strip().lower()] = value.strip().strip('"')

    if body and not data.get("definition"):
        data["definition"] = body.splitlines()[0].strip()

    return data


def build_glossary() -> list[dict]:
    rows = []
    for path in sorted(TERMS_DIR.glob("*.md")):
        if path.name == "README.md":
            continue
        row = parse_front_matter(path)
        rows.append({
            "term": row.get("term", path.stem.replace("-", " ").title()),
            "jurisdiction": row.get("jurisdiction", ""),
            "category": row.get("category", ""),
            "definition": row.get("definition", ""),
            "status": row.get("status", ""),
            "source_url": row.get("source_url", ""),
        })
    return rows


def main() -> None:
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    rows = build_glossary()

    with OUTPUT_FILE.open("w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=FIELDNAMES)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    print(f"Wrote {len(rows)} glossary entries to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
