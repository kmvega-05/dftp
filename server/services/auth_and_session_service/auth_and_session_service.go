package auth_and_session_service

import (
	"strings"

	"dftp-server/entities"
	"dftp-server/modules/user_management"
)

// HandleCommand procesa los comandos de autenticación y reinicio
func HandleCommand(session *entities.Session, cmd entities.Command) {
	switch strings.ToUpper(cmd.Name) {
	case "USER":
		handleUSER(session, cmd.Args)
	case "PASS":
		handlePASS(session, cmd.Args)
	case "REIN":
		handleREIN(session)
	case "ACCT":
		session.ControlConn.Write([]byte("202 Comando ACCT no implementado\r\n"))
	default:
		session.ControlConn.Write([]byte("502 Comando no implementado\r\n"))
	}
}

// handleUSER guarda el usuario pendiente en la sesión
func handleUSER(session *entities.Session, args []string) {
	if len(args) < 1 {
		session.ControlConn.Write([]byte("501 Syntax error : [command USER expecting 1 argument(s)]\r\n"))
		return
	}

	username := args[0]

	// Mantener todos los campos iguales excepto PendingUser
	session.Update(session.CurrentUser, session.IsAuthenticated, session.VirtualWorkingDir, username)
	session.ControlConn.Write([]byte("331 User name okay, need password\r\n"))
}

// handlePASS valida el password usando user_management_module
func handlePASS(session *entities.Session, args []string) {
	if len(args) < 1 {
		session.ControlConn.Write([]byte("501 Syntax error : [command PASS expecting 1 argument(s)]\r\n"))
		return
	}

	password := args[0]

	if session.PendingUser == "" {
		session.ControlConn.Write([]byte("503 Bad sequence of commands\r\n"))
		return
	}

	db, err := user_management.LoadUsers("configs/users.json")
	if err != nil {
		session.ControlConn.Write([]byte("550 Error interno del servidor\r\n"))
		return
	}

	user, ok := db.ValidateUser(session.PendingUser, password)
	if !ok {
		session.Update(nil, false, "/", "")
		session.ControlConn.Write([]byte("530 Not logged in\r\n"))
		return
	}

	// Al iniciar sesión, la ruta virtual empieza en "/"
	session.Update(user, true, "/", "")
	session.ControlConn.Write([]byte("230 User logged in, proceed\r\n"))
}

// handleREIN resetea la sesión
func handleREIN(session *entities.Session) {
	session.Update(nil, false, "/", "")
	session.ControlConn.Write([]byte("220 Session reset\r\n"))
}
