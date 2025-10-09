package commandHandler

import (
	"dftp-server/entities"
	fsm "dftp-server/modules/file_system_manager"
	"fmt"
)

func HandleDELE(session *entities.Session, cmd entities.Command) {
	if !RequireAuth(session) {
		return
	}
	if !RequireArgs(session, cmd, 1) {
		return
	}
	dirArg := cmd.Args[0]
	_, err := fsm.RemoveDir(session.CurrentUser.Home, session.VirtualWorkingDir, dirArg)
	if err != nil {
		session.ControlConn.Write([]byte(fmt.Sprintf("550 %s\r\n", err.Error())))
		return
	}
	session.ControlConn.Write([]byte(fmt.Sprintf("257 \"%s\" directory deleted.\r\n", dirArg)))
}
