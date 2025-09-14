#!/bin/bash

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}=== FTP Project Deployment ===${NC}"

# Detener contenedores existentes
echo -e "${YELLOW}Deteniendo contenedores existentes...${NC}"
docker stop ftp-server ftp-client 2>/dev/null
docker rm ftp-server ftp-client 2>/dev/null

# Build del servidor
echo -e "${YELLOW}Construyendo servidor FTP...${NC}"
docker build -f docker/server/Dockerfile -t ftp-server .

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Servidor construido correctamente${NC}"
else
    echo -e "${RED}✗ Error construyendo servidor${NC}"
    exit 1
fi

# Build del cliente
echo -e "${YELLOW}Construyendo cliente FTP...${NC}"
docker build -f docker/client/Dockerfile -t ftp-client .

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Cliente construido correctamente${NC}"
else
    echo -e "${RED}✗ Error construyendo cliente${NC}"
    exit 1
fi

# Ejecutar servidor en segundo plano
echo -e "${YELLOW}Iniciando servidor FTP...${NC}"
docker run -d \
    --name ftp-server \
    -p 21:21 \
    -p 20:20 \
    -v "$(pwd)/server/configs:/configs" \
    ftp-server

echo -e "${GREEN}✓ Servidor iniciado en segundo plano${NC}"
echo -e "${YELLOW}Ver logs del servidor: docker logs ftp-server${NC}"

# Esperar un poco para que el servidor inicie
sleep 3

# Ejecutar cliente en modo interactivo
echo -e "${YELLOW}Iniciando cliente FTP (modo interactivo)...${NC}"
echo -e "${GREEN}Presiona Ctrl+C para salir del cliente${NC}"
docker run -it \
    --name ftp-client \
    --network host \
    ftp-client

echo -e "${YELLOW}=== Deployment completado ===${NC}"
echo -e "${YELLOW}Comandos útiles:${NC}"
echo -e "  Ver logs servidor: docker logs ftp-server"
echo -e "  Detener todo: docker stop ftp-server ftp-client"
echo -e "  Eliminar contenedores: docker rm ftp-server ftp-client"