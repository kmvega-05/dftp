package main

import (
	modules "dftp-client/modules"
	"flag"
	"fmt"
	"log"
)

func main() {
	addr := flag.String("addr", "127.0.0.1", "Dirección IP del servidor FTP")
	port := flag.String("port", "21", "Puerto del servidor FTP")
	user := flag.String("user", "", "Usuario a usar (opcional)")
	pass := flag.String("pass", "", "Contraseña a usar (opcional)")
	repl := flag.Bool("repl", true, "Iniciar REPL interactivo después de conectar")
	flag.Parse()

	client := modules.NewClient(*addr, *port)

	if err := client.Connect(); err != nil {
		log.Fatalf("No se pudo conectar al servidor: %v", err)
	}
	defer client.Close()
	fmt.Println("Conectado al servidor en", *addr+":"+*port)

	if *user != "" || *pass != "" {
		if err := client.Login(*user, *pass); err != nil {
			log.Fatalf("Error en login: %v", err)
		}
	}

	if *repl {
		client.StartREPL()
	}
}
