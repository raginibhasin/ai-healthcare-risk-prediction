from flask_principal import Permission, RoleNeed
from flask_login import current_user
from functools import wraps
from flask import abort

# Define roles
admin_permission = Permission(RoleNeed('admin'))
doctor_permission = Permission(RoleNeed('doctor'))
patient_permission = Permission(RoleNeed('patient'))
staff_permission = Permission(RoleNeed('staff'))

def require_role(role):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated or current_user.role != role:
                abort(403)
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def require_permission(permission):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not permission.allows(current_user):
                abort(403)
            return f(*args, **kwargs)
        return decorated_function
    return decorator