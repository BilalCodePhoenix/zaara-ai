# app/llm/tools.py 

FIND_DOCTOR_TOOL = {
    "name": "find_relevant_doctor",
    "description": (
        "Find the most appropriate dentist for a patient's "
        "dental problem."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "problem": {
                "type": "string",
                "description": (
                    "The patient's dental problem, such as "
                    "toothache, braces, wisdom tooth, or general "
                    "dental problem."
                )
            }
        },
        "required": [
            "problem"
        ]
    }
}


CHECK_AVAILABILITY_TOOL = {
    "name": "check_appointment_availability",
    "description": (
        "Check whether a specific dentist is available for "
        "a specific date and time."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "doctor_id": {
                "type": "integer",
                "description": (
                    "The database ID of the dentist."
                )
            },
            "appointment_date": {
                "type": "string",
                "description": (
                    "The appointment date in YYYY-MM-DD format."
                )
            },
            "appointment_time": {
                "type": "string",
                "description": (
                    "The appointment time in HH:MM format."
                )
            }
        },
        "required": [
            "doctor_id",
            "appointment_date",
            "appointment_time"
        ]
    }
}


BOOKING_TOOL = {
    "name": "book_dental_appointment",
    "description": (
        "Book a dental appointment for a patient. "
        "Use this tool only when the patient's problem, "
        "name, phone number, appointment date, and appointment "
        "time are available."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "problem": {
                "type": "string",
                "description": "The patient's dental problem."
            },
            "patient_name": {
                "type": "string",
                "description": "The patient's full name."
            },
            "patient_phone": {
                "type": "string",
                "description": "The patient's phone number."
            },
            "appointment_date": {
                "type": "string",
                "description": (
                    "Appointment date in YYYY-MM-DD format."
                )
            },
            "appointment_time": {
                "type": "string",
                "description": (
                    "Appointment time in HH:MM format."
                )
            }
        },
        "required": [
            "problem",
            "patient_name",
            "patient_phone",
            "appointment_date",
            "appointment_time"
        ]
    }
}


FIND_AVAILABLE_SLOTS_TOOL = {
    "name": "find_available_appointment_slots",
    "description": (
        "Find alternative available appointment slots for a dentist "
        "when the patient's requested time is unavailable."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "doctor_id": {
                "type": "integer",
                "description": "The database ID of the dentist."
            },
            "appointment_date": {
                "type": "string",
                "description": "Appointment date in YYYY-MM-DD format."
            },
            "appointment_time": {
                "type": "string",
                "description": "The patient's preferred time in HH:MM format."
            }
        },
        "required": [
            "doctor_id",
            "appointment_date",
            "appointment_time"
        ]
    }
}