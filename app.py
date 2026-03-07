import pickle
import numpy as np
import os
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

from flask import Flask, render_template, request, redirect, url_for, Response
import sqlite3
from datetime import datetime

app = Flask(__name__)

model = pickle.load(open("risk_model.pkl", "rb"))

# ---------------- DATABASE ---------------- #

def init_db():
    conn = sqlite3.connect("hospital.db")
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS patients (
            patient_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            age INTEGER,
            gender TEXT,
            weight REAL,
            blood_pressure TEXT,
            heart_rate INTEGER,
            existing_conditions TEXT,
            risk_level TEXT,
            registration_date TEXT
        )
    """)

    conn.commit()
    conn.close()


# ---------------- HOME ---------------- #

@app.route("/")
def home():
    return render_template("index.html")


# ---------------- REGISTER PAGE ---------------- #

@app.route("/register")
def register_page():
    return render_template("register.html")


# ---------------- SAVE PATIENT ---------------- #

@app.route("/submit_patient", methods=["POST"])
def submit_patient():

    name = request.form["name"]
    age = int(request.form["age"])
    gender = request.form["gender"]
    weight = float(request.form["weight"])
    blood_pressure = request.form["blood_pressure"]
    heart_rate = int(request.form["heart_rate"])
    existing_conditions = request.form["existing_conditions"]

    # Risk calculation
    prediction = model.predict([[age, heart_rate]])
    risk_level = prediction[0]

    date = datetime.now().strftime("%Y-%m-%d")

    conn = sqlite3.connect("hospital.db")
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO patients
        (name, age, gender, weight, blood_pressure, heart_rate, existing_conditions, risk_level, registration_date)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (name, age, gender, weight, blood_pressure, heart_rate, existing_conditions, risk_level, date))

    conn.commit()
    conn.close()

    return redirect("/patients")


# ---------------- VIEW PATIENTS ---------------- #

@app.route("/patients")
def patients():

    conn = sqlite3.connect("hospital.db")
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM patients")
    data = cursor.fetchall()

    conn.close()

    return render_template("patients.html", patients=data)


# ---------------- DELETE ---------------- #

@app.route("/delete/<int:id>")
def delete_patient(id):

    conn = sqlite3.connect("hospital.db")
    cursor = conn.cursor()

    cursor.execute("DELETE FROM patients WHERE patient_id=?", (id,))
    conn.commit()

    conn.close()

    return redirect("/patients")


# ---------------- EDIT ---------------- #

@app.route("/edit/<int:id>", methods=["GET", "POST"])
def edit_patient(id):

    conn = sqlite3.connect("hospital.db")
    cursor = conn.cursor()

    if request.method == "POST":

        name = request.form["name"]
        age = int(request.form["age"])
        heart_rate = int(request.form["heart_rate"])

        if age > 60 or heart_rate > 100:
            risk_level = "High"
        elif age > 40:
            risk_level = "Medium"
        else:
            risk_level = "Low"

        cursor.execute("""
            UPDATE patients
            SET name=?, age=?, heart_rate=?, risk_level=?
            WHERE patient_id=?
        """, (name, age, heart_rate, risk_level, id))

        conn.commit()
        conn.close()

        return redirect("/patients")

    cursor.execute("SELECT * FROM patients WHERE patient_id=?", (id,))
    patient = cursor.fetchone()

    conn.close()

    return render_template("edit.html", patient=patient)


# ---------------- EXPORT CSV ---------------- #

@app.route("/export")
def export():

    conn = sqlite3.connect("hospital.db")
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM patients")
    data = cursor.fetchall()

    conn.close()

    def generate():
        yield "ID,Name,Age,Gender,Weight,BP,HeartRate,Conditions,RiskLevel,Date\n"
        for row in data:
            yield ",".join(str(x) for x in row) + "\n"

    return Response(
        generate(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=patients.csv"}
    )

@app.route("/dashboard")
def dashboard():

    conn = sqlite3.connect("hospital.db")
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM patients")
    total = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM patients WHERE risk_level='High'")
    high = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM patients WHERE risk_level='Medium'")
    medium = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM patients WHERE risk_level='Low'")
    low = cursor.fetchone()[0]

    conn.close()

    return render_template(
        "dashboard.html",
        total=total,
        high=high,
        medium=medium,
        low=low
    )

# ---------------- RUN ---------------- #

if __name__ == "__main__":
    init_db()
    app.run(debug=True)