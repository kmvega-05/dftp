package modules

import (
	"bufio"
	"fmt"
	"os"
	"strings"
)

func (c *Client) StartREPL() {
	scanner := bufio.NewScanner(os.Stdin)

	for {
		fmt.Print("ftp> ")
		if !scanner.Scan() {
			break
		}
		cmd := scanner.Text()

		if strings.ToUpper(cmd) == "QUIT" {
			resp, err := c.SendCommand("QUIT")
			if err != nil {
				fmt.Println("Error al enviar QUIT:", err)
				continue
			}
			fmt.Println("Servidor:", resp)
			break
		}

		// Enviar lo que sea que el usuario escribió
		resp, err := c.SendCommand(cmd)
		if err != nil {
			fmt.Println("Error al enviar comando:", err)
			continue
		}
		fmt.Println("Servidor:", resp)
	}
}
