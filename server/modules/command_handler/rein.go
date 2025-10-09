package commandHandler

import "dftp-server/entities"

// HandleREIN reinicia la sesión actual.
func HandleREIN(session *entities.Session, cmd entities.Command) {
	// Reinicia todos los campos de la sesión
	session.RestartSession()

	// Responder con código FTP 220 (servicio listo)
	session.Reply(220, "Session reset")
}