"""
evals/agent_runner.py

Runs Zaara's REAL brain in text mode and records everything.
It reuses the same system prompt, model settings, and tool glue as the
voice bot, so the numbers we get are about the bot you actually demo.
Only STT/TTS are skipped.

Safety: it only runs against a TEST database (TEST_DATABASE_URL in .env).

Quick check from the project root:
    python -m evals.agent_runner
"""

import importlib
import json
import os
import re 
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------
# 1. SAFETY: point everything at the TEST database
# ---------------------------------------------------------

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")

if not TEST_DATABASE_URL:
    raise RuntimeError(
        "TEST_DATABASE_URL is not set in .env. "
        "Create a separate dental_test database first."
    )

if TEST_DATABASE_URL == os.getenv("DATABASE_URL"):
    raise RuntimeError(
        "TEST_DATABASE_URL is the same as DATABASE_URL. "
        "Refusing to run evals on the real database."
    )

# Must be set BEFORE the app modules are imported.
os.environ["DATABASE_URL"] = TEST_DATABASE_URL

# ---------------------------------------------------------
# 2. Import the real pieces
# ---------------------------------------------------------

from google import genai  # noqa: E402

import app.database.connection as db_connection  # noqa: E402

from app.tools.doctor_tools import find_relevant_doctor  # noqa: E402
from app.tools.appointment_tools import (  # noqa: E402
    check_appointment_availability,
    get_available_appointment_slots,
)
from app.tools.booking_tools import book_dental_appointment  # noqa: E402
from app.llm.tools import (  # noqa: E402
    FIND_DOCTOR_TOOL,
    CHECK_AVAILABILITY_TOOL,
    FIND_AVAILABLE_SLOTS_TOOL,
    BOOKING_TOOL,
)

# >>> CHANGE THIS to the real module path of your voice bot file <<<
# (the file that contains SYSTEM_PROMPT and the _prep_* helpers)
VOICE_MODULE = "app.voice.voice_agent"
voice = importlib.import_module(VOICE_MODULE)

# The voice module calls load_dotenv(override=True), which puts the REAL
# database url back into the environment. Force the test one again.
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
db_connection.DATABASE_URL = TEST_DATABASE_URL

# ---------------------------------------------------------
# 3. Config (copied from the voice bot so behavior matches)
# ---------------------------------------------------------

MODEL = voice.GEMINI_MODEL
TEMPERATURE = 0.3
MAX_OUTPUT_TOKENS = 200
MAX_STEPS = 6  # safety stop so a looping model can't run forever

# The voice bot's first (hidden) message when a call connects.
GREETING_TRIGGER = (
    "Call abhi connect hui hai. "
    "STATE 1 ka greeting bolo."
)

client = genai.Client(
    api_key=os.environ.get("GOOGLE_API_KEY")
    or os.environ["GEMINI_API_KEY"]
)

TOOLS = [
    {
        "function_declarations": [
            FIND_DOCTOR_TOOL,
            CHECK_AVAILABILITY_TOOL,
            FIND_AVAILABLE_SLOTS_TOOL,
            BOOKING_TOOL,
        ]
    }
]

# tool name -> (python function, arg-prep function used by the voice bot)
TOOL_FUNCS = {
    FIND_DOCTOR_TOOL["name"]: (find_relevant_doctor, None),
    CHECK_AVAILABILITY_TOOL["name"]: (
        check_appointment_availability,
        voice._prep_slot_args,
    ),
    FIND_AVAILABLE_SLOTS_TOOL["name"]: (
        get_available_appointment_slots,
        voice._prep_slot_args,
    ),
    BOOKING_TOOL["name"]: (
        book_dental_appointment,
        voice._prep_booking_args,
    ),
}


def get_system_prompt():
    """Same as the voice bot: prompt + today's date/time in IST."""
    now = datetime.now(ZoneInfo("Asia/Kolkata"))
    today_info = (
        "\n\n# AAJ KI JAANKARI\n"
        f"Aaj {now:%A}, {now:%d %B %Y} hai. Abhi samay {now:%I:%M %p} (IST) hai. "
        "'Kal', 'parso' jaise shabdon ko isi se asli din aur tareekh mein badlo."
    )
    return voice.SYSTEM_PROMPT + today_info


# ---------------------------------------------------------
# 4. Test database helpers
# ---------------------------------------------------------

def _assert_test_db():
    conn = db_connection.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT current_database()")
            name = cur.fetchone()[0]
    finally:
        conn.close()

    if "test" not in name.lower():
        raise RuntimeError(
            f"Connected to '{name}', which does not look like a test "
            "database. Stopping."
        )


def reset_db():
    """Wipe patients + appointments. Doctors stay."""
    _assert_test_db()
    conn = db_connection.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "TRUNCATE appointments, patients RESTART IDENTITY CASCADE;"
            )
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------
# 5. Tool execution (same behavior as the voice bot's handler)
# ---------------------------------------------------------

def run_tool(name, args):

    if name not in TOOL_FUNCS:
        return {
            "success": False,
            "error": "unknown_tool",
            "message": f"Unknown tool: {name}",
        }

    fn, prepare = TOOL_FUNCS[name]

    try:
        call_args = prepare(args) if prepare else args
    except (ValueError, KeyError, TypeError) as exc:
        return voice._make_safe(
            {
                "success": False,
                "error": "validation_error",
                "message": f"Invalid arguments: {exc}",
            }
        )

    try:
        result = fn(**call_args)
    except Exception:
        result = {
            "success": False,
            "error": "internal_error",
            "message": "Something went wrong while processing the request.",
        }

    return voice._make_safe(result)



MIN_SECONDS_BETWEEN_CALLS = 4.5   # free tier = 15 requests/min
_last_call = 0.0


def generate(messages):
    """One Gemini call, paced to the rate limit. Returns (response, ms)."""
    global _last_call

    for _ in range(6):
        wait = MIN_SECONDS_BETWEEN_CALLS - (time.monotonic() - _last_call)
        if wait > 0:
            time.sleep(wait)
        _last_call = time.monotonic()

        started = time.monotonic()
        try:
            response = client.models.generate_content(
                model=MODEL,
                contents=messages,
                config={
                    "tools": TOOLS,
                    "system_instruction": get_system_prompt(),
                    "temperature": TEMPERATURE,
                    "max_output_tokens": MAX_OUTPUT_TOKENS,
                },
            )
            return response, (time.monotonic() - started) * 1000

        except Exception as exc:
            text = str(exc)
            if "429" in text or "RESOURCE_EXHAUSTED" in text:
                match = re.search(r"retry in ([\d.]+)s", text)
                time.sleep((float(match.group(1)) if match else 30) + 2)
                continue
            raise

    raise RuntimeError("Still rate limited after 6 retries")


# ---------------------------------------------------------
# 6. The agent loop
# ---------------------------------------------------------

def run_turn(messages, user_message):
    """One user message -> agent reply. Returns reply + full trace."""

    messages.append({"role": "user", "parts": [{"text": user_message}]})

    tool_calls = []
    llm_ms = 0.0
    input_tokens = 0
    output_tokens = 0

    for _ in range(MAX_STEPS):

        response, call_ms = generate(messages)
        llm_ms += call_ms

        usage = getattr(response, "usage_metadata", None)
        if usage:
            input_tokens += getattr(usage, "prompt_token_count", 0) or 0
            output_tokens += getattr(usage, "candidates_token_count", 0) or 0

        content = response.candidates[0].content
        messages.append(content)

        calls = [
            part.function_call
            for part in (content.parts or [])
            if part.function_call
        ]

        if not calls:
            return {
                "user": user_message,
                "reply": response.text,
                "tool_calls": tool_calls,
                "llm_ms": round(llm_ms),
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "error": None,
            }

        # Handle ALL function calls in this response (the voice bot does).
        response_parts = []
        for fc in calls:
            args = dict(fc.args)
            result = run_tool(fc.name, args)

            tool_calls.append(
                {"name": fc.name, "args": args, "result": result}
            )
            response_parts.append(
                {
                    "function_response": {
                        "name": fc.name,
                        "response": result,
                    }
                }
            )

        messages.append({"role": "user", "parts": response_parts})

    return {
        "user": user_message,
        "reply": None,
        "tool_calls": tool_calls,
        "llm_ms": round(llm_ms),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "error": "max_steps_reached",
    }


def run_conversation(user_messages, reset=True, include_greeting=True):
    """
    Run a whole call. `user_messages` = list of what the caller says.
    Returns every turn, all tool calls in order, and token/latency totals.
    """

    if reset:
        reset_db()

    messages = []
    turns = []

    if include_greeting:
        turns.append(run_turn(messages, GREETING_TRIGGER))

    for text in user_messages:
        turns.append(run_turn(messages, text))

    return {
        "turns": turns,
        "all_tool_calls": [c for t in turns for c in t["tool_calls"]],
        "total_llm_ms": sum(t["llm_ms"] for t in turns),
        "total_input_tokens": sum(t["input_tokens"] for t in turns),
        "total_output_tokens": sum(t["output_tokens"] for t in turns),
    }


if __name__ == "__main__":
    out = run_conversation(["Mere daant mein bahut dard ho raha hai."])
    for t in out["turns"]:
        print("\nUSER :", t["user"])
        for c in t["tool_calls"]:
            print("TOOL :", c["name"], c["args"])
        print("ZAARA:", t["reply"])
    print("\nTokens in/out:",
          out["total_input_tokens"], "/", out["total_output_tokens"])
    print("LLM time (ms):", out["total_llm_ms"])