package commandHandler

import (
	"fmt"
	"dftp-server/entities"
)

// HandleUSER guarda el usuario pendiente en la sesión
func HandleUSER(session *entities.Session, cmd entities.Command) {
	// Verificar que se haya pasado al menos un argumento (nombre de usuario)
	if !RequireArgs(session, cmd, 1) {
		return
	}

	username := cmd.Args[0]

	// Reinicia la sesión (cierra conexiones, resetea estado)
	session.RestartSession()

	// Guardar el usuario pendiente
	session.PendingUser = username

	// Responder con código FTP 331
	session.Reply(331, fmt.Sprintf("User %s okay, need password", username))
}