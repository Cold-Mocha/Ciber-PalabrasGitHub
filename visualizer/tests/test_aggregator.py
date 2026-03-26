import asyncio

import pytest

from visualizer.visualizer_service.aggregator import WordAggregator


@pytest.mark.asyncio
async def test_record_and_retrieve_top_words_per_language():
    aggregator = WordAggregator(default_top_n=5)
    await aggregator.reset()

    await aggregator.record_word("python", "foo")
    await aggregator.record_word("python", "foo")
    await aggregator.record_word("python", "bar")
    await aggregator.record_word("java", "foo")

    python_top = await aggregator.get_top_words("python")
    java_top = await aggregator.get_top_words("java")

    assert python_top[0] == {"word": "foo", "count": 2}
    assert python_top[1] == {"word": "bar", "count": 1}
    assert java_top == [{"word": "foo", "count": 1}]


@pytest.mark.asyncio
async def test_wait_for_update_unblocks_on_new_data():
    aggregator = WordAggregator(default_top_n=5)
    await aggregator.reset()

    version_task = asyncio.create_task(aggregator.wait_for_update(-1))
    await asyncio.sleep(0)  # allow task to start waiting
    await aggregator.record_word("python", "hello")
    new_version = await version_task

    assert new_version >= 0


@pytest.mark.asyncio
async def test_get_snapshot_for_multiple_languages():
    aggregator = WordAggregator(default_top_n=5)
    await aggregator.reset()

    for word in ["foo", "bar", "foo"]:
        await aggregator.record_word("python", word)
    await aggregator.record_word("java", "baz")

    snapshot = await aggregator.get_snapshot(languages=["python", "java"], limit=2)

    assert snapshot["python"][0] == {"word": "foo", "count": 2}
    assert snapshot["python"][1] == {"word": "bar", "count": 1}
    assert snapshot["java"] == [{"word": "baz", "count": 1}]


@pytest.mark.asyncio
async def test_dashboard_payload_includes_repo_breakdown_and_activity():
    aggregator = WordAggregator(default_top_n=5)
    await aggregator.reset()

    await aggregator.record_word("python", "alpha", repo="team/repo", file_path="pkg/a.py", function_name="alpha_handler")
    await aggregator.record_word("python", "beta", repo="team/repo", file_path="pkg/a.py", function_name="beta_handler")
    await aggregator.record_word("java", "alpha", repo="team/repo", file_path="src/Main.java", function_name="alphaHandler")
    await aggregator.record_word("java", "gamma", repo="team/another", file_path="src/App.java", function_name="gammaHandler")

    payload = await aggregator.get_dashboard_payload(
        language="python",
        limit=5,
        repo_limit=5,
        activity_limit=4,
        repo_top_words=3,
    )

    assert payload["language"] == "python"
    assert payload["language_metrics"]["python"]["total_words"] == 2
    assert payload["language_metrics"]["java"]["files_processed"] == 2
    assert payload["top_words_by_language"]["java"][0]["word"] == "alpha"
    assert payload["combined_top_words"][0]["word"] == "alpha"
    top_repo = payload["top_repos"][0]
    assert top_repo["repo"] == "team/repo"
    assert top_repo["languages"]["python"] == 2
    assert top_repo["files_processed"]["java"] == 1
    assert top_repo["language_top_words"]["java"][0]["word"] == "alpha"
    assert len(payload["recent_activity"]) == 4
    assert payload["recent_activity"][0]["function_name"] != ""
