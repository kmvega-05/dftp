FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 21 20 50000-50010

CMD ["python", "-u", "main.py"]