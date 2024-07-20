import sqlite3


error = sqlite3.OperationalError


class Database:
    def __init__(self, database):
        self.database = database

    def get(self) -> tuple[sqlite3.Connection, sqlite3.Cursor]:
        conn: sqlite3.Connection = sqlite3.connect(self.database, check_same_thread=False)
        cur = conn.cursor()
        
        return conn, cur

    def release(self, connection: sqlite3.Connection, cursor: sqlite3.Cursor):
        cursor.close()
        connection.commit()


pool = Database('data/sqlite.db')
