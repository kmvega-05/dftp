FROM python:3.9-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /home/app

# Copy requirements and project files to /home/app
COPY . /home/app
RUN pip install --upgrade pip && \
    if [ -f requirements.txt ]; then pip install -r requirements.txt; fi

# Expose Streamlit default port
EXPOSE 8501

# Streamlit config (optional, disables telemetry)
ENV STREAMLIT_TELEMETRY_ENABLED=false

# Entrypoint to run Streamlit app desde la raíz del proyecto
CMD ["streamlit", "run", "ui/app.py", "--server.port=8501", "--server.address=0.0.0.0"]