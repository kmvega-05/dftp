package entities

import "net"

// User representa un usuario cargado desde user_management_module
type User struct {
	Username string 	// Nombre de usuario
	Password string 	// Contraseña del usuario
	Home     string 	// Directorio raíz del usuario
}

// Session mantiene el estado de una conexión FTP con un cliente
type Session struct {
	Conn            net.Conn	// Conexión de red con el cliente
	CurrentUser     *User 		// Usuario autenticado actualmente
	IsAuthenticated bool		// Indica si el usuario ha sido autenticado
	WorkingDir      string 		// Directorio actual de trabajo
	PendingUser     string 		// Usuario enviado por USER, en espera de PASS
}

// NewSession crea una nueva sesión FTP para un cliente
func NewSession(conn net.Conn) *Session {
	return &Session{
		Conn:            conn,
		CurrentUser:     nil,
		IsAuthenticated: false,
		WorkingDir:      "/",
		PendingUser:     "",
	}
}

// Update actualiza los campos de la sesión
func (s *Session) Update(currentUser *User, isAuthenticated bool, workingDir string, pendingUser string) {
	s.CurrentUser = currentUser
	s.IsAuthenticated = isAuthenticated
	s.WorkingDir = workingDir
	s.PendingUser = pendingUser
}