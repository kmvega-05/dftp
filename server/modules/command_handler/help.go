package commandHandler

import (
	"dftp-server/entities"
	"encoding/json"
	"os"
)

type CommandForHelp struct {
	Name string `json:"Name"`
	Text string `json:"Text"`
}

type CommandsList struct {
	Commands []CommandForHelp `json:"commands"`
}

func HandleHELP(session *entities.Session, cmd entities.Command) {
	if !RequireAuth(session) {
		return
	}
	file, _ := os.ReadFile("commands.json") //TODO: Probablemente halla que ajustar el path aqui, pruebalo y cambialo por el correcto. Si da mucho palo mete aqui el archivo commands.json
	var commands CommandsList
	json.Unmarshal(file, &commands)
	ans := "214-The following commands are recognized:\r\n"
	if len(cmd.Args) == 0 {
		for _, command := range commands.Commands {
			ans += " " + command.Name + "\r\n"
		}
		ans += "214 Help OK.\r\n"
		session.ControlConn.Write([]byte(ans))
	} else if len(cmd.Args) == 1 {
		found := false
		for _, command := range commands.Commands {
			if command.Name == cmd.Args[0] {
				ans = "214 " + command.Text + "\r\n"
				session.ControlConn.Write([]byte(ans))
				found = true
			}
		}
		if !found {
			ans = "504 Command not implemented for that parameter.\r\n"
			session.ControlConn.Write([]byte(ans))
		}
	} else {
		session.ControlConn.Write([]byte("550 Invalid Command Format\r\n"))
	}
}
