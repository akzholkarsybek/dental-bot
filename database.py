import os

import psycopg2
from dotenv import load_dotenv

load_dotenv()


def get_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
    )


def update_customer_name(customer_id, name):
    connection = get_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE customers
                SET name = %s
                WHERE id = %s;
                """,
                (name, customer_id),
            )

        connection.commit()

    finally:
        connection.close()

def get_or_create_customer(telegram_id):
    connection = get_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO customers (telegram_id)
                VALUES (%s)
                ON CONFLICT (telegram_id)
                DO NOTHING
                RETURNING id, telegram_id, name;
                """,
                (telegram_id,),
            )

            customer = cursor.fetchone()

            if customer is None:
                cursor.execute(
                    """
                    SELECT id, telegram_id, name
                    FROM customers
                    WHERE telegram_id = %s;
                    """,
                    (telegram_id,),
                )

                customer = cursor.fetchone()

        connection.commit()
        return customer

    finally:
        connection.close()

def save_message(customer_id, role, content):
    connection = get_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO messages
                    (customer_id, role, content)
                VALUES
                    (%s, %s, %s);
                """,
                (customer_id, role, content),
            )

        connection.commit()

    finally:
        connection.close()


def get_recent_messages(customer_id, limit=10):
    connection = get_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT role, content
                FROM messages
                WHERE customer_id = %s
                ORDER BY created_at DESC, id DESC
                LIMIT %s;
                """,
                (customer_id, limit),
            )

            rows = cursor.fetchall()

        return list(reversed(rows))

    finally:
        connection.close()


if __name__ == "__main__":
    connection = get_connection()

    try:
        print("PostgreSQL connected successfully.")
    finally:
        connection.close()