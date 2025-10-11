import json
import bcrypt
import os

def create_users_file():
    # Crear directorio data si no existe
    os.makedirs('data', exist_ok=True)
    
    # Contraseñas en texto plano para encriptar
    plain_passwords = {
        "test": "password123",
        "admin": "admin123"
    }
    
    users = []
    
    for username, plain_password in plain_passwords.items():
        # Encriptar contraseña
        hashed_password = bcrypt.hashpw(plain_password.encode('utf-8'), bcrypt.gensalt())
        
        user = {
            "username": username,
            "password": hashed_password.decode('utf-8'),  # Convertir bytes a string
            "home_directory": f"/home/{username}"
        }
        users.append(user)
    
    # Crear estructura del JSON
    data = {
        "users": users
    }
    
    # Guardar en archivo
    with open('data/users.json', 'w') as f:
        json.dump(data, f, indent=2)
    
    print("Archivo users.json creado exitosamente")
    print("Usuarios creados:")
    for user in users:
        print(f"  - {user['username']}: {user['home_directory']}")

if __name__ == "__main__":
    create_users_file()