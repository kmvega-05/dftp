package commandHandler

import (
	"dftp-server/entities"
	fsm "dftp-server/modules/file_system_manager"
	"fmt"
)

// HandleDELE maneja el comando DELE, que elimina un archivo.
func HandleDELE(session *entities.Session, cmd entities.Command) {
	// Requiere que el usuario esté autenticado
	if !RequireAuth(session) {
		return
	}

	// Verificar que se haya pasado un argumento
	if !RequireArgs(session, cmd, 1) {
		return
	}

	fileArg := cmd.Args[0]

	// Intentar eliminar el archivo usando el File System Manager
	err := fsm.RemoveFile(session.CurrentUser.Home, session.VirtualWorkingDir, fileArg)
	if err != nil {
		// Responder con código FTP 550 si hubo error
		session.Reply(550, fmt.Sprintf("%s", err.Error()))
		return
	}

	// Confirmación exitosa con código FTP 250
	session.Reply(250, fmt.Sprintf("\"%s\" deleted successfully.", fileArg))
}