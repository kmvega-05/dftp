FROM python:3.9-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV STREAMLIT_TELEMETRY_ENABLED=false
ENV CLIENT_FAST_START=1

WORKDIR /home/app

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

RUN pip3 install -r requirements.txt

# Copy the rest of the application code
COPY . .

# Make the entrypoint script executable
RUN chmod +x entrypoint.py

# Expose Streamlit default port
EXPOSE 8501

# Single entrypoint: the Python script that handles all initialization and startup
ENTRYPOINT ["python3", "-u", "entrypoint.py"]