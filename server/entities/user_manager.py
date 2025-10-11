import json
import os
import bcrypt

def get_users_file_path():
    """Obtiene la ruta al archivo de usuarios"""
    return os.path.join(os.path.dirname(__file__), '..', 'data', 'users.json')

def get_user_by_name(username):
    """Busca un usuario por nombre, retorna el usuario completo o None"""
    try:
        users_file = get_users_file_path()
        with open(users_file, 'r') as f:
            data = json.load(f)
        
        for user in data.get('users', []):
            if user['username'] == username:
                return user
        return None
    except Exception as e:
        print(f"Error reading users file: {e}")
        return None

def user_exists(username):
    """Verifica si un usuario existe"""
    return get_user_by_name(username) is not None

def validate_password(username, password):
    """Valida la contraseña de un usuario"""
    user = get_user_by_name(username)
    if user and 'password' in user:
        # Verificar la contraseña encriptada
        return bcrypt.checkpw(password.encode('utf-8'), user['password'].encode('utf-8'))
    return False