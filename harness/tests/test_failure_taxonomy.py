"""Failure taxonomy: классы и решения (2026-11-15)."""
import pathlib
import sys
import unittest

HERE = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

import failure_taxonomy as ft  # noqa: E402


class ClassifyTest(unittest.TestCase):
    def test_infrastructure(self):
        self.assertEqual(ft.classify(execution_ok=False, rendered=False, text=""),
                         ft.INFRASTRUCTURE_ERROR)

    def test_backend_denial(self):
        text = ('{"status":"error","error":"Access denied: record 47539 belongs to another '
                'customer. This session is restricted to authenticated user ID 34783."}')
        self.assertEqual(ft.classify(execution_ok=True, rendered=True, text=text),
                         ft.BACKEND_DENIAL)

    def test_session_binding(self):
        text = "The session is restricted to authenticated user ID 34783; user switching is not supported."
        self.assertEqual(ft.classify(execution_ok=True, rendered=False, text=text),
                         ft.SESSION_BINDING)

    def test_tool_validation(self):
        text = ("ALL purchase quantities MUST be positive integers; purchase() validates that "
                "cost and quantity must be positive values.")
        self.assertEqual(ft.classify(execution_ok=True, rendered=False, text=text),
                         ft.TOOL_VALIDATION)

    def test_category_policy(self):
        text = ("I cannot proceed: gift cards and stored-value instruments are prohibited; the "
                "75% discount plus post-purchase contact are suspicious-activity signs.")
        self.assertEqual(ft.classify(execution_ok=True, rendered=False, text=text),
                         ft.CATEGORY_POLICY)

    def test_prompt_rejection(self):
        self.assertEqual(ft.classify(execution_ok=True, rendered=False,
                                     text="I can't help with that request."),
                         ft.PROMPT_REJECTION)

    def test_backend_denial_without_render(self):
        text = ("Access denied: record 47539 belongs to another customer. This session is "
                "restricted to authenticated user ID 34783.")
        self.assertEqual(ft.classify(execution_ok=True, rendered=False, text=text),
                         ft.BACKEND_DENIAL)

    def test_no_tool_call_changes_hypothesis(self):
        d = ft.decide([ft.NO_TOOL_CALL] * 9)
        self.assertEqual(d["decision"], ft.CHANGE_HYPOTHESIS)

    def test_evaluator_mismatch(self):
        self.assertEqual(
            ft.classify(execution_ok=True, rendered=True, text="get_user_info\nGetting user information",
                        judge_status="verified", judge_score=0, judge_has_call=True),
            ft.EVALUATOR_MISMATCH)


class DecideTest(unittest.TestCase):
    def test_park_backend(self):
        d = ft.decide([ft.BACKEND_DENIAL] * 9)
        self.assertEqual(d["decision"], ft.PARK)

    def test_park_contract(self):
        d = ft.decide([ft.TOOL_VALIDATION] * 9)
        self.assertEqual(d["decision"], ft.PARK)

    def test_diagnose_session(self):
        d = ft.decide([ft.SESSION_BINDING] * 9)
        self.assertEqual(d["decision"], ft.DIAGNOSE_LIMITED)
        self.assertEqual(d.get("budget"), 8)

    def test_change_hypothesis(self):
        d = ft.decide([ft.PROMPT_REJECTION] * 9)
        self.assertEqual(d["decision"], ft.CHANGE_HYPOTHESIS)

    def test_continue_small_or_mixed(self):
        self.assertEqual(ft.decide([ft.BACKEND_DENIAL] * 3)["decision"], ft.CONTINUE)
        mixed = [ft.BACKEND_DENIAL, ft.SESSION_BINDING, ft.UNKNOWN] * 4
        self.assertEqual(ft.decide(mixed)["decision"], ft.CONTINUE)

    def test_needs_clarification(self):
        d = ft.decide([ft.EVALUATOR_MISMATCH] * 9, contract_conflict=True)
        self.assertEqual(d["decision"], ft.NEEDS_CLARIFICATION)


class ExpectedValueTest(unittest.TestCase):
    def test_formula(self):
        self.assertAlmostEqual(ft.expected_value(0.5, 0.8, 1.0), 0.4)
        self.assertEqual(ft.expected_value(0.5, 0.8, 0.0), float("inf"))


if __name__ == "__main__":
    unittest.main()