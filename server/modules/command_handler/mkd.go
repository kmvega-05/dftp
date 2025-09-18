package commandHandler

import (
	"fmt"
	"dftp-server/entities"
	fsm "dftp-server/modules/file_system_manager"
)

// HandleMKD crea un nuevo directorio
// Si se usa una ruta absoluta, se crea desde el root del home del usuario
// Si se usa una ruta relativa, se crea desde el directorio virtual actual
func HandleMKD(session *entities.Session, cmd entities.Command) {
	if !RequireAuth(session) {
		return
	}

	if !RequireArgs(session, cmd, 1) {
		return
	}

	dirArg := cmd.Args[0]

	// Delega la creación del directorio al File System Manager
	virtualPath, err := fsm.CreateDir(session.CurrentUser.Home, session.VirtualWorkingDir, dirArg)
	
	if err != nil {
		session.ControlConn.Write([]byte(fmt.Sprintf("550 %s\r\n", err.Error())))
		return
	}

	session.ControlConn.Write([]byte(fmt.Sprintf("257 \"%s\" directory created.\r\n", virtualPath)))
}