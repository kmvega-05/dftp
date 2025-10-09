package commandHandler

import (
	"fmt"
	"dftp-server/entities"
)

// HandlePWD maneja el comando PWD, que devuelve el directorio de trabajo actual.
func HandlePWD(session *entities.Session, cmd entities.Command) {
	// Requiere que el usuario esté autenticado
	if !RequireAuth(session) {
		return
	}

	// Responder con código FTP 257 y el directorio virtual actual
	session.Reply(257, fmt.Sprintf("\"%s\" is current directory.", session.VirtualWorkingDir))
}