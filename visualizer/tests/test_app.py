import pytest

from visualizer.visualizer_service.app import aggregator


@pytest.mark.asyncio
async def test_top_words_endpoint_returns_sorted_counts(async_client):
    for _ in range(3):
        await aggregator.record_word("python", "alpha")
    await aggregator.record_word("python", "beta")

    response = await async_client.get("/top-words", params={"language": "python", "limit": 2})

    assert response.status_code == 200
    payload = response.json()
    assert payload["language"] == "python"
    assert payload["top_words"][0] == {"word": "alpha", "count": 3}
    assert payload["top_words"][1] == {"word": "beta", "count": 1}


@pytest.mark.asyncio
async def test_top_words_endpoint_validates_language(async_client):
    response = await async_client.get("/top-words", params={"language": "ruby"})

    assert response.status_code == 400
    assert "Unsupported language" in response.json()["detail"]


@pytest.mark.asyncio
async def test_dashboard_endpoint_exposes_repo_and_activity(async_client):
    await aggregator.record_word("python", "alpha", repo="sample/repo", file_path="src/a.py", function_name="alpha")
    await aggregator.record_word("python", "alpha", repo="sample/repo", file_path="src/a.py", function_name="alpha")
    await aggregator.record_word("python", "beta", repo="sample/repo", file_path="src/b.py", function_name="beta")

    response = await async_client.get(
        "/dashboard",
        params={"language": "python", "limit": 5, "repo_limit": 3, "activity_limit": 3},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["language"] == "python"
    assert payload["language_metrics"]["python"]["total_words"] == 3
    assert payload["language_metrics"]["python"]["files_processed"] == 2
    assert payload["top_words_by_language"]["python"][0]["word"] == "alpha"
    assert payload["combined_top_words"][0]["word"] == "alpha"
    top_repo = payload["top_repos"][0]
    assert top_repo["repo"] == "sample/repo"
    assert top_repo["total_words"] == 3
    assert top_repo["language_top_words"]["python"][0]["word"] == "alpha"
    assert len(payload["recent_activity"]) > 0
    assert payload["recent_activity"][0]["function_name"] == "beta"
