from app.tools.doctor_tools import find_relevant_doctor
from app.tools.appointment_tools import (
    check_appointment_availability,
    get_available_appointment_slots
)
from app.tools.booking_tools import book_dental_appointment


def execute_tool(function_name, arguments, conversation):

    # ---------------------------------------------------------
    # FIND RELEVANT DOCTOR
    # ---------------------------------------------------------
    if function_name == "find_relevant_doctor":

        result = find_relevant_doctor(
            problem=arguments["problem"]
        )

        if result["success"]:
            doctor = result["doctor"]

            conversation.state.problem = arguments["problem"]
            conversation.state.doctor_id = doctor["id"]
            conversation.state.doctor_name = doctor["name"]

        return result

    # ---------------------------------------------------------
    # CHECK APPOINTMENT AVAILABILITY
    # ---------------------------------------------------------
    if function_name == "check_appointment_availability":

        result = check_appointment_availability(
            doctor_id=arguments["doctor_id"],
            appointment_date=arguments["appointment_date"],
            appointment_time=arguments["appointment_time"]
        )

        # IMPORTANT:
        # Do NOT update the confirmed appointment state here.
        #
        # Checking a slot does NOT mean the patient selected it.
        #
        # Example:
        # Patient: "Is 6 PM available?"
        #
        # Checking 6 PM should not make the state say:
        # appointment_time = 18:00
        #
        # The appointment becomes official only after booking.

        return result

    # ---------------------------------------------------------
    # FIND ALTERNATIVE AVAILABLE SLOTS
    # ---------------------------------------------------------
    if function_name == "find_available_appointment_slots":

        return get_available_appointment_slots(
            doctor_id=arguments["doctor_id"],
            appointment_date=arguments["appointment_date"],
            appointment_time=arguments["appointment_time"]
        )

    # ---------------------------------------------------------
    # BOOK DENTAL APPOINTMENT
    # ---------------------------------------------------------
    if function_name == "book_dental_appointment":

        result = book_dental_appointment(
            problem=arguments["problem"],
            patient_name=arguments["patient_name"],
            patient_phone=arguments["patient_phone"],
            appointment_date=arguments["appointment_date"],
            appointment_time=arguments["appointment_time"]
        )

        # Only update the final conversation state
        # after the database booking succeeds.
        if result["success"]:

            conversation.state.problem = arguments["problem"]

            conversation.state.patient_name = arguments["patient_name"]
            conversation.state.patient_phone = arguments["patient_phone"]

            # Use values returned by the booking service/database
            conversation.state.doctor_id = result["doctor_id"]
            conversation.state.doctor_name = result["doctor_name"]

            conversation.state.appointment_date = (
                result["appointment_date"]
            )
            conversation.state.appointment_time = (
                result["appointment_time"]
            )

            conversation.state.appointment_id = (
                result["appointment_id"]
            )

            # The appointment is now officially confirmed.
            conversation.state.appointment_confirmed = True

        return result

    # ---------------------------------------------------------
    # UNKNOWN TOOL
    # ---------------------------------------------------------
    return {
        "success": False,
        "error": "unknown_tool",
        "message": f"Unknown tool: {function_name}"
    }