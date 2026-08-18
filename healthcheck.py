import os
import sys

import psycopg2


try:
    connection = psycopg2.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        connect_timeout=3,
    )

    connection.close()

except Exception:
    sys.exit(1)

sys.exit(0)