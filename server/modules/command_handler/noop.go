package commandHandler

import (
	"dftp-server/entities"
)

func HandleNOOP(session *entities.Session, cmd entities.Command) {
	if !RequireAuth(session) {
		return
	}
	session.ControlConn.Write([]byte("200 OK"))
}
