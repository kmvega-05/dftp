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
	if !RequireAuth(session) {
		return
	}

	var listener net.Listener
	var port int
	var err error

	// Si ya había un listener/conexión previa, cerrarla
	if session.PasvListener != nil {
		session.PasvListener.Close()
		session.PasvListener = nil
	}
	if session.DataConn != nil {
		session.DataConn.Close()
		session.DataConn = nil
	}

	// Buscar puerto disponible en rango
	for p := PasvPortMin; p <= PasvPortMax; p++ {
		listener, err = net.Listen("tcp", fmt.Sprintf(":%d", p))
		if err == nil {
			port = p
			break
		}
	}
	if err != nil {
		session.ControlConn.Write([]byte("425 Can't open data connection.\r\n"))
		return
	}

	// Guardar en sesión
	session.PasvListener = listener
	session.DataMode = entities.DataPassive

	// Obtener IP del servidor (mejor si se configura externamente)
	serverAddr := session.ControlConn.LocalAddr().(*net.TCPAddr)
	ipParts := strings.Split(serverAddr.IP.To4().String(), ".")

	// Calcular p1,p2
	p1 := port / 256
	p2 := port % 256

	// Respuesta 227
	response := fmt.Sprintf("227 Entering Passive Mode (%s,%s,%s,%s,%d,%d).\r\n",
		ipParts[0], ipParts[1], ipParts[2], ipParts[3], p1, p2)
	session.ControlConn.Write([]byte(response))

	// Print de depuración
	fmt.Println("=== PASV Debug ===")
	fmt.Println("Listener:", session.PasvListener.Addr())
	fmt.Println("DataMode:", session.DataMode)

	// Esperar conexión en goroutine
	go func() {
		conn, err := listener.Accept()
		if err != nil {
			fmt.Println("Error accepting PASV connection:", err)
			return
		}

		session.DataConn = conn

		// Una vez aceptado, cerramos el listener
		session.PasvListener.Close()
		session.PasvListener = nil
	}()
}