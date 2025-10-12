# Iniciar swarm(solo la primera vez)
docker swarm init

# Construir imagenes
docker build -t dftp-client:latest ./client
docker build -t dftp-server:latest ./server

# Crear red overlay
docker network create -d overlay ftp_net

# Levantar el stack 
docker stack deploy -c docker-stack.yml dftp_stack

# Comprobar que todo inicio correctamente

## Servicios y Réplicas (debe salir 1/1 para cliente y servidor)
docker stack services dftp_stack

## Comprobar logs de cada servicio
docker service logs -f --raw dftp_stack_ftp_server
docker service logs -f --raw dftp_stack_ftp_client

# Probar
- Abrir navegador en http://127.0.0.1:8501

- Conectar a ftp_server, puerto 21

- Autenticarse con USER admin, PASS admin123

- Enviar comandos para probar
