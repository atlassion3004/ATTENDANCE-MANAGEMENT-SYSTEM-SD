import mysql.connector
import os
from dotenv import load_dotenv

load_dotenv()

def get_db_connection():
    # Check if we are using TiDB (set TIDB_MODE=True on Render)
    if os.getenv("TIDB_MODE", "false").lower() == "true":
        ca_cert = os.path.join(os.path.dirname(__file__), 'tidb-ca.pem')
        return mysql.connector.connect(
            host=os.getenv("DB_HOST"),
            port=int(os.getenv("DB_PORT", 4000)),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            database=os.getenv("DB_NAME"),
            ssl_ca=ca_cert,
            ssl_disabled=False,
        )
    
    # Local fallback (unchanged)
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "127.0.0.1"),
        port=int(os.getenv("DB_PORT", 3306)),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_NAME", "attendance_system"),
        ssl_disabled=True   # local MySQL without SSL
    )