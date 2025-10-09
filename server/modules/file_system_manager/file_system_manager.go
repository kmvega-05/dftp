package file_system_manager

import (
	"errors"
	"os"
	"path/filepath"
	"strings"
)

// DirExists verifica si el path existe y es un directorio real
func DirExists(path string) bool {
	path = filepath.Clean(path) // normaliza separadores y elimina redundancias
	info, err := os.Stat(path)
	if err != nil {
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

// ResolveVirtualPath resuelve una ruta virtual basada en el home del usuario y el directorio virtual actual
// Crea la ruta virtual tanto para rutas absolutas como relativas
// home: ruta real del home del usuario (ej: /srv/ftp/alice)
// currentVirtual: ruta virtual actual (ej: "/", "/docs")
// dirArg: argumento de directorio proporcionado por el usuario (ej: "docs", "/docs", "../docs")
func ResolveVirtualPath(home, currentVirtual, dirArg string) string {
	var newVirtual string

	if filepath.IsAbs(dirArg) {
		// Ruta absoluta → relativa al home
		newVirtual = NormalizePath(dirArg)
	} else {
		// Ruta relativa → combinar con directorio virtual actual
		newVirtual = NormalizePath(JoinPath(currentVirtual, dirArg))
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

// CreateDir intenta crear un directorio virtual dentro del home del usuario.
// Retorna la ruta virtual normalizada creada, o un error si falla.
func CreateDir(home, currentVirtual, dirArg string) (string, error) {
	if dirArg == "" {
		return "", errors.New("Missing directory name")
	}

	// 1. Resolver ruta virtual
	virtualPath := ResolveVirtualPath(home, currentVirtual, dirArg)
	realPath := VirtualToReal(home, virtualPath)

	// 2. Seguridad: validar que esté dentro del home
	if !IsInsideBase(realPath, home) {
		return "", errors.New("Access denied")
	}

	// 3. Verificar si ya existe
	if DirExists(realPath) {
		return "", errors.New("Directory already exists")
	}

	// 4. Intentar crear
	err := os.Mkdir(realPath, 0755)
	if err != nil {
		return "", err
	}

	return virtualPath, nil
}

// RemoveDir intenta eliminar un directorio virtual dentro del home del usuario.
// Retorna la ruta virtual normalizada eliminada, o un error si falla.
func RemoveDir(home, currentVirtual, dirArg string) (string, error) {
	if dirArg == "" {
		return "", errors.New("Missing directory name")
	}

	// 1. Resolver ruta virtual
	virtualPath := ResolveVirtualPath(home, currentVirtual, dirArg)
	realPath := VirtualToReal(home, virtualPath)

	// 2. Seguridad: validar que esté dentro del home
	if !IsInsideBase(realPath, home) {
		return "", errors.New("Access denied")
	}

	// 3. Verificar existencia y tipo
	info, err := os.Stat(realPath)
	if err != nil {
		if os.IsNotExist(err) {
			return "", errors.New("No such file or directory")
		}
		return "", err
	}
	if !info.IsDir() {
		return "", errors.New("Not a directory")
	}

	// 4. Comprobar si está vacío
	entries, err := os.ReadDir(realPath)
	if err != nil {
		return "", err
	}
	if len(entries) > 0 {
		return "", errors.New("Directory not empty")
	}

	// 5. Intentar borrar
	err = os.Remove(realPath)
	if err != nil {
		return "", err
	}

	return virtualPath, nil
}

// RemoveFile elimina un archivo dentro del home del usuario.
// Retorna un error si el archivo no existe, no es un archivo regular o está fuera del home.
func RemoveFile(home, currentVirtual, fileArg string) error {
	if fileArg == "" {
		return errors.New("Missing file name")
	}

	// 1. Resolver ruta virtual y real
	virtualPath := ResolveVirtualPath(home, currentVirtual, fileArg)
	realPath := VirtualToReal(home, virtualPath)

	// 2. Seguridad: asegurar que esté dentro del home
	if !IsInsideBase(realPath, home) {
		return errors.New("Access denied")
	}

	// 3. Verificar existencia
	info, err := os.Stat(realPath)
	if err != nil {
		if os.IsNotExist(err) {
			return errors.New("No such file or directory")
		}
		return err
	}

	// 4. Validar que sea un archivo regular (no directorio, no dispositivo)
	if info.IsDir() {
		return errors.New("Not a regular file")
	}

	// 5. Eliminar el archivo
	err = os.Remove(realPath)
	if err != nil {
		return err
	}

	return nil
}

// ListDir devuelve una lista de nombres de archivos y directorios dentro de un directorio virtual.
// Retorna []string con los nombres, o error si falla.
func ListDir(home, currentVirtual string) ([]string, error) {
	// Resolver ruta real
	realPath := VirtualToReal(home, currentVirtual)

	// Seguridad: validar que esté dentro del home
	if !IsInsideBase(realPath, home) {
		return nil, errors.New("Access denied")
	}

	// Leer contenido
	entries, err := os.ReadDir(realPath)
	if err != nil {
		return nil, err
	}

	names := make([]string, 0, len(entries))
	for _, entry := range entries {
		names = append(names, entry.Name())
	}

	return names, nil
}

func ReadFileContent(home, filePath string) (string, os.FileInfo, error) {
	realPath := VirtualToReal(home, filePath)
	if !IsInsideBase(realPath, home) {
		return "", nil, errors.New("Access denied")
	}
	content, err := os.ReadFile(realPath)
	if err != nil {
		return "", nil, err
	}
	var fileInfo, _ = os.Stat(realPath)

	return string(content), fileInfo, nil
}
