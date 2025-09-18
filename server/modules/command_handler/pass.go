package commandHandler

import (
	"dftp-server/entities"
	"dftp-server/modules/user_management"
)

// handlePASS valida el password usando user_management_module
func HandlePASS(session *entities.Session, cmd entities.Command) {
	
	if !RequireArgs(session, cmd, 1) {
		return
	}

	password := cmd.Args[0]

	// Debe haberse recibido previamente USER
	if session.PendingUser == "" {
		session.ControlConn.Write([]byte("503 Bad sequence of commands\r\n"))
		return
	}

	// Cargar base de usuarios
	db, err := user_management.LoadUsers("configs/users.json")
	if err != nil {
		session.ControlConn.Write([]byte("550 Internal server error\r\n"))
		return
	}

	// Validar credenciales
	user, ok := db.ValidateUser(session.PendingUser, password)
	if !ok {
		// Falla la autenticación: PendingUser se mantiene
		session.ControlConn.Write([]byte("530 Not logged in\r\n"))
		return
	}

	// Autenticación exitosa
	session.CurrentUser = user
	session.IsAuthenticated = true
	session.VirtualWorkingDir = "/"
	session.PendingUser = "" 

	session.ControlConn.Write([]byte("230 User logged in, proceed\r\n"))
}
