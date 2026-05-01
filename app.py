import pickle
import numpy as np
import os
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

from flask import Flask, render_template, request, redirect, url_for, Response, flash
import sqlite3
from datetime import datetime, timedelta
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SelectField, SubmitField
from wtforms.validators import DataRequired, Email, Length
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_principal import Principal, identity_loaded, UserNeed, RoleNeed
from post_login import PostLoginHandler
from auth_utils import hash_password, check_password
from permissions import require_role
from logging_config import security_logger
from models import EncryptedPatient
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'fallback_secret_key')
app.config['WTF_CSRF_ENABLED'] = True

limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

principals = Principal(app)

model = pickle.load(open("risk_model.pkl", "rb"))

# User class
class User(UserMixin):
    def __init__(self, id, name, email, role, department, username=None):
        self.id = id
        self.name = name
        self.email = email
        self.role = role
        self.department = department
        self.username = username

# Mock users database (with hashed passwords for demo)
users = {
    "admin": User(1, "John Admin", "admin@hospital.com", "admin", "administration", "admin"),
    "doctor": User(2, "Dr. Sarah Mitchell", "doctor@hospital.com", "doctor", "cardiology", "doctor"),
    "patient": User(3, "Patient User", "patient@hospital.com", "patient", "general", "patient"),
    "staff": User(4, "Staff User", "staff@hospital.com", "staff", "support", "staff")
}

@login_manager.user_loader
def load_user(user_id):
    # First check mock users
    for user in users.values():
        if user.id == int(user_id):
            return user
    # Then check db
    conn = sqlite3.connect("hospital.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, email, role, department, username FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return User(row[0], row[1], row[2], row[3], row[4], row[5])
    return None

def init_db():
    conn = sqlite3.connect("hospital.db")
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            email TEXT UNIQUE,
            password_hash TEXT,
            role TEXT,
            name TEXT,
            department TEXT,
            created_at TEXT,
            failed_attempts INTEGER DEFAULT 0,
            locked_until TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS patients (
            patient_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            age INTEGER,
            gender TEXT,
            weight REAL,
            blood_pressure_encrypted TEXT,
            heart_rate INTEGER,
            existing_conditions_encrypted TEXT,
            risk_level TEXT,
            registration_date TEXT,
            department TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS medical_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER,
            date TEXT,
            type TEXT,
            notes_encrypted TEXT,
            doctor TEXT,
            FOREIGN KEY (patient_id) REFERENCES patients (patient_id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS activity_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT,
            timestamp TEXT,
            details TEXT
        )
    """)

    conn.commit()
    conn.close()

@identity_loaded.connect_via(app)
def on_identity_loaded(sender, identity):
    identity.user = current_user

    if hasattr(current_user, 'id'):
        identity.provides.add(UserNeed(current_user.id))

    if hasattr(current_user, 'role'):
        identity.provides.add(RoleNeed(current_user.role))


class RegisterForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    name = StringField('Full Name', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=8)])
    role = SelectField('Role', choices=[('admin', 'Admin'), ('doctor', 'Doctor'), ('patient', 'Patient'), ('staff', 'Staff')], validators=[DataRequired()])
    department = StringField('Department')
    submit = SubmitField('Register')


class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    role = SelectField('Role', choices=[('admin', 'Admin'), ('doctor', 'Doctor'), ('patient', 'Patient'), ('staff', 'Staff')], validators=[DataRequired()])
    submit = SubmitField('Sign In')


# ---------------- USER REGISTER ---------------- #

@app.route("/")
def home():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


# ---------------- LOGIN ---------------- #

@app.route("/login", methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def login():
    form = LoginForm()
    if form.validate_on_submit():
        username = form.username.data
        password = form.password.data
        role = form.role.data
        user = None

        # Check mock users (with hashed check for demo)
        if username in users and check_password(password, hash_password('password')) and users[username].role == role:
            user = users[username]
        else:
            # Check db
            conn = sqlite3.connect("hospital.db")
            cursor = conn.cursor()
            cursor.execute("SELECT id, name, email, role, department, username, password_hash, failed_attempts, locked_until FROM users WHERE username = ?", (username,))
            row = cursor.fetchone()
            conn.close()
            if row:
                user_id, name, email, db_role, department, db_username, password_hash, failed_attempts, locked_until = row
                if locked_until and datetime.now() < datetime.fromisoformat(locked_until):
                    flash('Account locked due to too many failed attempts.')
                    security_logger.info(f"Login attempt on locked account: {username}")
                    return render_template("login.html", form=form)
                if check_password(password, password_hash) and db_role == role:
                    user = User(user_id, name, email, db_role, department, db_username)
                    # Reset failed attempts
                    conn = sqlite3.connect("hospital.db")
                    cursor = conn.cursor()
                    cursor.execute("UPDATE users SET failed_attempts = 0 WHERE id = ?", (user_id,))
                    conn.commit()
                    conn.close()
                    security_logger.info(f"Successful login: {username} ({role})")
                else:
                    # Increment failed attempts
                    failed_attempts += 1
                    locked_until = None
                    if failed_attempts >= 5:
                        locked_until = (datetime.now() + timedelta(minutes=15)).isoformat()
                    conn = sqlite3.connect("hospital.db")
                    cursor = conn.cursor()
                    cursor.execute("UPDATE users SET failed_attempts = ?, locked_until = ? WHERE id = ?", (failed_attempts, locked_until, user_id))
                    conn.commit()
                    conn.close()
                    security_logger.warning(f"Failed login attempt: {username} (attempt {failed_attempts})")

        if user:
            login_user(user)
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('dashboard'))
        else:
            flash('Invalid credentials or role mismatch')
    return render_template("login.html", form=form)


@app.route("/logout")
@login_required
def logout():
    security_logger.info(f"Logout: {current_user.username} ({current_user.role})")
    logout_user()
    return redirect(url_for('home'))


# ---------------- USER REGISTER ---------------- #

@app.route("/user_register", methods=['GET', 'POST'])
@login_required
@require_role('admin')
def user_register():
    form = RegisterForm()
    if form.validate_on_submit():
        username = form.username.data
        email = form.email.data
        name = form.name.data
        password = hash_password(form.password.data)
        role = form.role.data
        department = form.department.data or ''

        conn = sqlite3.connect("hospital.db")
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO users (username, email, password_hash, role, name, department, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (username, email, password, role, name, department, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            conn.commit()
            flash('Registration successful! Please log in.')
            security_logger.info(f"User registered: {username} ({role}) by {current_user.username}")
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Username or email already exists.')
        finally:
            conn.close()
    return render_template("user_register.html", form=form)


# ---------------- REGISTER PAGE ---------------- #

@app.route("/register")
def register_page():
    conn = sqlite3.connect("hospital.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM patients")
    patients = cursor.fetchall()
    conn.close()
    return render_template("register.html", patients=patients)


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
    department = request.form.get("department", "General")

    # Risk calculation
    prediction = model.predict([[age, heart_rate]])
    risk_level = prediction[0]

    date = datetime.now().strftime("%Y-%m-%d")

    # Encrypt sensitive data
    from models import EncryptedPatient
    encrypted_data = EncryptedPatient.encrypt_row(name, age, gender, weight, blood_pressure, heart_rate, existing_conditions, risk_level, date, department)

    conn = sqlite3.connect("hospital.db")
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO patients
        (name, age, gender, weight, blood_pressure_encrypted, heart_rate, existing_conditions_encrypted, risk_level, registration_date, department)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, encrypted_data)

    conn.commit()
    conn.close()

    security_logger.info(f"Patient registered: {name} by {current_user.username}")

    return redirect("/patients")


# ---------------- VIEW PATIENTS ---------------- #

@app.route("/patients")
@login_required
def patients():

    conn = sqlite3.connect("hospital.db")
    cursor = conn.cursor()

    # Build query with filters
    query = "SELECT * FROM patients WHERE 1=1"
    params = []

    risk = request.args.get('risk')
    if risk:
        query += " AND risk_level = ?"
        params.append(risk)

    department = request.args.get('department')
    if department:
        query += " AND department = ?"
        params.append(department)

    age_min = request.args.get('age_min')
    if age_min:
        query += " AND age >= ?"
        params.append(int(age_min))

    age_max = request.args.get('age_max')
    if age_max:
        query += " AND age <= ?"
        params.append(int(age_max))

    condition = request.args.get('condition')
    if condition:
        query += " AND existing_conditions LIKE ?"
        params.append(f"%{condition}%")

    search = request.args.get('search')
    if search:
        query += " AND (name LIKE ? OR patient_id LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%"])

    cursor.execute(query, params)
    rows = cursor.fetchall()

    conn.close()

    # Decrypt and create patient objects
    patients_list = [EncryptedPatient(row) for row in rows]

    security_logger.info(f"Patients viewed by {current_user.username} ({current_user.role})")

    return render_template("patients.html", patients=patients_list)


# ---------------- DELETE ---------------- #

@app.route("/delete/<int:id>")
@login_required
@require_role('admin')
def delete_patient(id):

    conn = sqlite3.connect("hospital.db")
    cursor = conn.cursor()

    cursor.execute("DELETE FROM patients WHERE patient_id=?", (id,))
    conn.commit()

    conn.close()

    security_logger.warning(f"Patient deleted: ID {id} by {current_user.username}")

    return redirect("/patients")


# ---------------- EDIT ---------------- #

@app.route("/edit/<int:id>", methods=["GET", "POST"])
def edit_patient(id):

    conn = sqlite3.connect("hospital.db")
    cursor = conn.cursor()

    if request.method == "POST":

        name = request.form["name"]
        age = int(request.form["age"])
        gender = request.form["gender"]
        weight = float(request.form["weight"])
        blood_pressure = request.form["blood_pressure"]
        heart_rate = int(request.form["heart_rate"])
        existing_conditions = request.form["existing_conditions"]
        department = request.form["department"]

        # Risk calculation
        prediction = model.predict([[age, heart_rate]])
        risk_level = prediction[0]

        cursor.execute("""
            UPDATE patients
            SET name=?, age=?, gender=?, weight=?, blood_pressure=?, heart_rate=?, existing_conditions=?, risk_level=?, department=?
            WHERE patient_id=?
        """, (name, age, gender, weight, blood_pressure, heart_rate, existing_conditions, risk_level, department, id))

        conn.commit()
        conn.close()

        return redirect("/patients")

    cursor.execute("SELECT * FROM patients WHERE patient_id=?", (id,))
    patient = cursor.fetchone()

    conn.close()

    return render_template("edit.html", patient=patient)


# ---------------- PATIENT PROFILE ---------------- #

@app.route("/patient/<int:id>")
def patient_profile(id):

    conn = sqlite3.connect("hospital.db")
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM patients WHERE patient_id=?", (id,))
    patient = cursor.fetchone()

    cursor.execute("SELECT * FROM medical_history WHERE patient_id=? ORDER BY date DESC", (id,))
    history = cursor.fetchall()

    conn.close()

    return render_template("patient_profile.html", patient=patient, history=history)


# ---------------- ADD MEDICAL HISTORY ---------------- #

@app.route("/add_history/<int:id>", methods=["POST"])
def add_medical_history(id):

    history_type = request.form["type"]
    notes = request.form["notes"]
    doctor = request.form["doctor"]
    date = datetime.now().strftime("%Y-%m-%d")

    conn = sqlite3.connect("hospital.db")
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO medical_history (patient_id, date, type, notes, doctor)
        VALUES (?, ?, ?, ?, ?)
    """, (id, date, history_type, notes, doctor))

    conn.commit()
    conn.close()

    return redirect(f"/patient/{id}")


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
@login_required
def dashboard():
    handler = PostLoginHandler()
    data = handler.get_dashboard_data()
    if current_user.role == 'admin':
        return render_template("admin_dashboard.html", **data)
    elif current_user.role == 'doctor':
        return render_template("doctors.html", **data)  # or doctor_dashboard if exists
    elif current_user.role == 'patient':
        return render_template("patient_profile.html", **data)  # or patient_dashboard
    else:
        return render_template("dashboard.html", **data)

@app.route("/")
def dashboard_page():

    total_patients = 45
    total_doctors = 10
    total_appointments = 20
    high_risk = 6

    return render_template(
        "dashboard.html",
        total_patients=total_patients,
        total_doctors=total_doctors,
        total_appointments=total_appointments,
        high_risk=high_risk
    )

@app.route("/risk")
def risk():
    return render_template("risk_analysis.html")

@app.route("/predict", methods=["POST"])
def predict():

    age = float(request.form["age"])
    weight = float(request.form["weight"])
    heart_rate = float(request.form["heart_rate"])

    data = [[age, weight, heart_rate]]

    prediction = model.predict(data)

    if prediction[0] == 0:
        result = "Low Risk"
    elif prediction[0] == 1:
        result = "Medium Risk"
    else:
        result = "High Risk"

    return render_template("risk_analysis.html", prediction=result)

@app.route("/risk-dashboard")
def risk_dashboard():

    import pandas as pd

    data = pd.read_csv("patients.csv")

    total_patients = len(data)

    high_risk = len(data[data["RiskLevel"] == "High"])
    medium_risk = len(data[data["RiskLevel"] == "Medium"])
    low_risk = len(data[data["RiskLevel"] == "Low"])

    return render_template(
        "risk_dashboard.html",
        total=total_patients,
        high=high_risk,
        medium=medium_risk,
        low=low_risk
    )

@app.route("/doctors")
def doctors():

    import pandas as pd

    data = pd.read_csv("doctors.csv")

    doctors = data.to_dict(orient="records")

    return render_template("doctors.html", doctors=doctors)

@app.route("/doctor/<int:doctor_id>")
def doctor_profile(doctor_id):

    import pandas as pd

    # Read doctors data
    doctors_data = pd.read_csv("doctors.csv")
    doctor = doctors_data[doctors_data['ID'] == doctor_id].to_dict(orient='records')

    if not doctor:
        return "Doctor not found", 404

    doctor = doctor[0]

    # Read appointments data to get doctor's schedule
    try:
        appointments_data = pd.read_csv("appointments.csv")
        doctor_appointments = appointments_data[appointments_data['Doctor'] == doctor['Name']].to_dict(orient='records')
    except:
        doctor_appointments = []

    # Read patients data to get doctor's patients
    try:
        patients_data = pd.read_csv("patients.csv")
        doctor_patients = patients_data[patients_data['Department'] == doctor['Department']].to_dict(orient='records')
    except:
        doctor_patients = []

    return render_template("doctor_profile.html",
                         doctor=doctor,
                         appointments=doctor_appointments,
                         patients=doctor_patients)

@app.route("/appointment")
def appointment():
    import pandas as pd

    # Read doctors data for the form
    doctors_data = pd.read_csv("doctors.csv")
    doctors = doctors_data.to_dict(orient='records')

    success = request.args.get('success', 0)

    return render_template("appointment.html", doctors=doctors, success=success)

@app.route("/book-appointment", methods=["POST"])
def book_appointment():

    import csv
    import os

    patient = request.form["patient"]
    doctor = request.form["doctor"]
    date = request.form["date"]
    time = request.form["time"]
    reason = request.form["reason"]
    phone = request.form.get("phone", "")

    # Check if appointments.csv exists and has headers
    file_exists = os.path.isfile("appointments.csv")

    with open("appointments.csv", "a", newline="") as file:
        writer = csv.writer(file)

        # Write headers if file doesn't exist
        if not file_exists:
            writer.writerow(["ID", "Patient", "Doctor", "Date", "Time", "Reason", "Phone", "Status"])

        # Get next ID
        if file_exists:
            with open("appointments.csv", "r") as read_file:
                lines = read_file.readlines()
                if len(lines) > 1:  # More than just header
                    last_line = lines[-1].strip().split(",")
                    next_id = int(last_line[0]) + 1
                else:
                    next_id = 1
        else:
            next_id = 1

        writer.writerow([next_id, patient, doctor, date, time, reason, phone, "Scheduled"])

    return redirect("/appointment?success=1")

@app.route("/appointments-dashboard")
def appointments_dashboard():

    import pandas as pd

    try:
        data = pd.read_csv("appointments.csv")
        appointments = data.to_dict(orient="records")
    except:
        appointments = []

    return render_template(
        "appointments_dashboard.html",
        appointments=appointments
    )

@app.route("/export_appointments")
def export_appointments():
    import pandas as pd

    try:
        data = pd.read_csv("appointments.csv")
    except:
        data = pd.DataFrame(columns=["ID", "Patient", "Doctor", "Date", "Time", "Reason", "Phone", "Status"])

    def generate():
        yield "ID,Patient,Doctor,Date,Time,Reason,Phone,Status\n"
        for _, row in data.iterrows():
            yield ",".join(str(x) for x in row) + "\n"

    return Response(
        generate(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=appointments.csv"}
    )

@app.route("/medicines")
def medicines():

    import pandas as pd

    data = pd.read_csv("medicines.csv")

    medicines = data.to_dict(orient="records")

    # Calculate low stock alerts
    low_stock = [med for med in medicines if med['Quantity'] <= med['Min_Stock_Level']]
    expiring_soon = [med for med in medicines if pd.to_datetime(med['Expiry_Date']) < pd.Timestamp.now() + pd.DateOffset(months=3)]

    return render_template(
        "medicines.html",
        medicines=medicines,
        low_stock_count=len(low_stock),
        expiring_count=len(expiring_soon)
    )

@app.route("/add_medicine", methods=["GET", "POST"])
def add_medicine():
    if request.method == "POST":
        import pandas as pd

        # Read existing data
        try:
            data = pd.read_csv("medicines.csv")
            new_id = data['ID'].max() + 1
        except:
            new_id = 1

        # Create new medicine entry
        new_medicine = {
            'ID': new_id,
            'Name': request.form["name"],
            'Category': request.form["category"],
            'Dosage_Form': request.form["dosage_form"],
            'Strength': request.form["strength"],
            'Manufacturer': request.form["manufacturer"],
            'Quantity': int(request.form["quantity"]),
            'Min_Stock_Level': int(request.form["min_stock_level"]),
            'Unit_Price': float(request.form["unit_price"]),
            'Expiry_Date': request.form["expiry_date"],
            'Batch_Number': request.form["batch_number"],
            'Description': request.form.get("description", "")
        }

        # Append to CSV
        df = pd.DataFrame([new_medicine])
        df.to_csv("medicines.csv", mode='a', header=False, index=False)

        return redirect("/medicines")

    return render_template("add_medicine.html")

@app.route("/update_stock/<int:medicine_id>", methods=["POST"])
def update_stock(medicine_id):
    import pandas as pd

    quantity_change = int(request.form["quantity_change"])
    operation = request.form["operation"]  # 'add' or 'subtract'

    # Read data
    data = pd.read_csv("medicines.csv")

    # Find and update the medicine
    mask = data['ID'] == medicine_id
    if operation == 'add':
        data.loc[mask, 'Quantity'] += quantity_change
    else:
        data.loc[mask, 'Quantity'] = max(0, data.loc[mask, 'Quantity'].iloc[0] - quantity_change)

    # Save back to CSV
    data.to_csv("medicines.csv", index=False)

    return redirect("/medicines")

@app.route("/export_medicines")
def export_medicines():
    import pandas as pd

    data = pd.read_csv("medicines.csv")

    def generate():
        yield "ID,Name,Category,Dosage_Form,Strength,Manufacturer,Quantity,Min_Stock_Level,Unit_Price,Expiry_Date,Batch_Number,Description\n"
        for _, row in data.iterrows():
            yield ",".join(str(x) for x in row) + "\n"

    return Response(
        generate(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=medicines.csv"}
    )

@app.route("/export_risk_data")
def export_risk_data():
    import pandas as pd

    try:
        data = pd.read_csv("patients.csv")
    except:
        data = pd.DataFrame(columns=["PatientID", "Name", "Age", "Gender", "RiskLevel"])

    def generate():
        yield "PatientID,Name,Age,Gender,RiskLevel\n"
        for _, row in data.iterrows():
            yield ",".join(str(x) for x in row) + "\n"

    return Response(
        generate(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=risk_assessment_data.csv"}
    )

@app.route("/settings")
@login_required
def settings():
    if current_user.role != 'admin':
        return redirect(url_for('dashboard'))
    return render_template("settings.html")

@app.route("/reports")
def reports():
    return render_template("reports.html")

@app.route("/admin")
@login_required
def admin_dashboard():
    if current_user.role != 'admin':
        return redirect(url_for('dashboard'))
    handler = PostLoginHandler()
    data = handler.get_dashboard_data()
    return render_template("admin_dashboard.html", **data)

@app.route("/admin/users", methods=['GET', 'POST'])
@login_required
def admin_users():
    if current_user.role != 'admin':
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        name = request.form['name']
        password = request.form['password']
        role = request.form['role']
        department = request.form.get('department', '')

        conn = sqlite3.connect("hospital.db")
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO users (username, email, password, role, name, department, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (username, email, password, role, name, department, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            conn.commit()
            flash('User added successfully!')
        except sqlite3.IntegrityError:
            flash('Username or email already exists.')
        finally:
            conn.close()
        return redirect(url_for('admin_users'))
    
    conn = sqlite3.connect("hospital.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, name, email, role, department, created_at FROM users")
    db_users = cursor.fetchall()
    conn.close()
    
    # Convert to dict format
    users = []
    for row in db_users:
        users.append({
            "id": row[0],
            "username": row[1],
            "name": row[2],
            "email": row[3],
            "role": row[4],
            "department": row[5],
            "status": "active",  # Assume active for now
            "last_login": "N/A"  # Not tracking yet
        })
    
    # Add mock users that are not in db
    mock_users = [
        {"id": 1, "username": "admin", "name": "John Admin", "email": "admin@hospital.com", "role": "admin", "department": "administration", "status": "active", "last_login": "2024-01-15 08:15"},
        {"id": 2, "username": "doctor", "name": "Dr. Sarah Mitchell", "email": "doctor@hospital.com", "role": "doctor", "department": "cardiology", "status": "active", "last_login": "2024-01-15 09:30"},
        {"id": 3, "username": "patient", "name": "Patient User", "email": "patient@hospital.com", "role": "patient", "department": "general", "status": "active", "last_login": "2024-01-15 10:00"}
    ]
    
    # Filter out mock users that are already in db
    existing_usernames = {u["username"] for u in users}
    for mock in mock_users:
        if mock["username"] not in existing_usernames:
            users.append(mock)
    
    return render_template("admin_users.html",
                         users=users,
                         total_users=len(users),
                         active_users=len([u for u in users if u["status"] == "active"]),
                         inactive_users=len([u for u in users if u["status"] == "inactive"]),
                         admin_users=len([u for u in users if u["role"] == "admin"]))

@app.route("/admin/logs")
def admin_logs():
    # Mock log data
    logs = [
        {"timestamp": "2024-01-15 14:30:25", "level": "INFO", "category": "auth", "user": "Dr. Sarah Mitchell", "message": "User logged in successfully", "ip_address": "192.168.1.100"},
        {"timestamp": "2024-01-15 14:25:10", "level": "WARNING", "category": "system", "user": "System", "message": "High memory usage detected", "ip_address": "localhost"},
        {"timestamp": "2024-01-15 14:20:45", "level": "ERROR", "category": "database", "user": "System", "message": "Failed to connect to database", "ip_address": "localhost"},
        {"timestamp": "2024-01-15 14:15:30", "level": "INFO", "category": "user", "user": "John Admin", "message": "Created new patient record", "ip_address": "192.168.1.101"},
        {"timestamp": "2024-01-15 14:10:15", "level": "INFO", "category": "api", "user": "System", "message": "API request processed successfully", "ip_address": "192.168.1.102"}
    ]
    return render_template("admin_logs.html",
                         logs=logs,
                         total_logs=len(logs),
                         info_logs=len([l for l in logs if l["level"] == "INFO"]),
                         warning_logs=len([l for l in logs if l["level"] == "WARNING"]),
                         error_logs=len([l for l in logs if l["level"] == "ERROR"]))

@app.route("/admin/backup")
def admin_backup():
    # Mock backup data
    backups = [
        {"id": "bk_001", "name": "Daily Backup - 2024-01-15", "description": "Automated daily backup", "type": "full", "size": "2.4 GB", "status": "completed", "created": "2024-01-15 02:00"},
        {"id": "bk_002", "name": "Weekly Backup - 2024-01-14", "description": "Weekly full backup", "type": "full", "size": "2.3 GB", "status": "completed", "created": "2024-01-14 02:00"},
        {"id": "bk_003", "name": "Manual Backup - Patient Data", "description": "Manual backup before migration", "type": "manual", "size": "1.8 GB", "status": "completed", "created": "2024-01-13 15:30"},
        {"id": "bk_004", "name": "Incremental Backup - 2024-01-13", "description": "Incremental backup", "type": "incremental", "size": "245 MB", "status": "completed", "created": "2024-01-13 02:00"},
        {"id": "bk_005", "name": "System Backup - 2024-01-12", "description": "Full system backup", "type": "full", "size": "3.1 GB", "status": "failed", "created": "2024-01-12 02:00"}
    ]
    return render_template("admin_backup.html",
                         backups=backups,
                         total_backups=len(backups),
                         successful_backups=len([b for b in backups if b["status"] == "completed"]),
                         failed_backups=len([b for b in backups if b["status"] == "failed"]),
                         backup_size="9.8 GB")

if __name__ == "__main__":
    init_db()
    app.run(debug=True)