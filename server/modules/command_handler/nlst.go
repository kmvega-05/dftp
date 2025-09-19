package commandHandler

import (
	"fmt"

	"dftp-server/entities"
	fsm "dftp-server/modules/file_system_manager"
)

func HandleNLST(session *entities.Session, cmd entities.Command) {

    var err error
    
	if !RequireAuth(session) {
		return
	}

	if !session.AcceptDataConnection() {
		session.ControlConn.Write([]byte("425 Can't open data connection.\r\n"))
		return
	}

	session.ControlConn.Write([]byte("150 Opening data connection for file list.\r\n"))

    files, err := fsm.ListDir(session.CurrentUser.Home, session.VirtualWorkingDir)
    
	if err != nil {
        session.ControlConn.Write([]byte("550 Failed to list directory.\r\n"))
        return
    }

    for _, name := range files {
        session.DataConn.Write([]byte(fmt.Sprintf("%s\r\n", name)))
    }

	session.DataConn.Close()
    session.DataConn = nil

    session.ControlConn.Write([]byte("226 Transfer complete.\r\n"))
}

