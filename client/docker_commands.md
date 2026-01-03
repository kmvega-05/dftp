# Construir la imagen
docker build -t dftp-client .

# Chequear que se construyo correctamente
docker images

# Ejecutar contenedor
docker run -d --rm --name dftp-client-app -p 8501:8501 dftp-client

Abrir navegador en localhost:8501

# Si se necesita reconstruir la imagen
docker stop dftp-client-app

Construir la imagen y ejecutar contenedor de nuevo