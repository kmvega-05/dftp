package commandHandler

import (
	"fmt"

	"dftp-server/entities"
)

func HandleTYPE(sess *entities.Session, cmd entities.Command) {
	if !sess.IsAuthenticated {
		sess.ControlConn.Write([]byte("530 Please login with USER and PASS.\r\n"))
		return
	}

	if !RequireArgs(sess, cmd, 1) {
		return
	}

	// Tomamos solo el primer argumento (ej: "I" o "A")
	mode := cmd.Args[0]

	// Responder sin aplicar cambios reales
	resp := fmt.Sprintf("200 Type set to %s (stub, no real effect).\r\n", mode)
	sess.ControlConn.Write([]byte(resp))
}