FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Usamos -u (unbuffered) para ver los logs en tiempo real en Docker
CMD ["python", "-u", "main.py"]