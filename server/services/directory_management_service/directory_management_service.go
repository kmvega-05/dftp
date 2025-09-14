package directory_management_service

import (
	"fmt"
	"dftp-server/entities"
	fsm "dftp-server/modules/file_system_manager"
)

func HandleCommand(session *entities.Session, cmd entities.Command) {
	switch cmd.Name {
	case "PWD":
		HandlePWD(session, cmd.Args)
	case "CWD":
		HandleCWD(session, cmd.Args)
	case "CDUP":
		HandleCDUP(session, cmd.Args)
	default:
		session.Conn.Write([]byte("502 Comando no implementado\r\n"))
	}
}

// HandlePWD devuelve la ruta virtual actual
func HandlePWD(session *entities.Session, args []string) {
	if !session.IsAuthenticated {
		session.Conn.Write([]byte("530 Not logged in.\r\n"))
		return
	}

	session.Conn.Write([]byte("257 \"" + session.VirtualWorkingDir + "\" is current directory.\r\n"))
}

// HandleCWD cambia el directorio virtual actual
func HandleCWD(session *entities.Session, args []string) {
	if !session.IsAuthenticated {
		session.Conn.Write([]byte("530 Not logged in.\r\n"))
		return
	}

	if len(args) < 1 {
		session.Conn.Write([]byte("550 Missing directory parameter.\r\n"))
		return
	}

	dirArg := args[0]

	// Resolver la nueva ruta virtual usando fsm
	newVirtual := fsm.ResolveVirtualPath(session.CurrentUser.Home, session.VirtualWorkingDir, dirArg)
	newReal := fsm.VirtualToReal(session.CurrentUser.Home, newVirtual)
	
	fmt.Println("Ruta real buscada:", newReal)

	// Verificar que la nueva ruta real esté dentro del home del usuario
	if !fsm.IsInsideBase(newReal, session.CurrentUser.Home) {
        session.Conn.Write([]byte("550 Permission denied.\r\n"))
        return
    }

	// Verificar existencia
	if !fsm.DirExists(newReal) {
		session.Conn.Write([]byte("550 Directory not found.\r\n"))
		return
	}

	// Actualizar la ruta virtual en la sesión
	session.VirtualWorkingDir = newVirtual
	session.Conn.Write([]byte("250 Directory successfully changed.\r\n"))
}

// HandleCDUP sube un nivel en el directorio virtual
func HandleCDUP(session *entities.Session, args []string) {
	if !session.IsAuthenticated {
		session.Conn.Write([]byte("530 Not logged in.\r\n"))
		return
	}

	// Calcular el directorio padre de forma segura
	parentVirtual := fsm.ParentDir(session.VirtualWorkingDir)
	parentReal := fsm.VirtualToReal(session.CurrentUser.Home, parentVirtual)

	// Asegurar que no se salga del home
	if !fsm.IsInsideBase(parentReal, session.CurrentUser.Home) {
		session.VirtualWorkingDir = "/"
		session.Conn.Write([]byte("200 Directory changed to root.\r\n"))
		return
	}

	// Actualizar ruta virtual
	session.VirtualWorkingDir = parentVirtual
	session.Conn.Write([]byte("200 Operation succesfully executed.\r\n"))
}
