# Cliente HTTP para consultar repositorios y archivos en GitHub

import httpx
import os
import asyncio

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
HEADERS = {"Authorization": f"Bearer {GITHUB_TOKEN}"} if GITHUB_TOKEN else {}
BASE_URL = "https://api.github.com"


async def get_top_repositories(client: httpx.AsyncClient, language: str, page: int) -> list[dict]:
    """Busca los repositorios más populares por lenguaje."""
    url = f"{BASE_URL}/search/repositories?q=language:{language}&sort=stars&order=desc&page={page}&per_page=5"

    response = await client.get(url, headers=HEADERS)

    if response.status_code == 403:
        print("[Rate Limit] Límite de GitHub alcanzado. Pausando 60 segundos...")
        await asyncio.sleep(60)
        return []

    response.raise_for_status()
    return response.json().get("items", [])


async def get_repository_files(client: httpx.AsyncClient, repo_full_name: str, default_branch: str) -> list[dict]:
    """Obtiene el árbol completo de archivos del repositorio."""
    url = f"{BASE_URL}/repos/{repo_full_name}/git/trees/{default_branch}?recursive=1"
    response = await client.get(url, headers=HEADERS)

    if response.status_code != 200:
        return []

    tree = response.json().get("tree", [])
    return [
        f for f in tree
        if f["type"] == "blob" and (f["path"].endswith(".py") or f["path"].endswith(".java"))
    ]


async def download_raw_code(
    client: httpx.AsyncClient,
    repo_full_name: str,
    default_branch: str,
    file_path: str,
) -> str:
    """Descarga el código fuente de un archivo desde raw.githubusercontent.com."""
    raw_url = f"https://raw.githubusercontent.com/{repo_full_name}/{default_branch}/{file_path}"
    try:
        response = await client.get(raw_url, headers=HEADERS)
        if response.status_code == 200:
            return response.text
    except Exception:
        pass
    return ""