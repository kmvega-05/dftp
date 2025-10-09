package commandHandler

import (
	"fmt"
	"dftp-server/entities"
)

// HandleTYPE maneja el comando TYPE, que establece el tipo de transferencia (I=binario, A=ASCII)
func HandleTYPE(sess *entities.Session, cmd entities.Command) {
	// Requiere autenticación
	if !sess.IsAuthenticated {
		sess.Reply(530, "Please login with USER and PASS.")
		return
	}

	// Verificar argumentos
	if !RequireArgs(sess, cmd, 1) {
		return
	}

	// Tomamos solo el primer argumento (ej: "I" o "A")
	mode := cmd.Args[0]

	// Responder con código 200, aunque no se aplique efecto real
	sess.Reply(200, fmt.Sprintf("Type set to %s (stub, no real effect).", mode))
}
