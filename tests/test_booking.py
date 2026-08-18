from datetime import datetime
from unittest.mock import MagicMock, patch

from appointments import book_appointment


CUSTOMER_ID = 91
SERVICE_ID = 3


def test_invalid_date():
    result = book_appointment(
        customer_id=CUSTOMER_ID,
        service_id=SERVICE_ID,
        appointment_date="not-a-date",
        appointment_time="09:00",
    )

    assert result["success"] is False
    assert result["message"] == "Invalid appointment date."


def test_invalid_time():
    result = book_appointment(
        customer_id=CUSTOMER_ID,
        service_id=SERVICE_ID,
        appointment_date="2026-08-18",
        appointment_time="invalid",
    )

    assert result["success"] is False
    assert "Invalid appointment time" in result["message"]


def test_past_date():
    fake_now = datetime(
        2026,
        8,
        16,
        12,
        0,
    )

    with patch(
        "appointments.get_current_datetime",
        return_value=fake_now,
    ):
        result = book_appointment(
            customer_id=CUSTOMER_ID,
            service_id=SERVICE_ID,
            appointment_date="2026-08-15",
            appointment_time="09:00",
        )

    assert result["success"] is False
    assert "past" in result["message"].lower()


def test_past_time_today():
    fake_now = datetime(
        2026,
        8,
        16,
        14,
        30,
    )

    with patch(
        "appointments.get_current_datetime",
        return_value=fake_now,
    ):
        result = book_appointment(
            customer_id=CUSTOMER_ID,
            service_id=SERVICE_ID,
            appointment_date="2026-08-16",
            appointment_time="13:00",
        )

    assert result["success"] is False
    assert "already passed" in result["message"].lower()


def test_invalid_clinic_time():
    result = book_appointment(
        customer_id=CUSTOMER_ID,
        service_id=SERVICE_ID,
        appointment_date="2026-08-18",
        appointment_time="12:00",
    )

    assert result["success"] is False
    assert "not a valid clinic" in result["message"].lower()


def test_service_not_found():
    mock_connection = MagicMock()
    mock_cursor = MagicMock()

    mock_connection.cursor.return_value.__enter__.return_value = (
        mock_cursor
    )

    mock_cursor.fetchone.return_value = None

    fake_now = datetime(
        2026,
        8,
        16,
        12,
        0,
    )

    with patch(
        "appointments.get_current_datetime",
        return_value=fake_now,
    ):
        with patch(
            "appointments.get_connection",
            return_value=mock_connection,
        ):
            result = book_appointment(
                customer_id=CUSTOMER_ID,
                service_id=999,
                appointment_date="2026-08-18",
                appointment_time="09:00",
            )

    assert result["success"] is False
    assert result["message"] == "Invalid service."


def test_already_booked():
    mock_connection = MagicMock()
    mock_cursor = MagicMock()

    mock_connection.cursor.return_value.__enter__.return_value = (
        mock_cursor
    )

    mock_cursor.fetchone.side_effect = [
        (SERVICE_ID, "Dental Filling"),
        (11,),
    ]

    fake_now = datetime(
        2026,
        8,
        16,
        12,
        0,
    )

    with patch(
        "appointments.get_current_datetime",
        return_value=fake_now,
    ):
        with patch(
            "appointments.get_connection",
            return_value=mock_connection,
        ):
            result = book_appointment(
                customer_id=CUSTOMER_ID,
                service_id=SERVICE_ID,
                appointment_date="2026-08-18",
                appointment_time="09:00",
            )

    assert result["success"] is False
    assert "already booked" in result["message"].lower()


def test_successful_booking():
    mock_connection = MagicMock()
    mock_cursor = MagicMock()

    mock_connection.cursor.return_value.__enter__.return_value = (
        mock_cursor
    )

    # First fetchone() = service
    # Second fetchone() = no existing appointment
    # Third fetchone() = newly created appointment ID
    mock_cursor.fetchone.side_effect = [
        (SERVICE_ID, "Dental Filling"),
        None,
        (123,),
    ]

    fake_now = datetime(
        2026,
        8,
        16,
        12,
        0,
    )

    with patch(
        "appointments.get_current_datetime",
        return_value=fake_now,
    ):
        with patch(
            "appointments.get_connection",
            return_value=mock_connection,
        ):
            result = book_appointment(
                customer_id=CUSTOMER_ID,
                service_id=SERVICE_ID,
                appointment_date="2026-08-18",
                appointment_time="09:00",
            )

    assert result["success"] is True
    assert result["appointment_id"] == 123
    assert result["service"] == "Dental Filling"
    assert result["date"] == "2026-08-18"
    assert result["time"] == "09:00"

    mock_connection.commit.assert_called_once()

def test_duplicate_booking_from_database():
    mock_connection = MagicMock()
    mock_cursor = MagicMock()

    mock_connection.cursor.return_value.__enter__.return_value = (
        mock_cursor
    )

    mock_cursor.fetchone.side_effect = [
        (SERVICE_ID, "Dental Filling"),
    ]

    import psycopg2

    mock_cursor.execute.side_effect = [
        None,  # service SELECT
        psycopg2.errors.UniqueViolation(),
    ]

    fake_now = datetime(
        2026,
        8,
        16,
        12,
        0,
    )

    with patch(
        "appointments.get_current_datetime",
        return_value=fake_now,
    ):
        with patch(
            "appointments.get_connection",
            return_value=mock_connection,
        ):
            result = book_appointment(
                customer_id=CUSTOMER_ID,
                service_id=SERVICE_ID,
                appointment_date="2026-08-18",
                appointment_time="09:00",
            )

    assert result["success"] is False
    assert "just booked" in result["message"].lower()

    mock_connection.rollback.assert_called_once()