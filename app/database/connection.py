import os

import psycopg
from dotenv import load_dotenv

from app.exceptions import DatabaseError


load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")


def get_connection():

    try:
        return psycopg.connect(DATABASE_URL)

    except psycopg.Error as error:

        raise DatabaseError(
            "Unable to connect to the database."
        ) from error