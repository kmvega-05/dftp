package commandHandler

import (
    "dftp-server/entities"
)

// HandleQUIT maneja el comando QUIT, que termina la sesión.
func HandleQUIT(session *entities.Session, cmd entities.Command) {
    session.ControlConn.Write([]byte("221 Goodbye.\r\n"))
}