# run this once (or from Flask shell) to set a password for a test student
from db import get_db_connection
import bcrypt

password = "student123"
hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
conn = get_db_connection()
cursor = conn.cursor()
cursor.execute("UPDATE student SET password_hash = %s WHERE studentid = %s", (hashed, "2024-123456"))
conn.commit()
cursor.close()
conn.close()
print("Password set")