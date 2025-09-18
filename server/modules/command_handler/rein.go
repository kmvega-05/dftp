package commandHandler

import (
    "dftp-server/entities"
)

// handleREIN reinicia la sesión actual.
func HandleREIN(session *entities.Session, cmd entities.Command) {
	session.RestartSession()
	session.ControlConn.Write([]byte("220 Session reset\r\n"))
}
