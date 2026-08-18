from datetime import date, time
from unittest.mock import MagicMock, patch

from appointment_management import (
    get_customer_appointments,
    cancel_appointment,
)


CUSTOMER_ID = 91


def make_connection(cursor):
    connection = MagicMock()

    connection.cursor.return_value.__enter__.return_value = cursor

    return connection


def test_get_customer_appointments():
    cursor = MagicMock()

    cursor.fetchall.return_value = [
        (
            8,
            "Dental Consultation",
            date(2026, 8, 17),
            time(11, 0),
        ),
        (
            11,
            "Dental Filling",
            date(2026, 8, 18),
            time(9, 0),
        ),
    ]

    connection = make_connection(cursor)

    with patch(
        "appointment_management.get_connection",
        return_value=connection,
    ):
        result = get_customer_appointments(
            CUSTOMER_ID
        )

    assert result == [
        {
            "appointment_id": 8,
            "service": "Dental Consultation",
            "date": "2026-08-17",
            "time": "11:00",
        },
        {
            "appointment_id": 11,
            "service": "Dental Filling",
            "date": "2026-08-18",
            "time": "09:00",
        },
    ]


def test_cancel_appointment_success():
    cursor = MagicMock()

    cursor.fetchone.return_value = (
        11,
        "Dental Filling",
        date(2026, 8, 18),
        time(9, 0),
    )

    connection = make_connection(cursor)

    with patch(
        "appointment_management.get_connection",
        return_value=connection,
    ):
        result = cancel_appointment(
            customer_id=CUSTOMER_ID,
            appointment_id=11,
        )

    assert result["success"] is True
    assert result["appointment_id"] == 11
    assert result["service"] == "Dental Filling"
    assert result["date"] == "2026-08-18"
    assert result["time"] == "09:00"

    connection.commit.assert_called_once()


def test_cancel_nonexistent_appointment():
    cursor = MagicMock()

    cursor.fetchone.return_value = None

    connection = make_connection(cursor)

    with patch(
        "appointment_management.get_connection",
        return_value=connection,
    ):
        result = cancel_appointment(
            customer_id=CUSTOMER_ID,
            appointment_id=999,
        )

    assert result["success"] is False
    assert "not found" in result["message"].lower()


def test_customer_cannot_cancel_other_customer_appointment():
    cursor = MagicMock()

    # Database query includes customer_id,
    # so an appointment belonging to someone else
    # should not be returned.
    cursor.fetchone.return_value = None

    connection = make_connection(cursor)

    with patch(
        "appointment_management.get_connection",
        return_value=connection,
    ):
        result = cancel_appointment(
            customer_id=CUSTOMER_ID,
            appointment_id=999,
        )

    assert result["success"] is False