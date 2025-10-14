# --------------------------------------
# INICIAR SWARM (MANAGER)
# --------------------------------------
docker swarm init --advertise-addr <ip-host>

# (Guardar el comando de join que se genera)

# --------------------------------------
# UNIRSE AL SWARM (WORKER)
# --------------------------------------
docker swarm join --token x-x-x-x ip:port

# --------------------------------------
# CREAR RED (MANAGER)
# --------------------------------------
docker network create --driver overlay --attachable ftp_net

# --------------------------------------
# CREAR VOLUMEN(MANAGER)
# --------------------------------------
docker volume create ftp_volume

# --------------------------------------
# LEVANTAR SERVICIO FTP-SERVER (MANAGER)
# --------------------------------------
docker service create \
  --name ftp_server \
  --network ftp_net \
  --publish 21:21 \
  --publish 20:20 \
  --publish 50000-50010:50000-50010 \
  --mount type=volume,source=ftp_volume,destination=/tmp/ftp_root \
  dftp-server:latest

# --------------------------------------
# CHEQUEAR SERVICIO (MANAGER)
# --------------------------------------
docker service ls
docker service ps ftp_server

# --------------------------------------
# CONSTRUIR IMAGEN CLIENTE (WORKER)
# --------------------------------------
# En el WORKER construir la imagen:
docker build -t dftp-client:latest ~/MyProyects/dftp/client

# --------------------------------------
# LEVANTAR SERVICIO FTP-CLIENT (MANAGER)
# --------------------------------------
docker service create \
  --name ftp_client \
  --network ftp_net \
  --publish 8501:8501 \
  --constraint node.role==worker \
  dftp-client:latest

# --------------------------------------
# CHEQUEAR SERVICIOS (MANAGER)
# --------------------------------------
docker service ls
docker service ps ftp_client
docker service ps ftp_server

# --------------------------------------
# VER LOGS (MANAGER)
# --------------------------------------
docker service logs ftp_server
docker service logs ftp_client


# ELIMINAR SWARM

# ELIMINAR SERVICIOS(MANAGER)
docker service rm ftp-server
docker service rm ftp-client

# SALIR DEL SWARM(WORKER)
docker swarm leave

# SALIR DEL SWARM(MANAGER)
docker swarm leave --force

# VERIFICACION(MANAGER)
docker node ls



