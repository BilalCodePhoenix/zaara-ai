from app.services.patient_service import get_or_create_patient


def find_or_create_patient(name, phone):
    return get_or_create_patient(name, phone)