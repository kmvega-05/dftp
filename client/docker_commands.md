# dFTP Client - Docker Commands

## Quick Start (Recomendado)

Usar el script `client.sh` para gestionar imagen y contenedor:

```bash
# Primera vez: construir imagen
./client.sh build

# Ejecutar con volumen montado (hot reload - sin rebuild)
./client.sh run

# En otra terminal: detener el contenedor
./client.sh stop

# Limpiar todo (imagen + contenedor)
./client.sh clean

# Reconstruir y ejecutar de nuevo
./client.sh rebuild
```

## Ventajas del script

- **Sin rebuild necesario**: El código está montado como volumen
- **Hot reload**: Los cambios se ven automáticamente
- **Gestión simple**: Comandos claros para build/run/stop
- **Red Docker**: Conecta automáticamente a la red `dftp_net`

## Acceder a la aplicación

Después de ejecutar `./client.sh run`:
- UI: http://localhost:8501
- Ver logs en la terminal donde corre el contenedor

## Comandos manuales (si necesitas)

```bash
# Construir imagen
docker build -t dftp-client:latest .

# Ejecutar con volumen (sin rebuild cada vez)
docker run --rm --name dftp-client --net dftp_net -p 8501:8501 -v $(pwd):/home/app dftp-client:latest

# Detener
docker stop dftp-client

# Ver logs
docker logs dftp-client
```

## Notas

- El volumen `-v $(pwd):/home/app` permite hot reload sin reconstruir
- La red `dftp_net` conecta con otros nodos del servidor
- Los logs se ven con nivel DEBUG gracias a los cambios recientes
