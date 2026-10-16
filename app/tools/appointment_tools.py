from app.services.appointment_service import (
    check_availability,
    book_appointment,
    find_available_slots
)


def check_appointment_availability(
    doctor_id,
    appointment_date,
    appointment_time
):
    available = check_availability(
        doctor_id,
        appointment_date,
        appointment_time
    )

    return {
        "success": True,
        "available": available,
        "doctor_id": doctor_id,
        "appointment_date": str(appointment_date),
        "appointment_time": str(appointment_time)
    }


def create_appointment(
    patient_id,
    doctor_id,
    appointment_date,
    appointment_time
):
    return book_appointment(
        patient_id,
        doctor_id,
        appointment_date,
        appointment_time
    )


def get_available_appointment_slots(
    doctor_id,
    appointment_date,
    appointment_time
):
    slots = find_available_slots(
        doctor_id,
        appointment_date,
        appointment_time
    )

    return {
        "success": True,
        "doctor_id": doctor_id,
        "appointment_date": str(appointment_date),
        "available_slots": [
            slot.strftime("%H:%M")
            for slot in slots
        ]
    }