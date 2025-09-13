FROM golang:1.21-alpine

WORKDIR /app

# Copiamos el código del cliente
COPY src/client/ ./

# Construimos la aplicación del cliente
RUN go build -o ftp-client .

# Comando para ejecutar el cliente (interactivo)
CMD ["./ftp-client"]