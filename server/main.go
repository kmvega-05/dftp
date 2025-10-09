package main

import (
	"fmt"
	"log"
	"net"

	"dftp-server/modules/connection_manager"
)

func main() {
	port := "21"

	// Abre un socket TCP en el puerto especificado
	listener, err := net.Listen("tcp", ":"+port)
	if err != nil {
		log.Fatalf("Error iniciando listener: %v", err)
	}
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
