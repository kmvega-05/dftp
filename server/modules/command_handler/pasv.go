package commandHandler

import (
	"dftp-server/entities"
	"fmt"
	"math/rand"
	"net"
	"strings"
	"time"
)

const (
	PasvPortMin = 20000
	PasvPortMax = 21000
)

// HandlePASV maneja el comando PASV, que establece la conexión pasiva del servidor.
func HandlePASV(session *entities.Session, cmd entities.Command) {
	if !RequireAuth(session) {
		return
	}

	session.ClosePassiveConnection()

	listener, port := startListener()
	if listener == nil {
		session.Reply(425, "Can't open data connection.")
		return
	}

	session.PasvListener = listener
	session.DataMode = entities.DataPassive

	ipParts, p1, p2 := getIPAndPort("127.0.0.1", port)

	response := fmt.Sprintf("Entering Passive Mode (%s,%s,%s,%s,%d,%d).",
		ipParts[0], ipParts[1], ipParts[2], ipParts[3], p1, p2)
	session.Reply(227, response)

	fmt.Println("=== PASV Debug ===")
	fmt.Println("Listener:", session.PasvListener.Addr())
	fmt.Println("DataMode:", session.DataMode)
}

// startListener intenta abrir un listener TCP en un puerto aleatorio dentro del rango
func startListener() (net.Listener, int) {
	rand.Seed(time.Now().UnixNano())
	maxAttempts := PasvPortMax - PasvPortMin + 1

	for i := 0; i < maxAttempts; i++ {
		port := rand.Intn(PasvPortMax-PasvPortMin+1) + PasvPortMin
		l, err := net.Listen("tcp", fmt.Sprintf(":%d", port))
		if err == nil {
			return l, port
		}
	}
	return nil, 0
}

// getIPAndPort descompone la IP y el puerto en los valores requeridos por FTP
func getIPAndPort(serverIP string, port int) ([]string, int, int) {
	ipParts := strings.Split(serverIP, ".")
	p1 := port / 256
	p2 := port % 256
	return ipParts, p1, p2
}
