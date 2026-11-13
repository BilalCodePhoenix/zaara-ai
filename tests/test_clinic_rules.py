"""
tests/test_clinic_rules.py

Checks that the BACKEND enforces the clinic rules, so they hold even if
the LLM forgets them. Read-only: it only calls check_availability and
find_available_slots, nothing is written to the database.

Run:  python -m pytest tests/test_clinic_rules.py -v
"""

from datetime import date, timedelta

from app.services.appointment_service import (
    check_availability,
    find_available_slots,
)

DOCTOR_ID = 1  # any active doctor id from your doctors table


def next_weekday(weekday):
    """Next date (after today) that falls on weekday. Mon=0 ... Sun=6."""
    today = date.today()
    return today + timedelta(days=(weekday - today.weekday()) % 7 or 7)


def test_inside_hours_on_a_weekday_can_be_available():
    # Sanity check so the other tests are meaningful.
    assert check_availability(DOCTOR_ID, next_weekday(2), "11:00") is True


def test_before_opening_is_not_available():
    assert check_availability(DOCTOR_ID, next_weekday(2), "08:30") is False


def test_at_closing_time_is_not_available():
    assert check_availability(DOCTOR_ID, next_weekday(2), "18:00") is False


def test_evening_is_not_available():
    assert check_availability(DOCTOR_ID, next_weekday(2), "21:00") is False


def test_sunday_is_never_available():
    assert check_availability(DOCTOR_ID, next_weekday(6), "11:00") is False


def test_no_alternative_slots_offered_on_sunday():
    assert find_available_slots(DOCTOR_ID, next_weekday(6), "11:00") == []


def test_past_date_is_not_available():
    yesterday = date.today() - timedelta(days=1)
    assert check_availability(DOCTOR_ID, yesterday, "11:00") is False