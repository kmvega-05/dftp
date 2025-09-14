package connection_manager

import "fmt"
import "net"
import "dftp-server/modules/command_dispatcher"


// Inicia la conexión con un cliente FTP
func HandleClient(conn net.Conn) {
	defer conn.Close()

	// Enviar banner de bienvenida FTP
	conn.Write([]byte("220 Bienvenido al servidor FTP\r\n"))

	// Aquí, en el futuro, se pedirá USER y PASS según protocolo

	// Delegar al CommandDispatcher para mantener la sesión activa
	command_dispatcher.CommandDispatcher(conn)

	fmt.Println("Cliente desconectado:", conn.RemoteAddr())
}
