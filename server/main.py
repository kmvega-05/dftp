from entities.ftp_server import FTPServer

if __name__ == "__main__":
    # Crear instancia del servidor FTP
    server = FTPServer(host='localhost', port=2121)
    
    # Iniciar el servidor
    server.start_server()