FROM python:3.9-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /home/app

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

RUN pip install -r requirements.txt

# Copy the rest of the application code
COPY . .

# Expose Streamlit default port
EXPOSE 8501

# Streamlit config (optional, disables telemetry)
ENV STREAMLIT_TELEMETRY_ENABLED=false

# Entrypoint to run Streamlit app desde la raíz del proyecto
CMD ["streamlit", "run", "ui/app.py", "--server.port=8501", "--server.address=0.0.0.0"]