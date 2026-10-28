import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import review_status as rs  # noqa: E402

TERMS = rs.load_terms()
CAL = next(t for t in TERMS if t["calibration"])
OTHER = next(t for t in TERMS if not t["calibration"])


def body(term, field="Law", eu="0 – Specifically regulated", fr="Don't know", us="Don't know",
         credit=rs.CREDIT_YES, verdict="Yes, keep it as it is"):
    return (
        f"### Term\n\n{term}\n\n### Should this term be in the glossary?\n\n{verdict}\n\n"
        f"### Your field\n\n{field}\n\n### EU: how much law covers this term?\n\n{eu}\n\n"
        f"### France: how much law covers this term?\n\n{fr}\n\n"
        f"### US (federal and state): how much law covers this term?\n\n{us}\n\n"
        "### Timing of the rules\n\nRules apply today\n\n"
        "### Does the legal definition match how the technology works?\n\nPartly matches\n\n"
        "### Your assessment\n\n_No response_\n\n"
        f"### List me as a contributor\n\n{credit}\n\n### Licence\n\n- [x] I grant ...\n"
    )


def issue(n, login, term, created="2026-11-01T10:00:00Z", **kw):
    return {"number": n, "user": {"login": login}, "created_at": created, "labels": [],
            "body": body(term, **kw)}


class ReviewStatus(unittest.TestCase):
    def test_labels_match_issue_form(self):
        yml = (ROOT / ".github" / "ISSUE_TEMPLATE" / "assess-term.yml").read_text(encoding="utf-8")
        for label in rs.ALL_LABELS:
            self.assertIn(f'label: "{label}"', yml)

    def test_parse_scores_and_choices(self):
        recs = rs.build([issue(1, "ana", CAL["term"], eu="2 – Only general rules apply (indirect)",
                               fr="n/a – Technical term, no legal framework needed")], TERMS)
        self.assertEqual(len(recs), 1)
        r = recs[0]
        self.assertEqual(r["cov"], {"eu": 2, "fr": "na", "us": None})
        self.assertEqual(r["fit"], "Partly matches")
        self.assertTrue(r["listed"])

    def test_latest_assessment_per_reviewer_and_term(self):
        recs = rs.build([
            issue(1, "ana", CAL["term"], created="2026-11-01T10:00:00Z", eu="3 – No legal framework"),
            issue(2, "Ana", CAL["term"], created="2026-11-02T10:00:00Z", eu="1 – Regulated in part only"),
        ], TERMS)
        self.assertEqual(len(recs), 1)
        self.assertEqual(recs[0]["cov"]["eu"], 1)

    def test_untrusted_input_is_ignored(self):
        bad_term = issue(1, "ana", "# injected | term")
        bad_login = issue(2, "x\n- [evil](http://x)", CAL["term"])
        pr = issue(3, "bob", CAL["term"])
        pr["pull_request"] = {}
        invalid = issue(4, "cy", CAL["term"])
        invalid["labels"] = [{"name": "invalid"}]
        not_assessment = {"number": 5, "user": {"login": "dee"}, "body": "hello", "labels": []}
        self.assertEqual(rs.build([bad_term, bad_login, pr, invalid, not_assessment], TERMS), [])

    def test_status_hides_scores_and_tracks_coverage(self):
        issues = [
            issue(1, "ana", CAL["term"], field="Law", eu="2 – Only general rules apply (indirect)"),
            issue(2, "bo", CAL["term"], field="Software engineering", eu="0 – Specifically regulated"),
        ]
        out = rs.render_status(rs.build(issues, TERMS), TERMS)
        self.assertIn("1 more; needs Machine learning or AI research", out)
        self.assertNotIn("Specifically regulated", out)
        self.assertNotIn("EU", out.split("## Terms that need reviewers")[1])

    def test_extended_terms_are_tracked_separately(self):
        ext = next(t for t in TERMS if t["extended"])
        core = [t for t in TERMS if not t["extended"]]
        self.assertGreater(len(core), 0)
        self.assertFalse(ext["calibration"])
        out = rs.render_status(rs.build([], TERMS), TERMS)
        self.assertIn(f"Core terms fully covered", out)
        self.assertIn("Extended terms (Part K) fully covered", out)
        # core terms are listed before extended ones in the to-do table
        todo = out.split("## Terms that need reviewers")[1].split("## All terms")[0]
        self.assertLess(todo.index(f"| {core[0]['id']} |"), todo.index(f"| {ext['id']} |"))

    def test_term_is_covered_with_three_fields(self):
        issues = [issue(i, n, OTHER["term"], field=f) for i, (n, f) in enumerate(
            [("a", "Law"), ("b", "Machine learning or AI research"), ("c", "Software engineering")], 1)]
        recs = rs.build(issues, TERMS)
        self.assertEqual(rs.needs([r for r in recs]), (0, []))

    def test_results_flag_split_and_agreement(self):
        issues = [
            issue(1, "a", CAL["term"], eu="0 – Specifically regulated"),
            issue(2, "b", CAL["term"], eu="3 – No legal framework"),
            issue(3, "c", CAL["term"], eu="3 – No legal framework"),
        ]
        out = rs.render_results(rs.build(issues, TERMS), TERMS)
        self.assertIn("3 (n=3) ⚠ split", out)
        self.assertRegex(out, r"\| EU \| 3 \| 33% \| 33% \|")

    def test_contributors_respect_opt_out_and_have_no_counts(self):
        issues = [
            issue(1, "zed", CAL["term"]),
            issue(2, "ana", CAL["term"]),
            issue(3, "ana", OTHER["term"]),
            issue(4, "hidden", CAL["term"], credit="No, keep me off the list"),
        ]
        out = rs.render_contributors(rs.build(issues, TERMS))
        self.assertNotIn("hidden", out)
        self.assertLess(out.index("ana"), out.index("zed"))
        self.assertFalse(re.search(r"\d", out.split("ranking.")[1]))


if __name__ == "__main__":
    unittest.main()
