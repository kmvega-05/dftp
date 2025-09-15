package file_transfer_service

import (
	"fmt"
	"net"
	"strings"
	"dftp-server/entities"
)

// Rango de puertos para modo PASV (configurable)
const (
	PasvPortMin = 50000
	PasvPortMax = 51000
)

// HandleCommand procesa los comandos relacionados con la transferencia de archivos
func HandleCommand(session *entities.Session, cmd entities.Command) {
	switch strings.ToUpper(cmd.Name) {
	case "PASV":
		handlePASV(session)
	case "PORT":
		handlePORT(session, cmd.Args)
	case "LIST":
		handleLIST(session, cmd.Args)
	case "RETR":
		handleRETR(session, cmd.Args)
	case "STOR":
		handleSTOR(session, cmd.Args)
	default:
		session.Conn.Write([]byte("502 Comando no implementado\r\n"))
	}
}

// handlePASV inicia un listener TCP para transferencia de datos pasiva
func handlePASV(session *entities.Session) {
	if !session.IsAuthenticated {
		session.Conn.Write([]byte("530 Not logged in.\r\n"))
		return
	}

	var listener net.Listener
	var port int
	var err error

	// Elegir un puerto libre dentro del rango
	
	for p := PasvPortMin; p <= PasvPortMax; p++ {
		listener, err = net.Listen("tcp", fmt.Sprintf(":%d", p))
		if err == nil {
			port = p
			break
		}
	}
	if err != nil {
		session.Conn.Write([]byte("425 Can't open data connection.\r\n"))
		return
	}

	// Obtener IP del servidor
	serverAddr := session.Conn.LocalAddr().(*net.TCPAddr)
	ipParts := strings.Split(serverAddr.IP.String(), ".")

	// Calcular p1 y p2 para el puerto
	p1 := port / 256
	p2 := port % 256

	// Construir respuesta
	response := fmt.Sprintf("227 Entering Passive Mode (%s,%s,%s,%s,%d,%d).\r\n",
		ipParts[0], ipParts[1], ipParts[2], ipParts[3], p1, p2)
	session.Conn.Write([]byte(response))

	// Esperar que el cliente se conecte (goroutine)
	go func() {
		conn, err := listener.Accept()
		if err != nil {
			fmt.Println("Error accepting PASV connection:", err)
			return
		}

		session.DataConn = conn
		
		// Cerrar listener, ya no se necesita
		listener.Close()
	}()
}

func handlePORT(session *entities.Session, args []string) {
	// 1. Validar autenticación
	// 2. Parsear IP y puerto desde args
	// 3. Guardar en session.DataIP y session.DataPort
	// 4. Preparar session.DataConn para la conexión activa
}

func handleLIST(session *entities.Session, args []string) {
	// 1. Validar autenticación
	// 2. Verificar que haya conexión de datos (PASV o PORT)
	// 3. Obtener ruta virtual a listar (usar fsm)
	// 4. Enviar listado de directorio por session.DataConn
}

func handleRETR(session *entities.Session, args []string) {
	// 1. Validar autenticación
	// 2. Verificar que haya conexión de datos
	// 3. Abrir archivo y enviarlo por session.DataConn
}

func handleSTOR(session *entities.Session, args []string) {
	// 1. Validar autenticación
	// 2. Verificar que haya conexión de datos
	// 3. Recibir archivo desde session.DataConn y guardarlo
}
