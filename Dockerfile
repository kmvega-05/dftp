FROM python:3.11-slim

WORKDIR /app

# Evita buffers en salida para ver logs en tiempo real
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    DFTP_SUBNET=172.25.0.0/24

# Copia todo el proyecto al contenedor
COPY . /app

# Instala dependencias si existe requirements.txt
RUN set -e \
    && if [ -f /app/requirements.txt ]; then pip install --no-cache-dir -r /app/requirements.txt; fi

# Puertos comunes usados por los nodos (no obligatorio)
EXPOSE 9000 20 21 2121

# Por defecto ejecutamos python
ENTRYPOINT ["python3"]

# Script por defecto
CMD ["tests/run_discovery.py"]
