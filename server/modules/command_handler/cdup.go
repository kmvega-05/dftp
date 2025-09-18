package commandHandler

import (
	"dftp-server/entities"
	fsm "dftp-server/modules/file_system_manager"
)
// HandleCDUP sube un nivel en el directorio virtual
func HandleCDUP(session *entities.Session, cmd entities.Command) {
	
	if !RequireAuth(session) {
		return
	}

	// Calcular el directorio padre de forma segura
	parentVirtual := fsm.ParentDir(session.VirtualWorkingDir)

	// Actualizar ruta virtual
	session.VirtualWorkingDir = parentVirtual
	session.ControlConn.Write([]byte("200 Operation succesfully executed.\r\n"))
}