#!/bin/bash

# Colores
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}=== Iniciando solo servidor FTP ===${NC}"

# Detener servidor existente
docker stop ftp-server 2>/dev/null
docker rm ftp-server 2>/dev/null

# Build y run del servidor
docker build -f docker/server/Dockerfile -t ftp-server . && \
docker run -it \
    --name ftp-server \
    -p 21:21 \
    -p 20:20 \
    -v "$(pwd)/src/server/data:/data" \
    ftp-server

echo -e "${GREEN}Servidor detenido${NC}"