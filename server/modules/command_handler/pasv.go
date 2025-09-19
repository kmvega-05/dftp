package commandHandler

import (
	"dftp-server/entities"
	"fmt"
	"net"
	"strings"
)

const (
	PasvPortMin = 20000
	PasvPortMax = 21000
)

// handlePASV maneja el comando PASV, que establece la conexión pasiva del servidor.
func HandlePASV(session *entities.Session, cmd entities.Command) {

	var listener net.Listener
	var port int

	if !RequireAuth(session) {
		return
	}

	// Cerrar cualquier conexión y listener pasivos previos
	session.ClosePassiveConnection()

	// Crea un listener para escuchar conexiones en un puerto
	listener, port = StartListener()

	if listener == nil {
		session.ControlConn.Write([]byte("425 Can't open data connection.\r\n"))
		return
	}

	// Guardar en sesión
	session.PasvListener = listener
	session.DataMode = entities.DataPassive

	ipParts, p1, p2 := Get_ip_and_port("127.0.0.1", port)	

	// Enviar respuesta al cliente
	response := fmt.Sprintf("227 Entering Passive Mode (%s,%s,%s,%s,%d,%d).\r\n", ipParts[0], ipParts[1], ipParts[2], ipParts[3], p1, p2)
	session.ControlConn.Write([]byte(response))

	// Debug
	fmt.Println("=== PASV Debug ===")
	fmt.Println("Listener:", session.PasvListener.Addr())
	fmt.Println("DataMode:", session.DataMode)
}

func StartListener() (net.Listener, int) {
	for p := PasvPortMin; p <= PasvPortMax; p++ {
		
		l, err := net.Listen("tcp", fmt.Sprintf(":%d", p))
		
		if err == nil {
			return l, p
		}
	}
	return nil, 0
}

func Get_ip_and_port(serverIP string, port int) ([]string,int,int) {

	ipParts := strings.Split(serverIP, ".")

	p1 := port / 256
	p2 := port % 256

	return ipParts, p1, p2
} 