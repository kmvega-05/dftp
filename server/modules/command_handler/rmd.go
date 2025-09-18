package commandHandler

import (
	"fmt"
	"dftp-server/entities"
	fsm "dftp-server/modules/file_system_manager"
)	

// HandleRMD elimina un directorio vacío
// Si se usa una ruta absoluta, se elimina desde el root del home del usuario
// Si se usa una ruta relativa, se elimina desde el directorio virtual actual
func HandleRMD(session *entities.Session, cmd entities.Command) {
	if !RequireAuth(session) {
		return
	}

	if !RequireArgs(session, cmd, 1) {
		return
	}

	dirArg := cmd.Args[0]

	// Delega la eliminiación del directorio al File System Manager
	virtualPath, err := fsm.RemoveDir(session.CurrentUser.Home, session.VirtualWorkingDir, dirArg)
	
	if err != nil {
		session.ControlConn.Write([]byte(fmt.Sprintf("550 %s\r\n", err.Error())))
		return
	}

	session.ControlConn.Write([]byte(fmt.Sprintf("250 Directory \"%s\" removed.\r\n", virtualPath)))
}