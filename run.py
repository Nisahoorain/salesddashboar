import mysql.connector
from mysql.connector import Error

def test_connection():
    connection = None
    try:
        # Establish the connection
        connection = mysql.connector.connect(
            host='157.173.210.232',
            user='nisa',
            password='nisa123??',
            database='nisa_sales'
        )

        if connection.is_connected():
            db_info = connection.get_server_info()
            print(f"Connected to MariaDB server version {db_info}")
            cursor = connection.cursor()
            cursor.execute("SELECT DATABASE();")
            record = cursor.fetchone()
            print(f"Connected to database: {record}")
            cursor.close()

    except Error as e:
        print(f"Error while connecting to MariaDB: {e}")

    finally:
        if connection and connection.is_connected():
            connection.close()
            print("MariaDB connection is closed")

if __name__ == "__main__":
    test_connection()
