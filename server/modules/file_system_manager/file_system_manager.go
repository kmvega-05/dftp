package file_system_manager

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
)

// DirExists verifica si el path existe y es un directorio real
func DirExists(path string) bool {
	path = filepath.Clean(path) // normaliza separadores y elimina redundancias
	info, err := os.Stat(path)
	if err != nil {
		fmt.Println("DirExists error:", err)
		fmt.Println("Path usado:", path)
		return false
	}
	return info.IsDir()
}

// NormalizePath normaliza una ruta absoluta o relativa
// Elimina dobles separadores, "." y ".." donde es posible
func NormalizePath(path string) string {
	return filepath.Clean(path)
}

// JoinPath une varias partes de una ruta de manera segura
func JoinPath(elem ...string) string {
	return filepath.Join(elem...)
}

// ParentDir devuelve el directorio padre de una ruta absoluta
func ParentDir(path string) string {
	return filepath.Dir(path)
}

// IsInsideBase verifica que 'path' esté contenido dentro de 'base'
// útil para asegurar que no se salga del home del usuario
func IsInsideBase(path, base string) bool {
	absPath, _ := filepath.Abs(path)
	absBase, _ := filepath.Abs(base)
	return strings.HasPrefix(absPath, absBase)
}

func ResolveVirtualPath(home, currentVirtual, dirArg string) string {
	var newVirtual string

	if filepath.IsAbs(dirArg) {
		// Ruta absoluta → relativa al home
		newVirtual = NormalizePath(dirArg)
	} else {
		// Ruta relativa → combinar con directorio virtual actual
		newVirtual = NormalizePath(JoinPath(currentVirtual, dirArg))
	}

	// Normalizamos y aseguramos que nunca salga del home
	realPath := VirtualToReal(home, newVirtual)
	if !IsInsideBase(realPath, home) {
		return string(filepath.Separator) // "/", raíz virtual
	}

	return newVirtual
}

// VirtualToReal convierte una ruta virtual en la ruta real del sistema
// home: ruta real del home del usuario (ej: /srv/ftp/alice)
// virtualPath: ruta virtual que ve el usuario (ej: "/", "/docs")
func VirtualToReal(home, virtualPath string) string {
	cleanVirtual := filepath.Clean(virtualPath)

	if cleanVirtual == string(filepath.Separator) {
		return home
	}

	return filepath.Join(home, cleanVirtual)
}
