package commandHandler

import (
	"dftp-server/entities"
	fsm "dftp-server/modules/file_system_manager"
)

// HandleCWD maneja el comando CWD, que cambia el directorio de trabajo actual.
func HandleCWD(session *entities.Session, cmd entities.Command) {

	if !RequireAuth(session) {
		return
	}

	if !RequireArgs(session, cmd, 1) {
		return
	}

	dirArg := cmd.Args[0]

	// Resolver la nueva ruta virtual con respecto al directorio actual
	newVirtual := fsm.ResolveVirtualPath(session.CurrentUser.Home, session.VirtualWorkingDir, dirArg)
	newReal := fsm.VirtualToReal(session.CurrentUser.Home, newVirtual)

	// Verificar que el directorio exista físicamente
	if !fsm.DirExists(newReal) {
		session.Reply(550, "Directory not found.")
		return
	}

	// Actualizar el directorio de trabajo virtual
	session.VirtualWorkingDir = newVirtual
	session.Reply(250, "Directory successfully changed.")
}
