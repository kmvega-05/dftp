package commandHandler

import (
	"dftp-server/entities"
	fsm "dftp-server/modules/file_system_manager"
	"fmt"
	"os"
)

func HandleLIST(session *entities.Session, cmd entities.Command) {
	content, fileInfo, err := fsm.ReadFileContent(session.CurrentUser.Home, session.VirtualWorkingDir)
	if err == nil {
		session.DataConn.Write([]byte(ShowFileInfo(fileInfo)))
		session.DataConn.Write([]byte(fmt.Sprintf("%s\r\n", content)))
		session.DataConn.Close()
		session.DataConn = nil
		session.ControlConn.Write([]byte("226 Transfer complete.\r\n"))
	} else {
		HandleNLST(session, cmd)
	}
}

func ShowFileInfo(file os.FileInfo) string {
	var ans string = file.Name() + "\n" +
		file.Mode().String() + "\n" +
		fmt.Sprint(file.Size()) + "\n"
	return ans
}
