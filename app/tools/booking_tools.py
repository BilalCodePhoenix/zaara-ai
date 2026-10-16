from pydantic import ValidationError

from app.schemas.booking import BookingRequest
from app.services.booking_service import create_booking
from app.exceptions import BookingError


def book_dental_appointment(
    problem,
    patient_name,
    patient_phone,
    appointment_date,
    appointment_time
):

    # 1. Validate input
    try:

        booking = BookingRequest(
            problem=problem,
            patient_name=patient_name,
            patient_phone=patient_phone,
            appointment_date=appointment_date,
            appointment_time=appointment_time
        )

    except ValidationError as error:

        return {
            "success": False,
            "error": "validation_error",
            "message": str(error)
        }

    # 2. Execute booking
    try:

        return create_booking(
            problem=booking.problem,
            patient_name=booking.patient_name,
            patient_phone=booking.patient_phone,
            appointment_date=booking.appointment_date,
            appointment_time=booking.appointment_time
        )

    except BookingError as error:

        return {
            "success": False,
            "error": "booking_error",
            "message": str(error)
        }

    except Exception:

        return {
            "success": False,
            "error": "internal_error",
            "message": "Something went wrong while processing the appointment."
        }