package commandHandler

import (
	"dftp-server/entities"
	"fmt"
	"strconv"
	"strings"
)

// handlePORT maneja el comando PORT, que establece la conexión activa del cliente.
func HandlePORT(session *entities.Session, cmd entities.Command) {
	
	if !RequireAuth(session) {
		return
	}

	if !RequireArgs(session, cmd, 1) {
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

	arg := cmd.Args[0]

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