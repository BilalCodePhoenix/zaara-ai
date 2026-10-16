from app.database.connection import get_connection


def get_doctors():
    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute("""
        SELECT id, name, specialization, consultation_fee
        FROM doctors
        WHERE is_active = TRUE;
    """)

    doctors = cursor.fetchall()

    cursor.close()
    connection.close()

    return doctors