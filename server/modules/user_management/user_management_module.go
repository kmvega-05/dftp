package modules

import (
	"encoding/json"
	"fmt"
	"os"

	"dftp/src/server/entities"

	"golang.org/x/crypto/bcrypt"
)

// UsersDB mantiene la lista de usuarios cargados desde el JSON
type UsersDB struct {
	Users []entities.User `json:"users"`
}

// LoadUsers carga la lista de usuarios desde el archivo JSON
func LoadUsers(path string) (*UsersDB, error) {
	file, err := os.Open(path)
	if err != nil {
		return nil, fmt.Errorf("no se pudo abrir el archivo de usuarios: %w", err)
	}

	defer file.Close()

	var db UsersDB
	if err := json.NewDecoder(file).Decode(&db); err != nil {
		return nil, fmt.Errorf("error al parsear JSON de usuarios: %w", err)
	}

	return &db, nil
}

// FindUser busca un usuario por nombre
func (db *UsersDB) FindUser(username string) *entities.User {
	for _, u := range db.Users {
		if u.Username == username {
			return &u
		}
	}
	return nil
}

// ValidateUser valida usuario y contraseña usando bcrypt
func (db *UsersDB) ValidateUser(username, password string) (*entities.User, bool) {
	user := db.FindUser(username)
	if user == nil {
		return nil, false
	}

	// Compara la contraseña recibida con el hash almacenado
	err := bcrypt.CompareHashAndPassword([]byte(user.Password), []byte(password))
	if err != nil {
		return nil, false
	}

	return user, true
}
