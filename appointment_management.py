from database import get_connection

from datetime import datetime

from appointments import (
    CLINIC_TIMES,
    get_current_datetime,
)

def get_customer_appointments(customer_id):
    connection = get_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    a.id,
                    s.name,
                    a.appointment_date,
                    a.appointment_time
                FROM appointments a
                JOIN services s
                    ON a.service_id = s.id
                WHERE a.customer_id = %s
                AND a.status = 'confirmed'
                ORDER BY
                    a.appointment_date,
                    a.appointment_time;
                """,
                (customer_id,),
            )

            rows = cursor.fetchall()

        return [
            {
                "appointment_id": row[0],
                "service": row[1],
                "date": str(row[2]),
                "time": row[3].strftime("%H:%M"),
            }
            for row in rows
        ]

    finally:
        connection.close()


def cancel_appointment(
    customer_id,
    appointment_id,
):
    connection = get_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    a.id,
                    s.name,
                    a.appointment_date,
                    a.appointment_time
                FROM appointments a
                JOIN services s
                    ON a.service_id = s.id
                WHERE a.id = %s
                AND a.customer_id = %s
                AND a.status = 'confirmed';
                """,
                (
                    appointment_id,
                    customer_id,
                ),
            )

            appointment = cursor.fetchone()

            if not appointment:
                return {
                    "success": False,
                    "message": (
                        "Appointment not found or it has "
                        "already been cancelled."
                    ),
                }

            cursor.execute(
                """
                UPDATE appointments
                SET status = 'cancelled'
                WHERE id = %s
                AND customer_id = %s
                AND status = 'confirmed';
                """,
                (
                    appointment_id,
                    customer_id,
                ),
            )

        connection.commit()

        return {
            "success": True,
            "appointment_id": appointment[0],
            "service": appointment[1],
            "date": str(appointment[2]),
            "time": appointment[3].strftime("%H:%M"),
        }

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()

def reschedule_appointment(
    customer_id,
    appointment_id,
    new_date,
    new_time,
):
    now = get_current_datetime()

    # Validate date
    try:
        new_date_obj = datetime.strptime(
            new_date,
            "%Y-%m-%d",
        ).date()
    except ValueError:
        return {
            "success": False,
            "message": "Invalid appointment date.",
        }

    # Validate time
    try:
        datetime.strptime(
            new_time,
            "%H:%M",
        )
    except ValueError:
        return {
            "success": False,
            "message": "Invalid appointment time. Use HH:MM.",
        }

    # Cannot reschedule to a past date
    if new_date_obj < now.date():
        return {
            "success": False,
            "message": (
                "Appointments cannot be rescheduled "
                "to a date in the past."
            ),
        }

    # Cannot reschedule to a past time today
    if new_date_obj == now.date():
        current_time = now.strftime("%H:%M")

        if new_time <= current_time:
            return {
                "success": False,
                "message": (
                    "That time has already passed. "
                    "Please choose a later time."
                ),
            }

    # Must be a clinic time
    if new_time not in CLINIC_TIMES:
        return {
            "success": False,
            "message": (
                "That is not a valid clinic appointment time."
            ),
        }

    connection = get_connection()

    try:
        with connection.cursor() as cursor:

            # Find the customer's confirmed appointment
            cursor.execute(
                """
                SELECT
                    a.id,
                    a.service_id,
                    s.name,
                    a.appointment_date,
                    a.appointment_time
                FROM appointments a
                JOIN services s
                    ON a.service_id = s.id
                WHERE a.id = %s
                AND a.customer_id = %s
                AND a.status = 'confirmed';
                """,
                (
                    appointment_id,
                    customer_id,
                ),
            )

            appointment = cursor.fetchone()

            if not appointment:
                return {
                    "success": False,
                    "message": (
                        "Appointment not found or it has "
                        "already been cancelled."
                    ),
                }

            service_id = appointment[1]
            service_name = appointment[2]

            # Check whether the new slot is occupied
            cursor.execute(
                """
                SELECT id
                FROM appointments
                WHERE appointment_date = %s
                AND appointment_time = %s
                AND service_id = %s
                AND status = 'confirmed'
                AND id != %s;
                """,
                (
                    new_date,
                    new_time,
                    service_id,
                    appointment_id,
                ),
            )

            if cursor.fetchone():
                return {
                    "success": False,
                    "message": (
                        "That new appointment time is already booked."
                    ),
                }

            # Update the existing appointment
            cursor.execute(
                """
                UPDATE appointments
                SET
                    appointment_date = %s,
                    appointment_time = %s
                WHERE id = %s
                AND customer_id = %s
                AND status = 'confirmed';
                """,
                (
                    new_date,
                    new_time,
                    appointment_id,
                    customer_id,
                ),
            )

        connection.commit()

        return {
            "success": True,
            "appointment_id": appointment_id,
            "service": service_name,
            "date": new_date,
            "time": new_time,
        }

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()