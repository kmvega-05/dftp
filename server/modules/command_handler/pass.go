package commandHandler

import (
	"dftp-server/entities"
	"dftp-server/modules/user_management"
)

// HandlePASS valida el password usando el módulo user_management
func HandlePASS(session *entities.Session, cmd entities.Command) {
	// Verificar que se pase al menos un argumento (el password)
	if !RequireArgs(session, cmd, 1) {
		return
	}

	password := cmd.Args[0]

	// Debe haberse recibido previamente USER
	if session.PendingUser == "" {
		session.Reply(503, "Bad sequence of commands")
		return
	}

	// Cargar base de usuarios
	db, err := user_management.LoadUsers("configs/users.json")
	if err != nil {
		session.Reply(550, "Internal server error")
		return
	}

	// Validar credenciales
	user, ok := db.ValidateUser(session.PendingUser, password)
	if !ok {
		// Falla la autenticación: PendingUser se mantiene
		session.Reply(530, "Not logged in")
		return
	}

	// Autenticación exitosa
	session.CurrentUser = user
	session.IsAuthenticated = true
	session.VirtualWorkingDir = "/"
	session.PendingUser = "" 

	session.Reply(230, "User logged in, proceed")
}
