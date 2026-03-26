# Visualizador de palabras en métodos (Python + Java)

Herramienta de diagnóstico para extraer las palabras más usadas en nombres de funciones/métodos de repos públicos en GitHub (Python y Java). Arquitectura productor–consumidor: **Miner** recolecta y envía a Redis, **Visualizer** consume en tiempo real y muestra rankings.

## Tecnologías principales
- **Miner**: Python 3, `httpx` (API GitHub), `javalang` (parseo Java), `ast` (parseo Python), Redis como cola.
- **Visualizer backend**: FastAPI + WebSockets, `redis.asyncio`, agregador en memoria.
- **Visualizer frontend**: HTML/CSS/JS plano (sin build), consumo de REST + WS.
- **Infra**: Docker + docker-compose (servicios: miner, visualizer, redis).

## Estructura del proyecto
```
PythonProject/
├─ docker-compose.yml        # Orquestación de servicios
├─ miner/                    # Productor
│  ├─ main.py                # Loop infinito, progreso y envío a Redis
│  ├─ github_client.py       # Consulta repos y descarga archivos
│  ├─ parsers.py             # Extrae nombres de funciones/métodos
│  ├─ word_splitter.py       # Separa identificadores en palabras
│  └─ Dockerfile             # Imagen del miner
├─ visualizer/               # Consumidor
│  ├─ visualizer_service/
│  │  ├─ app.py              # FastAPI + endpoints + websockets
│  │  ├─ aggregator.py       # Conteos, métricas y progreso en memoria
│  │  ├─ consumer.py         # Lee de Redis y alimenta el agregador
│  │  ├─ config.py           # Settings por env vars
│  │  └─ static/             # Frontend (HTML, CSS, JS)
│  └─ Dockerfile             # Imagen del visualizer
├─ README.md                 # Este documento
├─ .env.example              # Variables de entorno de ejemplo
```

## Decisiones y supuestos

## Cómo ejecutar
Requisitos: Docker y docker-compose instalados.

1) Clonar el repositorio
```bash
git clone <URL-Repo>
cd PythonProject
```

2) Configurar entorno
- Copia `.env.example` a `.env` y completa `GITHUB_TOKEN` (opcional, sin token el límite es 60 req/h).

3) Levantar servicios
```bash
docker compose up --build
```
4) Ver el dashboard
- Abre: `http://localhost:8000` (health: `http://localhost:8000/healthz`). Ajusta Top-N en la UI; el panel se actualiza en vivo.

5) Detener
```bash
docker compose down
```
