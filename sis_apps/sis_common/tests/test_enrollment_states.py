"""Run without Django: python -m unittest sis_common.tests.test_enrollment_states."""

# ruff: noqa: PT027 -- Keep these tests runnable with the Python standard library only.

import unittest
from datetime import date

from sis_common.enrollment_states import transition_status, validate_enrollment_dates


class EnrollmentStateTests(unittest.TestCase):
    def test_suspend_resume_then_abandon_and_replays(self):
        state = transition_status("validee", "suspendre")
        assert state == "suspendue"
        with self.assertRaises(ValueError):
            transition_status(state, "suspendre")
        state = transition_status(state, "reprendre")
        assert state == "validee"
        with self.assertRaises(ValueError):
            transition_status(state, "reprendre")
        state = transition_status(state, "abandonner")
        assert state == "abandonnee"
        for operation in ("suspendre", "reprendre", "abandonner"):
            with self.subTest(operation=operation), self.assertRaises(ValueError):
                transition_status(state, operation)

    def test_only_approved_records_can_be_interrupted(self):
        for state in ("en_cours", "provisoire", "refusee", "annulee"):
            for operation in ("suspendre", "reprendre", "abandonner"):
                with self.subTest(state=state, operation=operation), self.assertRaises(ValueError):
                    transition_status(state, operation)
        assert transition_status("suspendue", "abandonner") == "abandonnee"

    def test_current_dates_are_inclusive_but_expired_year_never_reopens(self):
        start, end = date(2026, 9, 1), date(2027, 7, 1)
        for today in (start, end):
            validate_enrollment_dates(start, end, today, ongoing=True)
        validate_enrollment_dates(start, end, date(2026, 8, 1))
        with self.assertRaises(ValueError):
            validate_enrollment_dates(start, end, date(2026, 8, 1), ongoing=True)
        for ongoing in (False, True):
            with self.subTest(ongoing=ongoing), self.assertRaises(ValueError):
                validate_enrollment_dates(start, end, date(2027, 7, 2), ongoing=ongoing)
