from app.llm.client import client
from app.llm.tools import (
    FIND_DOCTOR_TOOL,
    CHECK_AVAILABILITY_TOOL,
    FIND_AVAILABLE_SLOTS_TOOL,
    BOOKING_TOOL
)
from app.llm.executor import execute_tool
from app.llm.conversation import Conversation

import json
from app.llm.prompts import get_system_instruction

def run_agent_turn(conversation, user_message):

    print("\nUSER:")
    print(user_message)

    conversation.add_user_message(user_message)

    tools = [
        {
            "function_declarations": [
                FIND_DOCTOR_TOOL,
                CHECK_AVAILABILITY_TOOL,
                FIND_AVAILABLE_SLOTS_TOOL,
                BOOKING_TOOL
            ]
        }
    ]

    while True:

        response = client.models.generate_content(
            model="gemini-3.5-flash-lite",
            contents=conversation.get_messages(),
            config={
                "tools": tools,
                "system_instruction": get_system_instruction()
            }
        )

        conversation.add_ai_message(
            response.candidates[0].content
        )

        function_call = None

        for part in response.candidates[0].content.parts:
            if part.function_call:
                function_call = part.function_call
                break

        # Gemini has finished this turn
        if not function_call:

            print("\nAI:")
            print(response.text)

            return response.text

        print("\nLLM requested:")
        print(function_call.name)

        print("\nArguments:")
        print(function_call.args)

        tool_result = execute_tool(
            function_call.name,
            dict(function_call.args),
            conversation 
        )

        print("\nTool result:")
        print(tool_result)

        # Convert date/time/etc. into JSON-safe values
        tool_result = json.loads(
            json.dumps(tool_result, default=str)
        )

        conversation.add_tool_result(
            function_call.name,
            tool_result
        )


def main():

    conversation = Conversation()

    run_agent_turn(
        conversation,
        "I have severe tooth pain."
    )

    run_agent_turn(
        conversation,
        "I want an appointment after tomorrow at 05:30 PM."
    )

    run_agent_turn(
        conversation,
        "06 PM works for me."
    )

    run_agent_turn(
        conversation,
        "My name is Amir Khan and my phone number is 9276543210."
    )

    run_agent_turn(
        conversation,
        "okay so lets book for 4:30 pm, i will come to your clinic."
    )

    print("\nCURRENT STATE:")
    print("Problem:", conversation.state.problem)
    print("Doctor:", conversation.state.doctor_name)
    print("Doctor ID:", conversation.state.doctor_id)
    print("Date:", conversation.state.appointment_date)
    print("Time:", conversation.state.appointment_time)
    print("Patient:", conversation.state.patient_name)
    print("Phone:", conversation.state.patient_phone)
    print("Appointment ID:", conversation.state.appointment_id)

if __name__ == "__main__":
    main()