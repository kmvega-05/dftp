package commandHandler

import (
	"fmt"
	"dftp-server/entities"
	fsm "dftp-server/modules/file_system_manager"
)

// HandleMKD crea un nuevo directorio.
// Si se usa una ruta absoluta, se crea desde el root del home del usuario.
// Si se usa una ruta relativa, se crea desde el directorio virtual actual.
func HandleMKD(session *entities.Session, cmd entities.Command) {
	// Requiere que el usuario esté autenticado
	if !RequireAuth(session) {
		return
	}

	// Verificar que se haya pasado un argumento
	if !RequireArgs(session, cmd, 1) {
		return
	}

	dirArg := cmd.Args[0]

	// Delegar la creación del directorio al File System Manager
	virtualPath, err := fsm.CreateDir(session.CurrentUser.Home, session.VirtualWorkingDir, dirArg)
	if err != nil {
		// Código FTP 550: acción no tomada
		session.Reply(550, err.Error())
		return
	}

	// Código FTP 257: directorio creado
	session.Reply(257, fmt.Sprintf("\"%s\" directory created.", virtualPath))
}