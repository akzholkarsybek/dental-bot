from datetime import datetime, date, time
from unittest.mock import MagicMock, patch

from appointment_management import reschedule_appointment


CUSTOMER_ID = 91
APPOINTMENT_ID = 11
SERVICE_ID = 3


def make_connection(cursor):
    connection = MagicMock()
    connection.cursor.return_value.__enter__.return_value = cursor
    return connection


def test_invalid_date():
    result = reschedule_appointment(
        customer_id=CUSTOMER_ID,
        appointment_id=APPOINTMENT_ID,
        new_date="not-a-date",
        new_time="09:00",
    )

    assert result["success"] is False
    assert result["message"] == "Invalid appointment date."


def test_invalid_time():
    result = reschedule_appointment(
        customer_id=CUSTOMER_ID,
        appointment_id=APPOINTMENT_ID,
        new_date="2026-08-20",
        new_time="invalid",
    )

    assert result["success"] is False
    assert "invalid appointment time" in result["message"].lower()


def test_past_date():
    fake_now = datetime(2026, 8, 18, 12, 0)

    with patch(
        "appointment_management.get_current_datetime",
        return_value=fake_now,
    ):
        result = reschedule_appointment(
            customer_id=CUSTOMER_ID,
            appointment_id=APPOINTMENT_ID,
            new_date="2026-08-17",
            new_time="09:00",
        )

    assert result["success"] is False
    assert "past" in result["message"].lower()


def test_past_time_today():
    fake_now = datetime(2026, 8, 18, 14, 30)

    with patch(
        "appointment_management.get_current_datetime",
        return_value=fake_now,
    ):
        result = reschedule_appointment(
            customer_id=CUSTOMER_ID,
            appointment_id=APPOINTMENT_ID,
            new_date="2026-08-18",
            new_time="13:00",
        )

    assert result["success"] is False
    assert "already passed" in result["message"].lower()


def test_invalid_clinic_time():
    fake_now = datetime(2026, 8, 18, 12, 0)

    with patch(
        "appointment_management.get_current_datetime",
        return_value=fake_now,
    ):
        result = reschedule_appointment(
            customer_id=CUSTOMER_ID,
            appointment_id=APPOINTMENT_ID,
            new_date="2026-08-20",
            new_time="12:00",
        )

    assert result["success"] is False
    assert "not a valid clinic" in result["message"].lower()


def test_appointment_not_found():
    cursor = MagicMock()
    cursor.fetchone.return_value = None

    connection = make_connection(cursor)

    fake_now = datetime(2026, 8, 18, 12, 0)

    with patch(
        "appointment_management.get_current_datetime",
        return_value=fake_now,
    ):
        with patch(
            "appointment_management.get_connection",
            return_value=connection,
        ):
            result = reschedule_appointment(
                customer_id=CUSTOMER_ID,
                appointment_id=999,
                new_date="2026-08-20",
                new_time="09:00",
            )

    assert result["success"] is False
    assert "not found" in result["message"].lower()


def test_new_slot_already_booked():
    cursor = MagicMock()

    # First query finds the customer's appointment.
    cursor.fetchone.side_effect = [
        (
            APPOINTMENT_ID,
            SERVICE_ID,
            "Dental Filling",
            date(2026, 8, 18),
            time(9, 0),
        ),
        # Second query finds another appointment in the new slot.
        (20,),
    ]

    connection = make_connection(cursor)

    fake_now = datetime(2026, 8, 18, 12, 0)

    with patch(
        "appointment_management.get_current_datetime",
        return_value=fake_now,
    ):
        with patch(
            "appointment_management.get_connection",
            return_value=connection,
        ):
            result = reschedule_appointment(
                customer_id=CUSTOMER_ID,
                appointment_id=APPOINTMENT_ID,
                new_date="2026-08-20",
                new_time="14:00",
            )

    assert result["success"] is False
    assert "already booked" in result["message"].lower()


def test_successful_reschedule():
    cursor = MagicMock()

    cursor.fetchone.side_effect = [
        (
            APPOINTMENT_ID,
            SERVICE_ID,
            "Dental Filling",
            date(2026, 8, 18),
            time(9, 0),
        ),
        None,
    ]

    connection = make_connection(cursor)

    fake_now = datetime(2026, 8, 18, 12, 0)

    with patch(
        "appointment_management.get_current_datetime",
        return_value=fake_now,
    ):
        with patch(
            "appointment_management.get_connection",
            return_value=connection,
        ):
            result = reschedule_appointment(
                customer_id=CUSTOMER_ID,
                appointment_id=APPOINTMENT_ID,
                new_date="2026-08-20",
                new_time="14:00",
            )

    assert result["success"] is True
    assert result["appointment_id"] == APPOINTMENT_ID
    assert result["service"] == "Dental Filling"
    assert result["date"] == "2026-08-20"
    assert result["time"] == "14:00"

    connection.commit.assert_called_once()


def test_customer_cannot_reschedule_other_customer_appointment():
    cursor = MagicMock()

    # Because the query includes customer_id,
    # an appointment belonging to another customer
    # should not be found.
    cursor.fetchone.return_value = None

    connection = make_connection(cursor)

    fake_now = datetime(2026, 8, 18, 12, 0)

    with patch(
        "appointment_management.get_current_datetime",
        return_value=fake_now,
    ):
        with patch(
            "appointment_management.get_connection",
            return_value=connection,
        ):
            result = reschedule_appointment(
                customer_id=999,
                appointment_id=APPOINTMENT_ID,
                new_date="2026-08-20",
                new_time="14:00",
            )

    assert result["success"] is False
    assert "not found" in result["message"].lower()