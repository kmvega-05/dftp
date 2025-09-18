package connection_manager

import (
	"fmt"
	"net"
	"dftp-server/entities"
	cmd_handler "dftp-server/modules/command_handler" 
)

// Inicia la conexión con un cliente FTP
func HandleClient(conn net.Conn) {
	defer conn.Close()

	// Crear nueva sesión default sin autenticar
	session := entities.NewSession(conn)

	// Enviar banner de bienvenida FTP
	session.ControlConn.Write([]byte("220 Bienvenido al servidor FTP\r\n"))

	// Delegar al CommandHandler
	cmd_handler.DispatchCommand(session)

	fmt.Println("Cliente desconectado:", conn.RemoteAddr())
}
