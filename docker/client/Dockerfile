FROM golang:1.24 

WORKDIR /app

# Copiamos el código del cliente
COPY client/ ./

# Construimos la aplicación del cliente
RUN go build -o ftp-client .

# Comando para ejecutar el cliente (interactivo)
CMD ["./ftp-client"]