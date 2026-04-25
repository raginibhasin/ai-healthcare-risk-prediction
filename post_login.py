# post_login.py
# This file contains code for using the healthcare app after user login
# It provides role-based functionality and dashboard management

import sqlite3
from datetime import datetime
from flask import current_app, render_template, redirect, url_for
from flask_login import current_user
from auth_utils import decrypt_data

class PostLoginHandler:
    """
    Handles post-login functionality for the healthcare management app.
    Provides role-based access and dashboard management.
    """

    def __init__(self):
        self.db_path = "hospital.db"

    def get_dashboard_data(self):
        """
        Get dashboard data based on user role.
        Returns appropriate data for the user's dashboard.
        """
        if current_user.role == 'admin':
            return self._get_admin_dashboard_data()
        elif current_user.role == 'doctor':
            return self._get_doctor_dashboard_data()
        elif current_user.role == 'patient':
            return self._get_patient_dashboard_data()
        else:
            return self._get_general_dashboard_data()

    def _get_admin_dashboard_data(self):
        """Get data for admin dashboard"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # System statistics
        cursor.execute("SELECT COUNT(*) FROM patients")
        total_patients = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM medical_history")
        total_records = cursor.fetchone()[0]

        # Recent activities
        cursor.execute("""
            SELECT date, type, notes_encrypted, doctor
            FROM medical_history
            ORDER BY date DESC LIMIT 5
        """)
        recent_activities_raw = cursor.fetchall()
        recent_activities = []
        for activity in recent_activities_raw:
            date, type_, encrypted_notes, doctor = activity
            notes = decrypt_data(encrypted_notes) if encrypted_notes else ""
            recent_activities.append((date, type_, notes, doctor))

        # Risk distribution
        cursor.execute("SELECT risk_level, COUNT(*) FROM patients GROUP BY risk_level")
        risk_stats = dict(cursor.fetchall())

        conn.close()

        return {
            'total_patients': total_patients,
            'total_records': total_records,
            'recent_activities': recent_activities,
            'risk_stats': risk_stats,
            'user_role': 'admin'
        }

    def _get_doctor_dashboard_data(self):
        """Get data for doctor dashboard"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Doctor's patients
        cursor.execute("""
            SELECT p.patient_id, p.name, p.risk_level, p.department
            FROM patients p
            JOIN medical_history mh ON p.patient_id = mh.patient_id
            WHERE mh.doctor = ?
            GROUP BY p.patient_id
        """, (current_user.name,))
        doctor_patients = cursor.fetchall()

        # Today's appointments (mock data since appointments table may not exist)
        today_appointments = [
            {'time': '09:00', 'patient': 'John Doe', 'type': 'Check-up'},
            {'time': '11:00', 'patient': 'Jane Smith', 'type': 'Consultation'},
            {'time': '14:00', 'patient': 'Bob Johnson', 'type': 'Follow-up'}
        ]

        # Pending tasks
        pending_tasks = [
            'Review lab results for Patient ID: 123',
            'Update treatment plan for Patient ID: 456',
            'Schedule follow-up for Patient ID: 789'
        ]

        conn.close()

        return {
            'doctor_patients': doctor_patients,
            'today_appointments': today_appointments,
            'pending_tasks': pending_tasks,
            'user_role': 'doctor'
        }

    def _get_patient_dashboard_data(self):
        """Get data for patient dashboard"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Patient's own data (assuming patient can view their own info)
        # In a real app, you'd link user to patient record
        cursor.execute("SELECT * FROM patients LIMIT 1")  # Mock: get first patient
        patient_info = cursor.fetchone()

        # Medical history
        if patient_info:
            cursor.execute("""
                SELECT date, type, notes, doctor
                FROM medical_history
                WHERE patient_id = ?
                ORDER BY date DESC
            """, (patient_info[0],))
            medical_history = cursor.fetchall()
        else:
            medical_history = []

        # Upcoming appointments (mock)
        upcoming_appointments = [
            {'date': '2024-01-20', 'time': '10:00', 'doctor': 'Dr. Smith', 'type': 'Check-up'},
            {'date': '2024-01-25', 'time': '14:30', 'doctor': 'Dr. Johnson', 'type': 'Consultation'}
        ]

        conn.close()

        return {
            'patient_info': patient_info,
            'medical_history': medical_history,
            'upcoming_appointments': upcoming_appointments,
            'user_role': 'patient'
        }

    def _get_general_dashboard_data(self):
        """Get general dashboard data for other roles"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM patients")
        total_patients = cursor.fetchone()[0]

        cursor.execute("SELECT risk_level, COUNT(*) FROM patients GROUP BY risk_level")
        risk_distribution = dict(cursor.fetchall())

        conn.close()

        return {
            'total_patients': total_patients,
            'risk_distribution': risk_distribution,
            'user_role': 'general'
        }

    def render_dashboard(self):
        """
        Render the appropriate dashboard template based on user role.
        """
        data = self.get_dashboard_data()

        if current_user.role == 'admin':
            return render_template('admin_dashboard.html', **data)
        elif current_user.role == 'doctor':
            return render_template('doctors.html', **data)
        elif current_user.role == 'patient':
            return render_template('patient_profile.html', patient=data['patient_info'], history=data['medical_history'])
        else:
            return render_template('dashboard.html', **data)

    def check_permissions(self, required_role):
        """
        Check if current user has required role for accessing certain features.
        """
        role_hierarchy = {
            'admin': 3,
            'doctor': 2,
            'patient': 1,
            'general': 0
        }

        user_level = role_hierarchy.get(current_user.role, 0)
        required_level = role_hierarchy.get(required_role, 0)

        return user_level >= required_level

    def log_user_activity(self, action, details=""):
        """
        Log user activities for audit purposes.
        """
        # In a real app, you'd store this in a database
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] User {current_user.name} ({current_user.role}): {action} - {details}"
        print(log_entry)  # In production, write to log file or database

# Usage example:
# from post_login import PostLoginHandler
#
# @app.route('/dashboard')
# @login_required
# def dashboard():
#     handler = PostLoginHandler()
#     return handler.render_dashboard()
#
# @app.route('/admin/patients')
# @login_required
# def admin_patients():
#     handler = PostLoginHandler()
#     if not handler.check_permissions('admin'):
#         return redirect(url_for('dashboard'))
#     # Proceed with admin functionality
#     handler.log_user_activity('accessed_admin_patients', 'Viewing patient management')
#     return render_template('admin_patients.html')