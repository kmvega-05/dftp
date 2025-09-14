package command_dispatcher

import "bufio"
import "fmt"
import "net"
import "dftp-server/entities"


// CommandDispatcher lee comandos del cliente y los despacha a los servicios adecuados.
func CommandDispatcher(conn net.Conn) {
	// Lector para obtener líneas enviadas por el cliente
	reader := bufio.NewReader(conn)

	for {
		// Leer línea enviada por el cliente
		line, err := reader.ReadString('\n')
		
		if err != nil {
			fmt.Println("Error leyendo del cliente:", err)
			return
		}

		// Convertir el mensaje en un Command
		cmd := entities.ParseCommand(line)
		
		// Ignorar líneas vacías
		if cmd.Name == "" {
			continue
		}
		
		// Despachar según el comando
		switch cmd.Name {
			case "QUIT":
				handleQUIT(conn)
				return
			
			default:
				handleUNKNOWN(conn, cmd.Name)
		}
	}
}

// handleQUIT maneja la finalización de la sesión
func handleQUIT(conn net.Conn) {
	conn.Write([]byte("221 Goodbye.\r\n"))
}

// handleUNKNOWN responde a comandos no implementados
func handleUNKNOWN(conn net.Conn, name string) {
	conn.Write([]byte(fmt.Sprintf("502 Command not implemented: %s\r\n", name)))
}
