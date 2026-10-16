import logging
import re

from app.database.connection import get_connection
from app.exceptions import PatientError

logger = logging.getLogger(__name__)


def _normalize(name):
    return re.sub(r"\s+", " ", (name or "").strip().lower())


def _same_person(spoken_name, stored_name):
    """Same person only if the full name matches exactly (ignoring case and spaces).

    Wrongly merging two different people is worse than creating a duplicate,
    because a merged record shows one person's appointment under another.
    Duplicates are easy to fix later in the admin screen.
    """
    a = _normalize(spoken_name)
    b = _normalize(stored_name)

    return bool(a) and a == b


def get_or_create_patient(name, phone):
    connection = None
    cursor = None

    try:
        logger.info("Looking up patient by phone and name")

        connection = get_connection()
        cursor = connection.cursor()

        # One phone number can belong to several people (family).
        cursor.execute(
            """
            SELECT id, name, phone
            FROM patients
            WHERE phone = %s
            ORDER BY id;
            """,
            (phone,)
        )

        candidates = cursor.fetchall()

        for patient in candidates:
            if _same_person(name, patient[1]):
                logger.info("Existing patient found: ID %s", patient[0])
                return patient

        logger.info(
            "No patient with this name on this phone (%s on file). Creating new patient",
            len(candidates)
        )

        cursor.execute(
            """
            INSERT INTO patients (name, phone)
            VALUES (%s, %s)
            RETURNING id, name, phone;
            """,
            (name, phone)
        )

        new_patient = cursor.fetchone()

        connection.commit()

        logger.info("New patient created: ID %s", new_patient[0])

        return new_patient

    except Exception as error:
        if connection:
            connection.rollback()

        logger.exception("Patient operation failed")

        raise PatientError(
            "Unable to create or retrieve patient."
        ) from error

    finally:
        if cursor:
            cursor.close()

        if connection:
            connection.close()