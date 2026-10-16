import logging
import psycopg

from app.database.connection import get_connection
from app.exceptions import AppointmentError

from datetime import date, datetime, time, timedelta

logger = logging.getLogger(__name__)


def check_availability(
    doctor_id,
    appointment_date,
    appointment_time
):
    connection = None
    cursor = None


    if isinstance(appointment_time, str):
        appointment_time = time.fromisoformat(
            appointment_time
        )

    if appointment_time < time(9, 0) or appointment_time >= time(18, 0):
        return False

    try:
        logger.info(
            "Checking appointment availability for doctor ID %s",
            doctor_id
        )

        connection = get_connection()
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT id
            FROM appointments
            WHERE doctor_id = %s
            AND appointment_date = %s
            AND appointment_time = %s
            AND status = 'booked';
            """,
            (
                doctor_id,
                appointment_date,
                appointment_time
            )
        )

        appointment = cursor.fetchone()

        available = appointment is None

        logger.info(
            "Appointment slot available: %s",
            available
        )

        return available

    except Exception as error:
        logger.exception("Availability check failed")

        raise AppointmentError(
            "Unable to check appointment availability."
        ) from error

    finally:
        if cursor:
            cursor.close()

        if connection:
            connection.close()


def book_appointment(
    patient_id,
    doctor_id,
    appointment_date,
    appointment_time
):
    connection = None
    cursor = None

    try:
        logger.info(
            "Booking appointment for doctor ID %s",
            doctor_id
        )

        connection = get_connection()
        cursor = connection.cursor()

        cursor.execute(
            """
            INSERT INTO appointments
            (
                patient_id,
                doctor_id,
                appointment_date,
                appointment_time,
                status
            )
            VALUES (%s, %s, %s, %s, 'booked')
            RETURNING id;
            """,
            (
                patient_id,
                doctor_id,
                appointment_date,
                appointment_time
            )
        )

        appointment_id = cursor.fetchone()[0]

        connection.commit()

        logger.info(
            "Appointment booked successfully: ID %s",
            appointment_id
        )

        return appointment_id

    except psycopg.errors.UniqueViolation:
        if connection:
            connection.rollback()

        logger.warning(
            "Appointment slot was already booked."
        )

        raise AppointmentError(
            "The appointment slot is no longer available."
        )

    except Exception as error:
        if connection:
            connection.rollback()

        logger.exception(
            "Appointment booking failed"
        )

        raise AppointmentError(
            "Unable to book the appointment."
        ) from error

    finally:
        if cursor:
            cursor.close()

        if connection:
            connection.close()

# it check the availability of slots of a doctor for any particular time interval
# basically it will return the 3 free slots 
def find_available_slots(
    doctor_id,
    appointment_date,
    start_time,
    number_of_slots=3
):
    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor()

        if isinstance(appointment_date, str):
            appointment_date = date.fromisoformat(appointment_date)

        if isinstance(start_time, str):
            start_time = time.fromisoformat(start_time)

        current_datetime = datetime.combine(
            appointment_date,
            start_time
        )

        available_slots = []

        for _ in range(12):

            current_time = current_datetime.time()

            if current_time >= time(18, 0):
                break

            cursor.execute(
                """
                SELECT id
                FROM appointments
                WHERE doctor_id = %s
                AND appointment_date = %s
                AND appointment_time = %s
                AND status = 'booked';
                """,
                (
                    doctor_id,
                    appointment_date,
                    current_time
                )
            )

            if cursor.fetchone() is None:
                available_slots.append(current_time)

            if len(available_slots) >= number_of_slots:
                break

            current_datetime += timedelta(minutes=30)

        return available_slots

    finally:
        if cursor:
            cursor.close()

        if connection:
            connection.close()