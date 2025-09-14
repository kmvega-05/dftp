package entities

import (
	"strings"
)

type Command struct {
	Name string   
	Args []string 
}

// ParseCommand convierte una línea de texto en un Command estructurado.
func ParseCommand(line string) Command {
	// Eliminar saltos de línea y espacios innecesarios
	line = strings.TrimSpace(line)

	// Dividir por espacios
	parts := strings.Fields(line)

	if len(parts) == 0 {
		return Command{Name: "", Args: []string{}}
	}

	// El primer token es el nombre del comando, el resto son argumentos
	return Command{
		Name: strings.ToUpper(parts[0]),
		Args: parts[1:],
	}
}
