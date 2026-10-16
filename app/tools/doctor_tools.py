from app.services.doctor_service import (
    get_available_doctors,
    recommend_doctor
)


def find_relevant_doctor(problem):

    doctor = recommend_doctor(problem)

    if not doctor:
        return {
            "success": False,
            "message": "No suitable dentist was found."
        }

    return {
        "success": True,
        "doctor": {
            "id": doctor[0],
            "name": doctor[1],
            "specialization": doctor[2],
            "consultation_fee": float(doctor[3])
        }
    }


def get_doctors():
    doctors = get_available_doctors()

    return [
        {
            "id": doctor[0],
            "name": doctor[1],
            "specialization": doctor[2],
            "consultation_fee": float(doctor[3])
        }
        for doctor in doctors
    ]