package commandHandler

import (
	"dftp-server/entities"
)

// HandlePWD maneja el comando PWD, que devuelve el directorio de trabajo actual.
func HandlePWD(session *entities.Session, cmd entities.Command) {
	
	if !RequireAuth(session) {
		return
	}

	session.ControlConn.Write([]byte("257 \"" + session.VirtualWorkingDir + "\" is current directory.\r\n"))
}