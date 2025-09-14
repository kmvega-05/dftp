package connection_listener

import "fmt"
import "net"
import "dftp-server/modules/connection_manager"


// Start inicia el listener del servidor en el puerto indicado.
func Start(port string) error {

	// Abre un socket tcp en el puerto especificado
    listener, err := net.Listen("tcp", ":"+port)
	
    if err != nil {
		return fmt.Errorf("error iniciando listener: %w", err)
	}
    // Asegurarse de cerrar el listener al finalizar
	defer listener.Close()

	fmt.Println("Servidor escuchando en el puerto", port)

	for {
        // Espera y acepta una nueva conexión entrante
		conn, err := listener.Accept()
		
        if err != nil {
			fmt.Println("Error aceptando conexión:", err)
			continue
		}

		fmt.Println("Cliente conectado:", conn.RemoteAddr())

		// Cada cliente se atiende en su propia goroutine
		go connection_manager.HandleClient(conn)
	}
}
