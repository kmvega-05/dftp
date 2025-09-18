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

	// Resolver la nueva ruta virtual usando fsm
	newVirtual := fsm.ResolveVirtualPath(session.CurrentUser.Home, session.VirtualWorkingDir, dirArg)
	newReal := fsm.VirtualToReal(session.CurrentUser.Home, newVirtual)
	
	// Verificar existencia
	if !fsm.DirExists(newReal) {
		session.ControlConn.Write([]byte("550 Directory not found.\r\n"))
		return
	}

	// Actualizar la ruta virtual en la sesión
	session.VirtualWorkingDir = newVirtual
	session.ControlConn.Write([]byte("250 Directory successfully changed.\r\n"))
}