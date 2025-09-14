package main

import "log"
import "dftp-server/modules/connection_listener"

func main() {
	port := "21"

	// Inicia el listener del servidor
	if err := connection_listener.Start(port); err != nil {
		log.Fatalf("No se pudo iniciar el servidor: %v", err)
	}
}
