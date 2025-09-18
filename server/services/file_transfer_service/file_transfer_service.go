package file_transfer_service

import (
	"fmt"
	"net"
	"strings"
	"strconv"
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
		session.ControlConn.Write([]byte("502 Comando no implementado\r\n"))
	}
}

func handlePASV(session *entities.Session) {
	if !session.IsAuthenticated {
		session.ControlConn.Write([]byte("530 Not logged in.\r\n"))
		return
	}

	// Si ya había un listener/conexión previa, cerrarla
	if session.PasvListener != nil {
		session.PasvListener.Close()
		session.PasvListener = nil
	}
	if session.DataConn != nil {
		session.DataConn.Close()
		session.DataConn = nil
	}

	var listener net.Listener
	var port int
	var err error

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


func handlePORT(session *entities.Session, args []string) {
	
	if len(args) == 0 {
    session.ControlConn.Write([]byte("501 Missing argument.\r\n"))
    return
	}
	
	if !session.IsAuthenticated {
		session.ControlConn.Write([]byte("530 Not logged in.\r\n"))
		return
	}

	// Cerrar cualquier conexión previa
	if session.DataConn != nil {
		session.DataConn.Close()
		session.DataConn = nil
	}
	if session.PasvListener != nil {
		session.PasvListener.Close()
		session.PasvListener = nil
	}

	arg := args[0]

	parts := strings.Split(arg, ",")
	if len(parts) != 6 {
		session.ControlConn.Write([]byte("501 Syntax error in parameters.\r\n"))
		return
	}

	// Construir dirección IP
	ip := fmt.Sprintf("%s.%s.%s.%s", parts[0], parts[1], parts[2], parts[3])

	// Calcular puerto
	p1, err1 := strconv.Atoi(parts[4])
	p2, err2 := strconv.Atoi(parts[5])
	if err1 != nil || err2 != nil {
		session.ControlConn.Write([]byte("501 Invalid port numbers.\r\n"))
		return
	}
	port := p1*256 + p2

	// Guardar en sesión
	session.ActiveHost = ip
	session.ActivePort = port
	session.DataMode = entities.DataActive

	session.ControlConn.Write([]byte("200 PORT command successful.\r\n"))

	// Print de depuración
	fmt.Println("=== PORT Debug ===")
	fmt.Println("ActiveHost:", session.ActiveHost)
	fmt.Println("ActivePort:", session.ActivePort)
	fmt.Println("DataMode:", session.DataMode)
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
