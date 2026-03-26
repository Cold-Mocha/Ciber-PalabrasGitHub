FROM python:3.11-slim

WORKDIR /app

ENV PIP_NO_CACHE_DIR=1

COPY requirements.txt ./
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

COPY visualizer_service ./visualizer_service

ENV PYTHONPATH=/app

CMD ["uvicorn", "visualizer_service.app:app", "--host", "0.0.0.0", "--port", "8000"]

