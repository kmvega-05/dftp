package entities

import "net"

// User representa un usuario cargado desde user_manager_module
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
