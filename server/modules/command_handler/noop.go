package commandHandler

import "dftp-server/entities"

// HandleNOOP responde al comando NOOP, que sirve para mantener viva la sesión.
func HandleNOOP(session *entities.Session, cmd entities.Command) {
	// Responder con código FTP 200 (comando OK)
	session.Reply(200, "OK")
}