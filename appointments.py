from datetime import datetime
from zoneinfo import ZoneInfo

from database import get_connection
import psycopg2

TIMEZONE = ZoneInfo("Asia/Almaty")

CLINIC_TIMES = [
    "09:00",
    "10:00",
    "11:00",
    "13:00",
    "14:00",
    "16:00",
    "17:00",
]


def get_current_datetime():
    return datetime.now(TIMEZONE)


def get_available_times(
    appointment_date,
    requested_period=None,
):
    """
    Return valid clinic times for a date and optional period.

    requested_period:
        None
        "morning"
        "afternoon"
    """

    now = get_current_datetime()
    today = now.date()

    try:
        requested_date = datetime.strptime(
            appointment_date,
            "%Y-%m-%d",
        ).date()
    except ValueError:
        return []

    # Never allow yesterday or any earlier date.
    if requested_date < today:
        return []

    available_times = CLINIC_TIMES.copy()

    # Morning: before 12:00
    if requested_period == "morning":
        available_times = [
            time
            for time in available_times
            if time < "12:00"
        ]

    # Afternoon: 12:00 and later
    elif requested_period == "afternoon":
        available_times = [
            time
            for time in available_times
            if time >= "12:00"
        ]

    # If the customer is booking today,
    # remove times that have already passed.
    if requested_date == today:
        current_time = now.strftime("%H:%M")

        available_times = [
            time
            for time in available_times
            if time > current_time
        ]

    return available_times


def check_availability(
    service_id,
    appointment_date,
    requested_period=None,
):
    connection = get_connection()

    try:
        with connection.cursor() as cursor:

            # Verify service exists.
            cursor.execute(
                """
                SELECT id, name, duration_minutes
                FROM services
                WHERE id = %s;
                """,
                (service_id,),
            )

            service = cursor.fetchone()

            if not service:
                return {
                    "success": False,
                    "message": "Service not found.",
                }

            # Get already booked appointments.
            cursor.execute(
                """
                SELECT appointment_time
                FROM appointments
                WHERE appointment_date = %s
                AND service_id = %s
                AND status = 'confirmed'
                ORDER BY appointment_time;
                """,
                (
                    appointment_date,
                    service_id,
                ),
            )

            booked_times = {
                row[0].strftime("%H:%M")
                for row in cursor.fetchall()
            }

            # Get valid times according to:
            # - date
            # - morning/afternoon
            # - current time
            possible_times = get_available_times(
                appointment_date,
                requested_period,
            )

            # Remove already booked times.
            available_times = [
                time
                for time in possible_times
                if time not in booked_times
            ]

            return {
                "success": True,
                "service_id": service[0],
                "service": service[1],
                "date": str(appointment_date),
                "requested_period": requested_period,
                "available_times": available_times,
            }

    finally:
        connection.close()


def book_appointment(
    customer_id,
    service_id,
    appointment_date,
    appointment_time,
):
    # Validate date format.
    try:
        requested_date = datetime.strptime(
            appointment_date,
            "%Y-%m-%d",
        ).date()
    except ValueError:
        return {
            "success": False,
            "message": "Invalid appointment date.",
        }

    # Validate time format.
    try:
        datetime.strptime(
            appointment_time,
            "%H:%M",
        )
    except ValueError:
        return {
            "success": False,
            "message": (
                "Invalid appointment time. "
                "Use HH:MM."
            ),
        }

    # Current Kazakhstan time.
    now = get_current_datetime()
    today = now.date()

    # Never allow booking in the past.
    if requested_date < today:
        return {
            "success": False,
            "message": (
                "Appointments cannot be booked "
                "for a date in the past."
            ),
        }

    # If booking today, the selected time
    # must still be in the future.
    if requested_date == today:
        current_time = now.strftime("%H:%M")

        if appointment_time <= current_time:
            return {
                "success": False,
                "message": (
                    "That appointment time has already "
                    "passed. Please choose a later time."
                ),
            }

    # Valid clinic appointment times.
    if appointment_time not in CLINIC_TIMES:
        return {
            "success": False,
            "message": (
                "That time is not a valid clinic "
                "appointment time."
            ),
        }

    connection = get_connection()

    try:
        with connection.cursor() as cursor:

            # Verify service exists.
            cursor.execute(
                """
                SELECT id, name
                FROM services
                WHERE id = %s;
                """,
                (service_id,),
            )

            service = cursor.fetchone()

            if not service:
                return {
                    "success": False,
                    "message": "Invalid service.",
                }

            # Check whether the exact slot is already booked.
            cursor.execute(
                """
                SELECT id
                FROM appointments
                WHERE appointment_date = %s
                AND appointment_time = %s
                AND service_id = %s
                AND status = 'confirmed';
                """,
                (
                    appointment_date,
                    appointment_time,
                    service_id,
                ),
            )

            if cursor.fetchone():
                return {
                    "success": False,
                    "message": (
                        "That time is already booked."
                    ),
                }

            # Create appointment.
            cursor.execute(
                """
                INSERT INTO appointments
                    (
                        customer_id,
                        service_id,
                        appointment_date,
                        appointment_time,
                        status
                    )
                VALUES
                    (
                        %s,
                        %s,
                        %s,
                        %s,
                        'confirmed'
                    )
                RETURNING id;
                """,
                (
                    customer_id,
                    service_id,
                    appointment_date,
                    appointment_time,
                ),
            )

            appointment_id = cursor.fetchone()[0]

        connection.commit()

        return {
            "success": True,
            "appointment_id": appointment_id,
            "service": service[1],
            "date": appointment_date,
            "time": appointment_time,
        }

    except psycopg2.errors.UniqueViolation:
        connection.rollback()

        return {
            "success": False,
            "message": (
                "That appointment time was just booked by another customer. "
                "Please choose another available time."
            ),
        }

    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def get_services():
    connection = get_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    id,
                    name,
                    description,
                    price,
                    duration_minutes
                FROM services
                ORDER BY id;
                """
            )

            rows = cursor.fetchall()

        return [
            {
                "id": row[0],
                "name": row[1],
                "description": row[2],
                "price": (
                    float(row[3])
                    if row[3] is not None
                    else None
                ),
                "duration_minutes": row[4],
            }
            for row in rows
        ]

    finally:
        connection.close()