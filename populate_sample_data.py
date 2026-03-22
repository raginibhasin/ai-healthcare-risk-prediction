import sqlite3
import random
from datetime import datetime, timedelta

# Sample data
names = [
    "John Smith", "Sarah Johnson", "Michael Brown", "Emily Davis", "David Wilson",
    "Lisa Garcia", "James Miller", "Maria Rodriguez", "Robert Martinez", "Jennifer Lopez",
    "William Anderson", "Linda Taylor", "Richard Thomas", "Patricia Jackson", "Charles White",
    "Barbara Harris", "Daniel Martin", "Susan Thompson", "Matthew Garcia", "Dorothy Clark",
    "Joseph Lewis", "Nancy Walker", "Thomas Hall", "Karen Allen", "Christopher Young"
]

conditions = [
    "Hypertension", "Diabetes", "Asthma", "Arthritis", "Heart Disease",
    "None", "Migraine", "Thyroid Disorder", "Depression", "Anxiety",
    "COPD", "Kidney Disease", "Liver Disease", "Cancer", "Stroke"
]

departments = ["Cardiology", "Neurology", "Internal Medicine", "Orthopedics", "Dermatology"]

def init_db():
    conn = sqlite3.connect("hospital.db")
    cursor = conn.cursor()

    # Add department column if not exists
    try:
        cursor.execute("ALTER TABLE patients ADD COLUMN department TEXT")
    except:
        pass

    # Create medical_history table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS medical_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER,
            date TEXT,
            type TEXT,
            notes TEXT,
            doctor TEXT,
            FOREIGN KEY (patient_id) REFERENCES patients (patient_id)
        )
    """)

    conn.commit()
    conn.close()

def add_sample_patients():
    conn = sqlite3.connect("hospital.db")
    cursor = conn.cursor()

    for i in range(25):
        name = random.choice(names)
        age = random.randint(18, 85)
        gender = random.choice(["Male", "Female"])
        weight = round(random.uniform(50, 120), 1)
        systolic = random.randint(90, 180)
        diastolic = random.randint(60, 120)
        bp = f"{systolic}/{diastolic}"
        heart_rate = random.randint(60, 120)
        condition = random.choice(conditions)
        department = random.choice(departments)

        # Simple risk calculation
        if age > 60 or heart_rate > 100 or systolic > 140:
            risk = "High"
        elif age > 40 or systolic > 130:
            risk = "Medium"
        else:
            risk = "Low"

        date = (datetime.now() - timedelta(days=random.randint(0, 365))).strftime("%Y-%m-%d")

        cursor.execute("""
            INSERT INTO patients
            (name, age, gender, weight, blood_pressure, heart_rate, existing_conditions, risk_level, registration_date, department)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (name, age, gender, weight, bp, heart_rate, condition, risk, date, department))

        patient_id = cursor.lastrowid

        # Add some medical history
        for _ in range(random.randint(1, 5)):
            history_date = (datetime.now() - timedelta(days=random.randint(0, 365))).strftime("%Y-%m-%d")
            history_type = random.choice(["Visit", "Test", "Medication", "Surgery", "Consultation"])
            notes = f"Patient {name} had a {history_type.lower()} on {history_date}."
            doctor = f"Dr. {random.choice(['Smith', 'Johnson', 'Brown', 'Davis', 'Wilson'])}"

            cursor.execute("""
                INSERT INTO medical_history (patient_id, date, type, notes, doctor)
                VALUES (?, ?, ?, ?, ?)
            """, (patient_id, history_date, history_type, notes, doctor))

    conn.commit()
    conn.close()
    print("Sample data added successfully!")

if __name__ == "__main__":
    init_db()
    add_sample_patients()