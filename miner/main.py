# Proceso de extracción que recorre repos, extrae palabras y las envía a Redis

import asyncio
import httpx
import redis
import os
import json

from github_client import get_top_repositories, get_repository_files, download_raw_code
from parsers import parse_python_functions, parse_java_methods
from word_splitter import extract_words_from_identifier

REDIS_HOST = os.getenv("REDIS_HOST", "redis")
redis_client = redis.Redis(host=REDIS_HOST, port=6379, db=0, decode_responses=True)


async def process_repository(client: httpx.AsyncClient, repo: dict, requested_language: str):
    print(f"Procesando repositorio: {repo['full_name']} (Estrellas: {repo['stargazers_count']})")

    files = await get_repository_files(client, repo['full_name'], repo['default_branch'])
    python_files = [f for f in files if f['path'].endswith('.py')]
    java_files = [f for f in files if f['path'].endswith('.java')]
    total_python = len(python_files)
    total_java = len(java_files)
    processed_python = 0
    processed_java = 0

    def _send_progress(status: str = "in_progress") -> None:
        progress_payload = json.dumps({
            "type": "progress",
            "repo": repo['full_name'],
            "status": status,
            "total_python_files": total_python,
            "total_java_files": total_java,
            "processed_python_files": processed_python,
            "processed_java_files": processed_java,
        })
        redis_client.rpush("extracted_words", progress_payload)

    _send_progress(status="start")

    for file_info in files:
        code = await download_raw_code(
            client,
            repo['full_name'],
            repo['default_branch'],
            file_info['path'],
        )
        if not code:
            continue

        if file_info['path'].endswith(".py"):
            function_names = parse_python_functions(code)
            detected_language = "python"
            processed_python += 1
        else:
            function_names = parse_java_methods(code)
            detected_language = "java"
            processed_java += 1

        for name in function_names:
            words = extract_words_from_identifier(name)
            for word in words:
                payload = json.dumps({
                    "word": word,
                    "language": detected_language,
                    "repo": repo['full_name'],
                    "file_path": file_info['path'],
                    "source_language": requested_language,
                    "function_name": name,
                })
                redis_client.rpush("extracted_words", payload)

        _send_progress()

    _send_progress(status="complete")


async def miner_loop():
    print("Iniciando Miner...")
    page = 1

    async with httpx.AsyncClient(timeout=15.0) as client:
        while True:
            for lang in ["python", "java"]:
                repos = await get_top_repositories(client, lang, page)

                for repo in repos:
                    await process_repository(client, repo, lang)
                    await asyncio.sleep(1)

            page += 1
            print(f"--- Avanzando a la página {page} ---")


if __name__ == "__main__":
    asyncio.run(miner_loop())