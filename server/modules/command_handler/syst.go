package commandHandler

import (
	"dftp-server/entities"
	"runtime"
	"fmt"
)

// HandleSYST responde con el sistema operativo del servidor.
func HandleSYST(session *entities.Session, cmd entities.Command) {
	so := runtime.GOOS
	session.Reply(215, fmt.Sprintf("SO Type is %s", so))
}
