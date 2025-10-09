package commandHandler

import (
	"bufio"
	"dftp-server/entities"
	"fmt"
)

type HandlerFunc func(*entities.Session, entities.Command)

var commandMap = map[string]HandlerFunc{
	"USER": HandleUSER,
	"PASS": HandlePASS,
	"QUIT": HandleQUIT,
	"REIN": HandleREIN,
	"PWD":  HandlePWD,
	"CWD":  HandleCWD,
	"CDUP": HandleCDUP,
	"MKD":  HandleMKD,
	"RMD":  HandleRMD,
	"PASV": HandlePASV,
	"NLST": HandleNLST,
	"LIST": HandleLIST,
	"TYPE": HandleTYPE,
	"NOOP": HandleNOOP,
	"HELP": HandleHELP,
	"SYST": HandleSYST,
	"DELE": HandleDELE,
}

func DispatchCommand(session *entities.Session) {
	reader := bufio.NewReader(session.ControlConn)

	for {
		// Leer una línea del cliente
		line, err := reader.ReadString('\n')

		// Manejar errores de lectura
		if err != nil {
			fmt.Println("Error al leer comando:", err)
			return
		}

		// Parsear el comando
		cmd := entities.ParseCommand(line)

		fmt.Printf("Comando recibido: %s %v\n", cmd.Name, cmd.Args)

		// Ejecuta el handler correspondiente, en caso de no existir responde con 502 Comando no implementado
		if handler, ok := commandMap[cmd.Name]; ok {
			handler(session, cmd)
			// Si el comando es QUIT, salir del loop y terminar la sesión
			if cmd.Name == "QUIT" {
				return
			}
		} else {
			session.ControlConn.Write([]byte("502 Comando no implementado\r\n"))
		}
	}
}

func RequireArgs(session *entities.Session, cmd entities.Command, expected int) bool {
	if len(cmd.Args) < expected {
		session.ControlConn.Write([]byte(fmt.Sprintf("501 Syntax error in parameters or arguments: [%s expecting %d argument(s)]\r\n", cmd.Name, expected)))
		return false
	}
	return true
}

func RequireAuth(session *entities.Session) bool {
	if !session.IsAuthenticated {
		session.ControlConn.Write([]byte("530 Not logged in\r\n"))
		return false
	}
	return true
}
