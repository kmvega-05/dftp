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
# CREAR VOLUMEN (MANAGER)
# --------------------------------------
docker volume create ftp_volume

# --------------------------------------
# CONSTRUIR IMAGENES EN AMBOS NODOS
# --------------------------------------

# En MANAGER construir imagen del servidor:
docker build -t dftp-server:latest ~/MyProyects/dftp/server

# En WORKER construir imagen del cliente:
docker build -t dftp-client:latest ~/MyProyects/dftp/client

# --------------------------------------
# LEVANTAR STACK COMPLETO (MANAGER)
# --------------------------------------
docker stack deploy -c docker-stack.yml ftp_stack

# --------------------------------------
# CHEQUEAR SERVICIOS (MANAGER)
# --------------------------------------
docker stack services ftp_stack
docker service ls
docker service ps ftp_stack_ftp_server
docker service ps ftp_stack_ftp_client

# --------------------------------------
# VER LOGS (MANAGER)
# --------------------------------------
docker service logs ftp_stack_ftp_server
docker service logs ftp_stack_ftp_client

# --------------------------------------
# VER ESTADO DEL STACK (MANAGER)
# --------------------------------------
docker stack ps ftp_stack