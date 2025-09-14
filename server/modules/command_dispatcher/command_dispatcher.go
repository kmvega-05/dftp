package command_dispatcher

import (
	"bufio"
	"fmt"

	"dftp-server/entities"
	"dftp-server/services/auth_and_session_service"
	"dftp-server/services/directory_management_service"
)

// CommandDispatcher escucha comandos del cliente y los procesa
func CommandDispatcher(session *entities.Session) {
	reader := bufio.NewReader(session.Conn)

	for {
		line, err := reader.ReadString('\n')
		if err != nil {
			fmt.Println("Error al leer comando:", err)
			return
		}

		cmd := entities.ParseCommand(line)
		switch cmd.Name {

			// Comandos relacionados con autenticación y sesión
			case "USER", "PASS", "REIN", "ACCT":
				auth_and_session_service.HandleCommand(session, cmd)
			
			case "PWD", "CWD", "CDUP":
				directory_management_service.HandleCommand(session, cmd)

			// Cierre de conexión  
			case "QUIT":
			session.Conn.Write([]byte("221 Cerrando la conexión\r\n"))
			return

			default:
				session.Conn.Write([]byte("502 Comando no implementado\r\n"))
		}
	}
}
