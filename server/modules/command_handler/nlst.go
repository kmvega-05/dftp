package commandHandler

import (
	"fmt"
	"dftp-server/entities"
	fsm "dftp-server/modules/file_system_manager"
)

func HandleNLST(session *entities.Session, cmd entities.Command) {
	if !RequireAuth(session) {
		return
	}

	if session.PasvListener == nil {
		session.Reply(425, "Can't open data connection.")
		return
	}

	// 1. Aceptar la conexión de datos
	fmt.Println("Aceptando conexion...")
	dataConn, err := session.PasvListener.Accept()
	if err != nil {
		session.Reply(425, "Can't open data connection.")
		session.ClosePassiveConnection()
		return
	}
	defer dataConn.Close()

	// 2. Obtener listado de archivos antes de enviar el 150
	files, err := fsm.ListDir(session.CurrentUser.Home, session.VirtualWorkingDir)
	if err != nil {
		session.Reply(550, "Failed to list directory.")
		session.ClosePassiveConnection()
		return
	}

	// 3. Enviar 150
	session.Reply(150, "Opening data connection for file list.")

	// 4. Enviar listado de archivos
	for _, name := range files {
		fmt.Fprintf(dataConn, "%s\r\n", name)
	}

	for _, name := range files {
		fmt.Println("Archivo:", name)
	}

	// 5. Cerrar listener y limpiar estado
	session.ClosePassiveConnection()

	// 6. Enviar 226
	session.Reply(226, "Transfer complete.")
}