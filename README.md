# Palabras Contador - Github Mining y Visualización en Tiempo Real

Herramienta simple que lee repos públicos de GitHub (Python y Java), toma los nombres de funciones/métodos y cuenta las palabras más usadas. Funciona como productor–consumidor: el **Miner** envía datos a Redis y el **Visualizer** los muestra en vivo.

## Tecnologías principales
- **Miner**: Python 3 con `httpx` (API GitHub), `javalang`, `ast` y Redis como cola
- **Visualizer**: FastAPI + WebSockets y frontend HTML/CSS/JS que consume REST y WS
- 
## Decisiones y supuestos
- Se lee TODO el repositorio (todos los archivos .py y .java) por cada proyecto.
- Redis se usa como cola de mensajes ligera para transportar eventos rápido entre productor y consumidor.
- El token de GitHub amplía el número de peticiones (funciona sin él, pero con límite)

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
