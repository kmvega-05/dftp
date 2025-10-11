from entities.ftp_server import FTPServer

if __name__ == "__main__":
    # Crear instancia del servidor FTP
    server = FTPServer(host='0.0.0.0', port=21)
    
    # Iniciar el servidor
    server.start_server()