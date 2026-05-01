from auth_utils import encrypt_data, decrypt_data

class EncryptedPatient:
    def __init__(self, db_row):
        self.patient_id = db_row[0]
        self.name = db_row[1]
        self.age = db_row[2]
        self.gender = db_row[3]
        self.weight = db_row[4]
        self.blood_pressure = decrypt_data(db_row[5]) if db_row[5] else None
        self.heart_rate = db_row[6]
        self.existing_conditions = decrypt_data(db_row[7]) if db_row[7] else None
        self.risk_level = db_row[8]
        self.registration_date = db_row[9]
        self.department = db_row[10]

    @staticmethod
    def encrypt_row(name, age, gender, weight, blood_pressure, heart_rate, existing_conditions, risk_level, registration_date, department):
        return (
            name, age, gender, weight,
            encrypt_data(blood_pressure) if blood_pressure else None,
            heart_rate,
            encrypt_data(existing_conditions) if existing_conditions else None,
            risk_level, registration_date, department
        )