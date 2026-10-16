"""Admin database functions (the "service layer").

Plain Python functions that read and write PostgreSQL. They know nothing
about web pages. They follow the same pattern as app/database/queries.py:
raw SQL through get_connection().

Safety rules used everywhere in this file:
  * Values are ALWAYS passed as %s parameters, never pasted into the SQL
    text. That is what stops SQL injection.
  * `with get_connection() as conn:` commits when the block succeeds,
    rolls back if anything raises, and always closes the connection.
"""

import logging
from datetime import date, datetime, timedelta, timezone

from psycopg.rows import dict_row

from app.admin.errors import DuplicateError, InvalidStateError, NotFoundError
from app.database.connection import get_connection

logger = logging.getLogger(__name__)

DOCTOR_COLUMNS = "id, name, specialization, consultation_fee, is_active"

# The clinic runs on Indian time (no daylight saving, so a fixed offset is safe
# and needs no extra packages). "Today" means today IN INDIA, not on the server.
CLINIC_TZ = timezone(timedelta(hours=5, minutes=30), "IST")

# Columns the admin may edit. Used to build UPDATE statements safely:
# column NAMES can't be parameters, so we only ever use names from this list.
EDITABLE_DOCTOR_COLUMNS = ("name", "specialization", "consultation_fee")


def _duplicate_exists(cur, name: str, specialization: str, exclude_id=None) -> bool:
    """True if a doctor with the same name (any capitalisation) and the same
    specialization already exists. `exclude_id` skips the doctor being edited."""
    cur.execute(
        """
        SELECT 1
        FROM doctors
        WHERE lower(name) = lower(%s)
          AND specialization = %s
          AND id IS DISTINCT FROM %s
        LIMIT 1;
        """,
        (name, specialization, exclude_id),
    )
    return cur.fetchone() is not None


def list_doctors() -> list[dict]:
    """All doctors, active ones first. (The voice agent's get_doctors()
    only returns ACTIVE doctors; the admin must see everyone.)"""
    with get_connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            f"""
            SELECT {DOCTOR_COLUMNS}
            FROM doctors
            ORDER BY is_active DESC, lower(name), id;
            """
        )
        return cur.fetchall()


def create_doctor(
    name: str,
    specialization: str,
    consultation_fee,
    is_active: bool = True,
) -> dict:
    with get_connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        if _duplicate_exists(cur, name, specialization):
            raise DuplicateError(
                f"{name} is already listed as {specialization}."
            )

        cur.execute(
            f"""
            INSERT INTO doctors (name, specialization, consultation_fee, is_active)
            VALUES (%s, %s, %s, %s)
            RETURNING {DOCTOR_COLUMNS};
            """,
            (name, specialization, consultation_fee, is_active),
        )
        doctor = cur.fetchone()

    logger.info("Admin added doctor id=%s (%s)", doctor["id"], doctor["specialization"])
    return doctor


def update_doctor(doctor_id: int, changes: dict) -> dict:
    """Change name / specialization / fee. Only the keys in `changes` are touched."""
    changes = {k: v for k, v in changes.items() if k in EDITABLE_DOCTOR_COLUMNS}

    with get_connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        # Lock this doctor's row so two admins can't edit it at the same moment.
        cur.execute(
            f"SELECT {DOCTOR_COLUMNS} FROM doctors WHERE id = %s FOR UPDATE;",
            (doctor_id,),
        )
        current = cur.fetchone()
        if current is None:
            raise NotFoundError("Doctor not found.")

        if not changes:
            return current

        new_name = changes.get("name", current["name"])
        new_spec = changes.get("specialization", current["specialization"])
        if _duplicate_exists(cur, new_name, new_spec, exclude_id=doctor_id):
            raise DuplicateError(f"{new_name} is already listed as {new_spec}.")

        # Column names come from the allow-list above, values are parameters.
        set_clause = ", ".join(f"{column} = %s" for column in changes)
        cur.execute(
            f"UPDATE doctors SET {set_clause} WHERE id = %s RETURNING {DOCTOR_COLUMNS};",
            (*changes.values(), doctor_id),
        )
        doctor = cur.fetchone()

    logger.info("Admin updated doctor id=%s fields=%s", doctor_id, list(changes))
    return doctor


def set_doctor_active(doctor_id: int, is_active: bool) -> dict:
    """The on/off toggle. We never DELETE a doctor: past appointments point
    at them (foreign key), so deactivating hides them from the voice
    assistant while keeping the history."""
    with get_connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            f"""
            UPDATE doctors
            SET is_active = %s
            WHERE id = %s
            RETURNING {DOCTOR_COLUMNS};
            """,
            (is_active, doctor_id),
        )
        doctor = cur.fetchone()
        if doctor is None:
            raise NotFoundError("Doctor not found.")

    logger.info("Admin set doctor id=%s active=%s", doctor_id, is_active)
    return doctor


# =====================================================================
# Shared helpers
# =====================================================================

def _today() -> date:
    return datetime.now(CLINIC_TZ).date()


def _like(text: str) -> str:
    """Turn what the admin typed into a safe LIKE pattern.
    A typed % or _ must be searched for literally, not act as a wildcard."""
    escaped = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def count_upcoming_for_doctor(doctor_id: int) -> int:
    """Booked appointments today or later. Used to warn before deactivating."""
    with get_connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT 1 FROM doctors WHERE id = %s;", (doctor_id,))
        if cur.fetchone() is None:
            raise NotFoundError("Doctor not found.")
        cur.execute(
            """
            SELECT COUNT(*) AS n
            FROM appointments
            WHERE doctor_id = %s
              AND status = 'booked'
              AND appointment_date >= %s;
            """,
            (doctor_id, _today()),
        )
        return cur.fetchone()["n"]


# =====================================================================
# Patients (read-only)
# =====================================================================

def list_patients(q: str | None = None, limit: int = 25, offset: int = 0) -> dict:
    """Newest patients first, with their appointment counts.
    `q` searches name (any capitalisation) or phone number (any part)."""
    today = _today()

    where, where_params = "", []
    if q and q.strip():
        pattern = _like(q.strip())
        where = "WHERE (p.name ILIKE %s OR p.phone LIKE %s)"
        where_params = [pattern, pattern]

    with get_connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(f"SELECT COUNT(*) AS total FROM patients p {where};", where_params)
        total = cur.fetchone()["total"]

        cur.execute(
            f"""
            SELECT p.id, p.name, p.phone, p.created_at,
                   COUNT(a.id) AS total_appointments,
                   COUNT(a.id) FILTER (
                       WHERE a.status = 'booked' AND a.appointment_date >= %s
                   ) AS upcoming_appointments,
                   MIN(a.appointment_date + a.appointment_time) FILTER (
                       WHERE a.status = 'booked' AND a.appointment_date >= %s
                   ) AS next_appointment
            FROM patients p
            LEFT JOIN appointments a ON a.patient_id = p.id
            {where}
            GROUP BY p.id
            ORDER BY p.created_at DESC, p.id DESC
            LIMIT %s OFFSET %s;
            """,
            [today, today, *where_params, limit, offset],
        )
        items = cur.fetchall()

    return {"items": items, "total": total}


# =====================================================================
# Appointments
# =====================================================================

_APPT_COLUMNS = """
    a.id, a.appointment_date, a.appointment_time, a.status,
    p.id AS patient_id, p.name AS patient_name, p.phone AS patient_phone,
    d.id AS doctor_id, d.name AS doctor_name, d.specialization AS doctor_specialization
"""
_APPT_FROM = """
    FROM appointments a
    JOIN patients p ON p.id = a.patient_id
    JOIN doctors d ON d.id = a.doctor_id
"""


def list_appointments(
    scope: str = "upcoming",
    on_date: date | None = None,
    doctor_id: int | None = None,
    status: str | None = None,
    q: str | None = None,
    limit: int = 25,
    offset: int = 0,
) -> dict:
    """Filtered appointment list.

    scope: "upcoming" = today and later (soonest first),
           "past" = before today (newest first), "all" = everything (newest first).
    on_date: one exact day; it overrides `scope` (soonest first).
    """
    conditions, params = [], []

    if on_date is not None:
        conditions.append("a.appointment_date = %s")
        params.append(on_date)
    elif scope == "upcoming":
        conditions.append("a.appointment_date >= %s")
        params.append(_today())
    elif scope == "past":
        conditions.append("a.appointment_date < %s")
        params.append(_today())

    if doctor_id is not None:
        conditions.append("a.doctor_id = %s")
        params.append(doctor_id)
    if status is not None:
        conditions.append("a.status = %s")
        params.append(status)
    if q and q.strip():
        pattern = _like(q.strip())
        conditions.append("(p.name ILIKE %s OR p.phone LIKE %s)")
        params += [pattern, pattern]

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    soonest_first = on_date is not None or scope == "upcoming"
    order = (
        "a.appointment_date, a.appointment_time, a.id"
        if soonest_first
        else "a.appointment_date DESC, a.appointment_time DESC, a.id DESC"
    )

    with get_connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(f"SELECT COUNT(*) AS total {_APPT_FROM} {where};", params)
        total = cur.fetchone()["total"]

        cur.execute(
            f"SELECT {_APPT_COLUMNS} {_APPT_FROM} {where} "
            f"ORDER BY {order} LIMIT %s OFFSET %s;",
            [*params, limit, offset],
        )
        items = cur.fetchall()

    return {"items": items, "total": total}


def update_appointment_status(appointment_id: int, new_status: str) -> dict:
    """Move a BOOKED appointment to cancelled or completed.

    Cancelling frees the time slot: your unique index
    (doctor, date, time) only applies while status = 'booked'."""
    with get_connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT status FROM appointments WHERE id = %s FOR UPDATE;",
            (appointment_id,),
        )
        current = cur.fetchone()
        if current is None:
            raise NotFoundError("Appointment not found.")
        if current["status"] != "booked":
            raise InvalidStateError(
                f"This appointment is already {current['status']}, so it can't be changed."
            )

        cur.execute(
            "UPDATE appointments SET status = %s WHERE id = %s;",
            (new_status, appointment_id),
        )
        cur.execute(
            f"SELECT {_APPT_COLUMNS} {_APPT_FROM} WHERE a.id = %s;",
            (appointment_id,),
        )
        appointment = cur.fetchone()

    logger.info("Admin set appointment id=%s status=%s", appointment_id, new_status)
    return appointment