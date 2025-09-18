package commandHandler

import "dftp-server/entities"

// handleUSER guarda el usuario pendiente en la sesión
func HandleUSER(session *entities.Session, cmd entities.Command) {
	
	if !RequireArgs(session, cmd, 1) {
		return
	}
	username := cmd.Args[0]

	session.RestartSession()

	// Actualiza el usuario pendiente en la sesión
	session.PendingUser = username
	session.ControlConn.Write([]byte("331 User name okay, need password\r\n"))
}