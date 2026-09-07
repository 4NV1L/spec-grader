import importlib.util
import json
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("spec_grade", ROOT / "scripts" / "spec_grade.py")
mod = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(mod)


class GradeTests(unittest.TestCase):
    def setUp(self):
        self.rubric = json.loads((ROOT / "config" / "rubric.json").read_text())
        self.obs = json.loads((ROOT / "tests" / "fixtures" / "evaluator_response.json").read_text())

    def test_weights_total_100(self):
        self.assertEqual(sum(c["weight"] for c in self.rubric["categories"]), 100)

    def test_deterministic_snapshot(self):
        report = mod.grade_observations(self.obs, self.rubric, "fixture.md", "2026-01-01T00:00:00+00:00")
        self.assertEqual((report["raw_score"], report["score"], report["grade"], report["verdict"]), (34.75, 35, "F", "NOT-READY"))
        self.assertEqual(report["autonomous_implementation_confidence"], 18)
        self.assertEqual([g["id"] for g in report["gate_failures"]], ["security_unaddressed"])
        self.assertEqual(report["score_improvement_plan"][0]["category"], "security_privacy")
        self.assertTrue(report["score_improvement_plan"][0]["clears_gate"])
        self.assertEqual(report["score_improvement_plan"][0]["potential_point_gain"], 1.75)

    def test_missing_category_rejected(self):
        self.obs["categories"].pop()
        with self.assertRaises(mod.GradeError): mod.grade_observations(self.obs, self.rubric, "fixture.md")

    def test_gate_caps_high_raw_score(self):
        for c in self.obs["categories"]: c["rating"] = 4
        next(c for c in self.obs["categories"] if c["id"] == "acceptance_criteria")["rating"] = 1
        self.obs["issues"] = []
        report = mod.grade_observations(self.obs, self.rubric, "fixture.md")
        self.assertEqual(report["score"], 59)
        self.assertEqual(report["verdict"], "NOT-READY")

    def test_improvement_contract(self):
        value = json.loads((ROOT / "tests" / "fixtures" / "improvement_response.json").read_text())
        mod.validate_improvement(value, self.rubric)
        value["changes"][0]["source"] = "invented-fact"
        with self.assertRaises(mod.GradeError): mod.validate_improvement(value, self.rubric)


if __name__ == "__main__": unittest.main()
