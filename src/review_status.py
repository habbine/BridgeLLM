#!/usr/bin/env python3
"""Count assessments per term and write the review dashboards.

Outputs (in assessment/):
  STATUS.md        which terms still need reviewers (no scores, so reviewers are not primed)
  CONTRIBUTORS.md  people who opted in, alphabetical, no ranking
  RESULTS.md       scores, disagreement and calibration agreement (only with --reveal)

Standard library only. Issue text is treated as data: only canonical terms and
fixed answer values are read from it; free text is never copied into the outputs.
"""

import argparse
import csv
import json
import os
import re
import statistics
import sys
import urllib.request
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assessment"
REPO = "habbine/ai-legal-glossary"
TARGET = 3  # independent assessments wanted per term

# Labels must match .github/ISSUE_TEMPLATE/assess-term.yml (a test checks this).
L_TERM = "Term"
L_VERDICT = "Should this term be in the glossary?"
L_FIELD = "Your field"
L_COV = {
    "eu": "EU: how much law covers this term?",
    "fr": "France: how much law covers this term?",
    "us": "US (federal and state): how much law covers this term?",
}
L_TIMING = "Timing of the rules"
L_FIT = "Does the legal definition match how the technology works?"
L_CREDIT = "List me as a contributor"
ALL_LABELS = [L_TERM, L_VERDICT, L_FIELD, *L_COV.values(), L_TIMING, L_FIT, L_CREDIT]

VERDICTS = [
    "Yes, keep it as it is",
    "Yes, but rename it",
    "Yes, but merge it with another term",
    "Yes, but split it into several terms",
    "No, remove it",
    "Not sure",
]
FIELDS = [
    "Law",
    "Machine learning or AI research",
    "Software engineering",
    "Policy or regulation",
    "Other",
]
CORE_FIELDS = FIELDS[:3]
TIMINGS = [
    "Rules apply today",
    "Rules adopted but not yet applicable",
    "Only proposed",
    "Mixed across jurisdictions (explain below)",
    "n/a",
]
FITS = ["Matches", "Partly matches", "Does not match", "No legal definition exists"]
CREDIT_YES = "Yes, list my GitHub username"
JURIS = {"eu": "EU", "fr": "France", "us": "US"}
LOGIN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9-]{0,38}")


def load_terms(path=None):
    path = path or OUT / "terms.csv"
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["id"] = int(r["id"])
        r["calibration"] = r["calibration"] == "yes"
    return rows


def sections(body):
    """Split a rendered issue-form body into {label: answer}."""
    out = {}
    parts = re.split(r"^### (.+?)\s*$", body or "", flags=re.M)
    for i in range(1, len(parts) - 1, 2):
        out[parts[i].strip()] = parts[i + 1].strip()
    return out


def score(value):
    """0-3 as int, 'na' for n/a, None for unknown/blank."""
    v = (value or "").strip()
    m = re.match(r"^([0-3])\b", v)
    if m:
        return int(m.group(1))
    if v.lower().startswith("n/a"):
        return "na"
    return None


def choice(value, allowed):
    v = (value or "").strip()
    return v if v in allowed else None


def parse_issue(issue, terms_by_name):
    """Return one assessment record, or None if the issue is not a valid assessment."""
    if "pull_request" in issue:
        return None
    if any(l.get("name") == "invalid" for l in issue.get("labels", [])):
        return None
    s = sections(issue.get("body"))
    if L_TERM not in s or L_VERDICT not in s:
        return None
    term = terms_by_name.get(s[L_TERM])
    if term is None:
        print(f"skip #{issue.get('number')}: unknown term", file=sys.stderr)
        return None
    login = (issue.get("user") or {}).get("login") or ""
    if not LOGIN_RE.fullmatch(login):
        print(f"skip #{issue.get('number')}: unusable login", file=sys.stderr)
        return None
    return {
        "login": login,
        "term_id": term["id"],
        "created": issue.get("created_at") or "",
        "verdict": choice(s.get(L_VERDICT), VERDICTS),
        "field": choice(s.get(L_FIELD), FIELDS),
        "cov": {k: score(s.get(lbl)) for k, lbl in L_COV.items()},
        "timing": choice(s.get(L_TIMING), TIMINGS),
        "fit": choice(s.get(L_FIT), FITS),
        "listed": (s.get(L_CREDIT) or "").strip() == CREDIT_YES,
    }


def build(issues, terms):
    """Parse issues; keep each reviewer's latest assessment per term."""
    by_name = {t["term"]: t for t in terms}
    latest = {}
    for issue in issues:
        rec = parse_issue(issue, by_name)
        if rec is None:
            continue
        key = (rec["login"].lower(), rec["term_id"])
        if key not in latest or rec["created"] > latest[key]["created"]:
            latest[key] = rec
    return list(latest.values())


def per_term(records):
    d = defaultdict(list)
    for r in records:
        d[r["term_id"]].append(r)
    return d


def needs(recs):
    covered = {r["field"] for r in recs if r["field"]}
    missing = [f for f in CORE_FIELDS if f not in covered]
    short = max(0, TARGET - len(recs))
    return short, missing


def render_status(records, terms):
    pt = per_term(records)
    reviewers = {r["login"].lower() for r in records}
    complete = sum(1 for t in terms if needs(pt[t["id"]]) == (0, []))
    empty = sum(1 for t in terms if not pt[t["id"]])
    cal = [t for t in terms if t["calibration"]]
    cal_done = sum(1 for t in cal if needs(pt[t["id"]]) == (0, []))

    L = ["# Review status", ""]
    L.append("Generated automatically. Scores are not shown here while the first pass is open, "
             "so they do not influence later reviewers.\n")
    L.append(f"- Reviewers so far: **{len(reviewers)}**")
    L.append(f"- Assessments: **{len(records)}**")
    L.append(f"- Terms fully covered (at least {TARGET} assessments, with law, machine learning and "
             f"software engineering all represented): **{complete} of {len(terms)}**")
    L.append(f"- Terms with no assessment yet: **{empty}**")
    L.append(f"- Phase 1 (★ calibration terms) fully covered: **{cal_done} of {len(cal)}**\n")

    def row(t):
        recs = pt[t["id"]]
        short, missing = needs(recs)
        covered = sorted({r["field"] for r in recs if r["field"]})
        star = " ★" if t["calibration"] else ""
        if not short and not missing:
            need = "✓ covered"
        else:
            bits = []
            if short:
                bits.append(f"{short} more")
            if missing:
                bits.append("needs " + ", ".join(missing))
            need = "; ".join(bits)
        return f"| {t['id']} | {t['term']}{star} | {len(recs)} | {', '.join(covered) or '–'} | {need} |"

    head = ["| # | Term | Assessments | Fields so far | Still needed |", "|--:|:--|--:|:--|:--|"]
    todo = [t for t in terms if needs(pt[t["id"]]) != (0, [])]
    todo.sort(key=lambda t: (not t["calibration"], len(pt[t["id"]]), t["id"]))
    L.append("## Terms that need reviewers\n")
    L += head + [row(t) for t in todo] if todo else ["Every term is covered."]
    L.append("\n## All terms\n")
    L += head + [row(t) for t in terms]
    return "\n".join(L) + "\n"


def render_contributors(records):
    people = defaultdict(set)
    for r in records:
        if r["listed"]:
            people[r["login"]].add(r["field"] or "Other")
    L = ["# Contributors", "",
         "People who assessed terms and chose to be listed, in alphabetical order. "
         "There is no ranking.", ""]
    for login in sorted(people, key=str.lower):
        L.append(f"- [{login}](https://github.com/{login}) — {', '.join(sorted(people[login]))}")
    if not people:
        L.append("No contributors listed yet.")
    return "\n".join(L) + "\n"


def fmt_median(vals):
    nums = [v for v in vals if isinstance(v, int)]
    if not nums:
        return "–"
    m = statistics.median(nums)
    m = int(m) if m == int(m) else m
    flag = " ⚠ split" if max(nums) - min(nums) >= 2 else ""
    return f"{m} (n={len(nums)}){flag}"


def dist(vals):
    c = Counter(v for v in vals if v)
    return ", ".join(f"{k} ×{n}" for k, n in c.most_common()) or "–"


def agreement(records, terms):
    """Pairwise agreement on 0-3 scores for calibration terms, per jurisdiction."""
    pt = per_term(records)
    out = {}
    for k in JURIS:
        exact = within1 = pairs = 0
        for t in terms:
            if not t["calibration"]:
                continue
            nums = [r["cov"][k] for r in pt[t["id"]] if isinstance(r["cov"][k], int)]
            for a, b in combinations(nums, 2):
                pairs += 1
                exact += a == b
                within1 += abs(a - b) <= 1
        out[k] = (pairs, exact, within1)
    return out


def render_results(records, terms):
    pt = per_term(records)
    L = ["# Results", "",
         "Generated automatically. Scores are ordinal, so the median is shown with the number of "
         "scores (n). **⚠ split** means the lowest and highest scores differ by 2 or more: "
         "that disagreement is itself a finding and is not averaged away.\n",
         "## Calibration agreement (★ terms)\n",
         "Share of reviewer pairs who gave the same score to the same term. Low agreement means the "
         "scoring guide needs clearer wording. Compute a formal reliability coefficient once there is "
         "enough data.\n",
         "| Jurisdiction | Reviewer pairs | Same score | Within 1 point |",
         "|:--|--:|--:|--:|"]
    for k, (pairs, exact, w1) in agreement(records, terms).items():
        pct = lambda x: f"{round(100 * x / pairs)}%" if pairs else "–"
        L.append(f"| {JURIS[k]} | {pairs} | {pct(exact)} | {pct(w1)} |")
    L += ["", "## Scores by term\n",
          "| # | Term | EU | France | US | Timing | Definition fit | Verdict |",
          "|--:|:--|:--|:--|:--|:--|:--|:--|"]
    for t in terms:
        recs = pt[t["id"]]
        if not recs:
            continue
        star = " ★" if t["calibration"] else ""
        L.append(
            f"| {t['id']} | {t['term']}{star} | "
            + " | ".join(fmt_median([r["cov"][k] for r in recs]) for k in JURIS)
            + f" | {dist(r['timing'] for r in recs)} | {dist(r['fit'] for r in recs)}"
            + f" | {dist(r['verdict'] for r in recs)} |"
        )
    return "\n".join(L) + "\n"


def fetch_issues(max_pages=50):
    items, page = [], 1
    while page <= max_pages:
        url = f"https://api.github.com/repos/{REPO}/issues?state=all&per_page=100&page={page}"
        req = urllib.request.Request(url, headers={
            "Accept": "application/vnd.github+json", "User-Agent": "review-status"})
        token = os.environ.get("GITHUB_TOKEN")
        if token:
            req.add_header("Authorization", f"Bearer {token}")
        with urllib.request.urlopen(req, timeout=30) as resp:
            batch = json.load(resp)
        if not batch:
            break
        items += batch
        page += 1
    return items


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--reveal", action="store_true", help="also write RESULTS.md (scores)")
    ap.add_argument("--issues-json", help="read issues from a JSON file instead of GitHub")
    args = ap.parse_args()

    terms = load_terms()
    if args.issues_json:
        issues = json.loads(Path(args.issues_json).read_text(encoding="utf-8"))
    else:
        issues = fetch_issues()
    records = build(issues, terms)

    (OUT / "STATUS.md").write_text(render_status(records, terms), encoding="utf-8")
    (OUT / "CONTRIBUTORS.md").write_text(render_contributors(records), encoding="utf-8")
    if args.reveal:
        (OUT / "RESULTS.md").write_text(render_results(records, terms), encoding="utf-8")
    print(f"{len(records)} assessments from {len({r['login'].lower() for r in records})} reviewers")


if __name__ == "__main__":
    main()
