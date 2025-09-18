package entities

import "net"

type DataMode int

const (
	DataNone DataMode = iota // No hay conexión activa
	DataActive               // Modo activo (PORT)
	DataPassive              // Modo pasivo (PASV)
)

// User representa un usuario cargado desde user_management_module
type User struct {
	Username string // Nombre de usuario
	Password string // Contraseña del usuario
	Home     string // Directorio raíz real del usuario (ej: /srv/ftp/alice)
}

// Session mantiene el estado de una conexión FTP con un cliente
type Session struct {
	ControlConn       net.Conn // Conexión de red con el cliente 
	CurrentUser       *User    // Usuario autenticado actualmente
	IsAuthenticated   bool     // Indica si el usuario ha sido autenticado
	VirtualWorkingDir string   // Directorio actual visible por el cliente (ej: /, /docs)
	PendingUser       string   // Usuario enviado por USER, en espera de PASS   
	
	// Conexión de datos
	DataConn       net.Conn   	// conexión de datos (socket ya aceptado/conectado)
	PasvListener   net.Listener // solo en modo PASV
	ActiveHost 	   string 		// dirección IP enviada por el cliente
	ActivePort 	   int   		// puerto calculado de p1*256 + p2
	DataMode       DataMode     // estado actual
}

// NewSession crea una nueva sesión FTP para un cliente
func NewSession(conn net.Conn) *Session {
	return &Session{
		ControlConn:      conn,
		DataConn:         nil,
		PasvListener:     nil,
		ActiveHost:       "",
		ActivePort:       0,
		DataMode:         DataNone,
		CurrentUser:      nil,
		IsAuthenticated:  false,
		VirtualWorkingDir: "/",
		PendingUser:      "",
	}
}

// RestartSession reinicia todos los campos de la sesión FTP a su estado inicial.
func (s *Session) RestartSession() {

	// Cerrar conexiones de datos si están activas
	if s.DataConn != nil {
		s.DataConn.Close()
		s.DataConn = nil
	}
	if s.PasvListener != nil {
		s.PasvListener.Close()
		s.PasvListener = nil
	}

	// Resetear estado de autenticación y directorio
	s.CurrentUser = nil
	s.IsAuthenticated = false
	s.VirtualWorkingDir = "/"
	s.PendingUser = ""

	// Resetear estado de conexión de datos
	s.ActiveHost = ""
	s.ActivePort = 0
	s.DataMode = DataNone
}
