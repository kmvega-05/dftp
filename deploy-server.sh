#!/bin/bash

# Colores
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

IMAGE_NAME="ftp-server"
CONTAINER_NAME="ftp-server"
VOLUME_NAME="test_fs_volume"

# Flag rebuild: pasar "true" como primer argumento para forzar rebuild
REBUILD=${1:-false}

echo -e "${YELLOW}=== Iniciando script FTP ===${NC}"

# Crear volumen persistente si no existe
docker volume inspect $VOLUME_NAME >/dev/null 2>&1 || \
    docker volume create $VOLUME_NAME

# Build de la imagen solo si no existe o si se fuerza rebuild
if [ "$REBUILD" = "true" ] || ! docker image inspect $IMAGE_NAME >/dev/null 2>&1; then
    echo -e "${YELLOW}=== Construyendo imagen ${IMAGE_NAME} ===${NC}"
    docker build -f docker/server/Dockerfile -t $IMAGE_NAME .
else
    echo -e "${GREEN}Imagen ${IMAGE_NAME} ya existe, no se construye de nuevo${NC}"
fi

# Levantar contenedor con --rm (efímero)
echo -e "${YELLOW}=== Levantando contenedor FTP ===${NC}"
docker run --rm -it \
    --name $CONTAINER_NAME \
    -p 21:21 -p 20:20 \
    -p 20000-20100:20000-20100 \
    -v "$(pwd)/server/configs:/configs" \
    -v $VOLUME_NAME:/app/test_fs \
    $IMAGE_NAME

echo -e "${GREEN}Contenedor detenido y eliminado${NC}"
