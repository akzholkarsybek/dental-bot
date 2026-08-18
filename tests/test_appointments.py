from datetime import datetime
from unittest.mock import patch

from appointments import (
    CLINIC_TIMES,
    get_available_times,
)


def test_all_clinic_times():
    assert CLINIC_TIMES == [
        "09:00",
        "10:00",
        "11:00",
        "13:00",
        "14:00",
        "16:00",
        "17:00",
    ]


def test_past_date_has_no_available_times():
    with patch("appointments.get_current_datetime") as mock_now:
        mock_now.return_value = datetime(
            2026,
            8,
            16,
            12,
            0,
        )

        result = get_available_times(
            "2026-08-15"
        )

        assert result == []


def test_tomorrow_has_all_times():
    with patch("appointments.get_current_datetime") as mock_now:
        mock_now.return_value = datetime(
            2026,
            8,
            16,
            12,
            0,
        )

        result = get_available_times(
            "2026-08-17"
        )

        assert result == [
            "09:00",
            "10:00",
            "11:00",
            "13:00",
            "14:00",
            "16:00",
            "17:00",
        ]


def test_afternoon_only():
    with patch("appointments.get_current_datetime") as mock_now:
        mock_now.return_value = datetime(
            2026,
            8,
            16,
            12,
            0,
        )

        result = get_available_times(
            "2026-08-17",
            requested_period="afternoon",
        )

        assert result == [
            "13:00",
            "14:00",
            "16:00",
            "17:00",
        ]


def test_morning_only():
    with patch("appointments.get_current_datetime") as mock_now:
        mock_now.return_value = datetime(
            2026,
            8,
            16,
            12,
            0,
        )

        result = get_available_times(
            "2026-08-17",
            requested_period="morning",
        )

        assert result == [
            "09:00",
            "10:00",
            "11:00",
        ]


def test_today_removes_past_times():
    with patch("appointments.get_current_datetime") as mock_now:
        mock_now.return_value = datetime(
            2026,
            8,
            16,
            14,
            30,
        )

        result = get_available_times(
            "2026-08-16"
        )

        assert result == [
            "16:00",
            "17:00",
        ]


def test_today_afternoon_removes_past_times():
    with patch("appointments.get_current_datetime") as mock_now:
        mock_now.return_value = datetime(
            2026,
            8,
            16,
            14,
            30,
        )

        result = get_available_times(
            "2026-08-16",
            requested_period="afternoon",
        )

        assert result == [
            "16:00",
            "17:00",
        ]