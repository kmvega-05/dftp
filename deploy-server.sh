#!/bin/bash

# Colores
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}=== Iniciando solo servidor FTP ===${NC}"

# Detener servidor existente
docker stop ftp-server 2>/dev/null
docker rm ftp-server 2>/dev/null

# Crear volumen persistente para test_fs si no existe
docker volume inspect test_fs_volume >/dev/null 2>&1 || \
    docker volume create test_fs_volume

# Build de la imagen
docker build -f docker/server/Dockerfile -t ftp-server .

# Run del servidor con volumen persistente
docker run -it \
    --name ftp-server \
    -p 21:21 \
    -p 20:20 \
    -v "$(pwd)/server/configs:/configs" \
    -v test_fs_volume:/app/test_fs \
    ftp-server

echo -e "${GREEN}Servidor detenido${NC}"
