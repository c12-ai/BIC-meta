from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


KIT_DIR = Path(__file__).resolve().parents[1]
EVAL_DIR = KIT_DIR / "evals"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


FIXTURES = load_module("bic_quality_eval_fixtures", EVAL_DIR / "fixtures.py")
GRADER = load_module("bic_quality_eval_grader", EVAL_DIR / "grade_agent_eval.py")


class AgentEvalHarnessTest(unittest.TestCase):
    def test_cases_are_unique_and_define_both_baselines_for_comparisons(self) -> None:
        config = json.loads((EVAL_DIR / "cases.json").read_text(encoding="utf-8"))
        ids = [case["id"] for case in config["cases"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertNotIn("old_skill", {mode for case in config["cases"] for mode in case["modes"]})
        for case in config["cases"]:
            self.assertTrue(case["prompt"].strip())
            self.assertTrue(set(case["modes"]) <= {"with_skill", "no_skill"})
            self.assertEqual(set(case["modes"]), set(case["expected_assess_calls"]))
            if "no_skill" in case["modes"]:
                self.assertIn("with_skill", case["modes"])

    def test_fixture_only_installs_skill_in_with_skill_mode(self) -> None:
        skill_source = KIT_DIR / "skill/bic-quality-guan-ping-ce"
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with_skill = root / "with/BIC-meta"
            no_skill = root / "without/BIC-meta"
            FIXTURES.build_fixture(with_skill, "resolved_issue", "with_skill", skill_source)
            FIXTURES.build_fixture(no_skill, "resolved_issue", "no_skill", skill_source)
            self.assertTrue((with_skill / ".agents/skills/bic-quality-guan-ping-ce/SKILL.md").is_file())
            self.assertFalse((no_skill / ".agents/skills/bic-quality-guan-ping-ce").exists())
            with_diff = FIXTURES._git(with_skill / "BIC-agent-service", "diff", "main...HEAD")
            without_diff = FIXTURES._git(no_skill / "BIC-agent-service", "diff", "main...HEAD")
            self.assertEqual(with_diff, without_diff)

    def test_fixture_rejects_missing_skill_source_in_with_skill_mode(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            missing_skill = root / "missing-skill"
            with self.assertRaisesRegex(FileNotFoundError, "missing SKILL.md"):
                FIXTURES.build_fixture(
                    root / "with/BIC-meta",
                    "resolved_issue",
                    "with_skill",
                    missing_skill,
                )

    def test_grader_deduplicates_command_events_and_gates_only_with_skill(self) -> None:
        case = {
            "id": "fixture",
            "expected_assess_calls": {"with_skill": 1},
            "facts": [{"id": "warning", "any": ["scan-failed"]}],
        }
        with tempfile.TemporaryDirectory() as temp:
            run_dir = Path(temp)
            event = {
                "type": "item.completed",
                "item": {
                    "id": "cmd-1",
                    "type": "command_execution",
                    "command": ".agents/skills/bic-quality-guan-ping-ce/scripts/assess-risk-matrix.sh",
                    "exit_code": 0,
                    "status": "completed",
                },
            }
            (run_dir / "events.jsonl").write_text(
                json.dumps({**event, "type": "item.started"}) + "\n" + json.dumps(event) + "\n",
                encoding="utf-8",
            )
            (run_dir / "final.md").write_text("Issue scan-failed; risk is unassessed.", encoding="utf-8")
            (run_dir / "run.json").write_text(
                json.dumps({
                    "case": case,
                    "mode": "with_skill",
                    "repetition": 1,
                    "exit_code": 0,
                    "duration_seconds": 1.0,
                    "forbidden_commands": ["pytest"],
                }),
                encoding="utf-8",
            )
            result = GRADER.grade_run(run_dir)
            self.assertEqual(result["assess_calls"], 1)
            self.assertTrue(result["gate_passed"])

    def test_grader_does_not_count_filename_search_as_assessment(self) -> None:
        self.assertFalse(GRADER.is_assessment_invocation("find .. -name assess-risk-matrix.sh"))
        self.assertFalse(GRADER.is_assessment_invocation("rg --files -g assess-risk-matrix.sh"))
        self.assertFalse(GRADER.is_assessment_invocation(
            "sed -n '1,220p' .agents/skills/x/scripts/assess-risk-matrix.sh"
        ))
        self.assertTrue(GRADER.is_assessment_invocation(".agents/skills/x/scripts/assess-risk-matrix.sh"))
        self.assertTrue(GRADER.is_assessment_invocation(
            "PATH=/tmp/bin:$PATH .agents/skills/x/scripts/assess-risk-matrix.sh"
        ))
        self.assertTrue(GRADER.is_assessment_invocation(
            "bash .agents/skills/x/scripts/assess-risk-matrix.sh"
        ))

    def test_forbidden_operations_distinguish_searches_from_execution(self) -> None:
        self.assertIsNone(GRADER.forbidden_operation("find . -name pytest.ini"))
        self.assertIsNone(GRADER.forbidden_operation("rg -n pytest pyproject.toml"))
        self.assertIsNone(GRADER.forbidden_operation(
            "/bin/zsh -lc 'rg -n \"(test|pytest|unittest)\" -S .'"
        ))
        self.assertEqual(GRADER.forbidden_operation("python -m pytest tests/unit"), "pytest")
        self.assertEqual(
            GRADER.forbidden_operation(
                "/bin/zsh -lc 'cd BIC-agent-service && python -m pytest tests/unit'"
            ),
            "pytest",
        )
        self.assertEqual(GRADER.forbidden_operation("git -C repo fetch origin"), "git fetch")

    def test_grouped_fact_matching_requires_each_semantic_group(self) -> None:
        fact = {
            "id": "no-shared-chain",
            "all_of_any": [
                ["不能证明", "无法证明", "不足以证明", "不足以说明", "未确认"],
                ["业务链", "业务流", "business chain", "business stream"],
            ],
        }
        self.assertTrue(GRADER.matches_fact(
            "现有证据不足以证明两个仓库属于同一业务链。",
            fact,
        ))
        self.assertTrue(GRADER.matches_fact(
            "当前证据不足以说明两个仓库属于同一业务链。",
            fact,
        ))
        self.assertFalse(GRADER.matches_fact("当前测试证据不足，需要补充断言。", fact))

    def test_grader_accepts_real_eval_wording_and_quoted_search_trace(self) -> None:
        case = {
            "id": "real-eval-regression",
            "expected_assess_calls": {"with_skill": 0},
            "facts": [{
                "id": "no-shared-chain",
                "all_of_any": [
                    ["不足以证明", "不足以说明"],
                    ["业务链", "业务流"],
                ],
            }],
        }
        with tempfile.TemporaryDirectory() as temp:
            run_dir = Path(temp)
            event = {
                "type": "item.completed",
                "item": {
                    "id": "cmd-1",
                    "type": "command_execution",
                    "command": "/bin/zsh -lc 'rg -n \"(test|pytest|unittest)\" -S .'",
                    "exit_code": 0,
                    "status": "completed",
                },
            }
            (run_dir / "events.jsonl").write_text(json.dumps(event) + "\n", encoding="utf-8")
            (run_dir / "final.md").write_text(
                "现有证据不足以证明两个仓库属于同一业务链。",
                encoding="utf-8",
            )
            (run_dir / "run.json").write_text(
                json.dumps({
                    "case": case,
                    "mode": "with_skill",
                    "repetition": 1,
                    "exit_code": 0,
                    "duration_seconds": 1.0,
                    "forbidden_commands": ["pytest"],
                }),
                encoding="utf-8",
            )
            result = GRADER.grade_run(run_dir)
            self.assertEqual(result["fact_score"], 1.0)
            self.assertEqual(result["command_violations"], [])
            self.assertTrue(result["gate_passed"])

    def test_stability_compares_normalized_fact_sets(self) -> None:
        runs = [
            {"stability_group": "same", "mode": "with_skill", "observed_fact_ids": ["repo", "issue"]},
            {"stability_group": "same", "mode": "with_skill", "observed_fact_ids": ["repo"]},
        ]
        stability = GRADER.stability_results(runs)
        self.assertEqual(stability[0]["fact_set_consistency"], 0.5)
        self.assertEqual(stability[0]["varying_fact_ids"], ["issue"])


if __name__ == "__main__":
    unittest.main()
