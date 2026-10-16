import logging

from app.database.connection import get_connection
from app.exceptions import AppointmentError 
import re 

logger = logging.getLogger(__name__)

# Spam guard: how many upcoming bookings one phone number may hold.
# A family can share a number, so keep this well above 1. Tune it per clinic.
MAX_ACTIVE_BOOKINGS_PER_PHONE = 5

def normalize_phone(phone):
    """Return a clean 10-digit Indian mobile number, or None if invalid.
 
    Accepts spaces, dashes and a +91 / 91 / 0 prefix. It checks the format
    only, not whose number it is: families share phones on purpose.
    """
    digits = re.sub(r"\D", "", str(phone or ""))
 
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
 
    elif len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
 
    if len(digits) == 10 and digits[0] in "6789":
        return digits
 
    return None


def _fetch_one(query, params):
    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor()
        cursor.execute(query, params)
        return cursor.fetchone()

    finally:
        if cursor:
            cursor.close()

        if connection:
            connection.close()


def patient_has_booking_at(patient_id, appointment_date, appointment_time):
    """True if this patient already holds a booked slot at the same date and
    time (with any doctor). A person cannot be in two chairs at once, but
    booking other days, or other times on the same day, is allowed."""
    row = _fetch_one(
        """
        SELECT 1
        FROM appointments
        WHERE patient_id = %s
          AND appointment_date = %s
          AND appointment_time = %s
          AND status = 'booked'
        LIMIT 1;
        """,
        (patient_id, appointment_date, appointment_time)
    )

    return row is not None


def count_upcoming_bookings_for_phone(phone):
    """Upcoming booked appointments across everyone on this phone number,
    measured in Indian time so 'upcoming' is correct on a UTC server."""
    row = _fetch_one(
        """
        SELECT COUNT(*)
        FROM appointments a
        JOIN patients p ON p.id = a.patient_id
        WHERE p.phone = %s
          AND a.status = 'booked'
          AND (a.appointment_date + a.appointment_time)
              >= (now() AT TIME ZONE 'Asia/Kolkata');
        """,
        (phone,)
    )

    return row[0]


def ensure_booking_allowed(
    patient_id,
    phone,
    appointment_date,
    appointment_time
):
    """Call this before book_appointment(). Raises AppointmentError if the
    booking should not go ahead. Slot clashes between different patients are
    still blocked by the unique constraint inside book_appointment()."""
    try:
        if patient_has_booking_at(
            patient_id,
            appointment_date,
            appointment_time
        ):
            raise AppointmentError("already_booked_at_this_time")

        if count_upcoming_bookings_for_phone(phone) >= MAX_ACTIVE_BOOKINGS_PER_PHONE:
            logger.warning("Booking limit reached for a phone number")
            raise AppointmentError("booking_limit_reached")

    except AppointmentError:
        raise

    except Exception as error:
        logger.exception("Booking rule check failed")

        raise AppointmentError(
            "Unable to check booking rules."
        ) from error