package commandHandler

import "dftp-server/entities"

// HandleQUIT maneja el comando QUIT, que termina la sesión.
func HandleQUIT(session *entities.Session, cmd entities.Command) {
    session.Reply(221, "Goodbye.")
}