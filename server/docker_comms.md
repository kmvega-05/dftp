# Construir Imagen
docker build -t servidor-ftp:latest .

# Chequear que se construyo correctamente
docker images

# Levantar contenedor
docker run -it --rm --name ftp-server -p 21:21 -p 20:20 -p 50000-50010:50000-50010 servidor-ftp:latest

# Si se necesita reconstruir la imagen
docker stop ftp-server

construir la imagen y levantar el container de nuevo

