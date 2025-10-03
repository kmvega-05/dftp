package commandHandler

import (
	"dftp-server/entities"
	"runtime"
)

func HandleSYST(session *entities.Session, cmd entities.Command) {
	so := runtime.GOOS
	session.ControlConn.Write([]byte("215 SO Type is " + so + "\r\n"))
}
