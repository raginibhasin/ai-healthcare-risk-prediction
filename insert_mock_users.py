import sqlite3
from auth_utils import hash_password
from datetime import datetime

# Mock users
users = [
    {"username": "admin", "name": "John Admin", "email": "admin@hospital.com", "role": "admin", "department": "administration"},
    {"username": "doctor", "name": "Dr. Sarah Mitchell", "email": "doctor@hospital.com", "role": "doctor", "department": "cardiology"},
    {"username": "patient", "name": "Patient User", "email": "patient@hospital.com", "role": "patient", "department": "general"},
    {"username": "staff", "name": "Staff User", "email": "staff@hospital.com", "role": "staff", "department": "support"}
]

password_hash = hash_password('password')

conn = sqlite3.connect("hospital.db")
cursor = conn.cursor()

for user in users:
    try:
        cursor.execute("""
            INSERT INTO users (username, email, password_hash, role, name, department, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (user["username"], user["email"], password_hash, user["role"], user["name"], user["department"], datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    except sqlite3.IntegrityError:
        print(f"User {user['username']} already exists.")

conn.commit()
conn.close()
print("Mock users added successfully!")