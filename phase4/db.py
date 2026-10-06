
import mysql.connector
from mysql.connector import pooling
from contextlib import contextmanager

MYSQL_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "root",  # Update with your local MySQL password
    "database": "telecom_warehouse",
    "port": 3306,
    "pool_name": "telecom_pool",
    "pool_size": 5,
    "pool_reset_session": True
}

try:
    connection_pool = pooling.MySQLConnectionPool(**MYSQL_CONFIG)
except mysql.connector.Error as err:
    connection_pool = None


@contextmanager
def get_db_connection():
    """Yields a managed MySQL database connection from the pool."""
    if connection_pool is None:
        raise ConnectionError("Database connection pool is not initialized.")
    conn = connection_pool.get_connection()
    try:
        yield conn
    finally:
        conn.close()