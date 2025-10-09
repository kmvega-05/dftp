package commandHandler

import (
	"fmt"
	"dftp-server/entities"
	fsm "dftp-server/modules/file_system_manager"
)

// HandleRMD elimina un directorio vacío.
// Si se usa una ruta absoluta, se elimina desde el root del home del usuario.
// Si se usa una ruta relativa, se elimina desde el directorio virtual actual.
func HandleRMD(session *entities.Session, cmd entities.Command) {
	// Requiere autenticación
	if !RequireAuth(session) {
		return
	}

	// Verificar argumentos
	if !RequireArgs(session, cmd, 1) {
		return
	}

	dirArg := cmd.Args[0]

	// Delegar la eliminación al File System Manager
	virtualPath, err := fsm.RemoveDir(session.CurrentUser.Home, session.VirtualWorkingDir, dirArg)
	if err != nil {
		// Código FTP 550: acción no tomada
		session.Reply(550, err.Error())
		return
	}

	// Código FTP 250: acción completada
	session.Reply(250, fmt.Sprintf("Directory \"%s\" removed.", virtualPath))
}
