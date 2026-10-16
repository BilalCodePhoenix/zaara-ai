from app.exceptions import AppointmentError
from app.services.doctor_service import recommend_doctor
from app.services.patient_service import get_or_create_patient
from app.services.booking_rules import (
    ensure_booking_allowed,
    normalize_phone
)
from app.services.appointment_service import (
    check_availability,
    book_appointment
)

# Rule errors that should reach the voice agent as a clear, specific result
# (the prompt tells Zara how to react to each of these codes).
RULE_ERRORS = {
    "already_booked_at_this_time": (
        "This patient already has an appointment at this date and time."
    ),
    "booking_limit_reached": (
        "This phone number already has too many upcoming appointments."
    ),
}


def create_booking(
    problem,
    patient_name,
    patient_phone,
    appointment_date,
    appointment_time
):
    # 0. Validate the phone number format before doing anything else
    clean_phone = normalize_phone(patient_phone)

    if clean_phone is None:
        return {
            "success": False,
            "error": "validation_error",
            "message": "Phone number must be a valid 10-digit mobile number."
        }

    patient_phone = clean_phone

    # 1. Find the most relevant doctor
    doctor = recommend_doctor(problem)

    if not doctor:
        return {
            "success": False,
            "message": "No suitable doctor was found."
        }

    doctor_id = doctor[0]
    doctor_name = doctor[1]
    specialization = doctor[2]

    # 2. Find existing patient (same full name on this phone) or create one
    patient = get_or_create_patient(
        patient_name,
        patient_phone
    )

    patient_id = patient[0]

    # 3. Booking rules: no clash for the same patient at the same time,
    #    and a cap on upcoming bookings per phone number (spam guard)
    try:
        ensure_booking_allowed(
            patient_id,
            patient_phone,
            appointment_date,
            appointment_time
        )

    except AppointmentError as error:
        code = str(error)

        if code in RULE_ERRORS:
            return {
                "success": False,
                "error": code,
                "message": RULE_ERRORS[code]
            }

        raise

    # 4. Check whether the requested slot is available
    available = check_availability(
        doctor_id,
        appointment_date,
        appointment_time
    )

    if not available:
        return {
            "success": False,
            "message": "The requested appointment slot is already booked."
        }

    # 5. Book the appointment
    appointment_id = book_appointment(
        patient_id,
        doctor_id,
        appointment_date,
        appointment_time
    )

    if not appointment_id:
        return {
            "success": False,
            "message": "The appointment could not be booked."
        }

    # 6. Return useful information
    return {
        "success": True,
        "appointment_id": appointment_id,
        "patient_id": patient_id,
        "doctor_id": doctor_id,
        "doctor_name": doctor_name,
        "specialization": specialization,
        "appointment_date": str(appointment_date),
        "appointment_time": str(appointment_time)
    }