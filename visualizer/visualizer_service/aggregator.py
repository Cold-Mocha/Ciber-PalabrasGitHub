# Agregador en memoria que consolida conteos, progreso y métricas para el visualizer.
from __future__ import annotations

import asyncio
import time
from collections import Counter, defaultdict, deque
from typing import Deque, Dict, List, Optional


class WordAggregator:
    """Maintains rolling word counts per language and signals updates to subscribers."""

    def __init__(self, default_top_n: int = 10):
        self.default_top_n = default_top_n
        self._counts: Dict[str, Counter] = defaultdict(Counter)
        self._repo_counts: Dict[str, Counter] = defaultdict(Counter)
        self._repo_language_totals: Dict[str, Counter] = defaultdict(Counter)
        self._repo_language_words: Dict[str, Dict[str, Counter]] = defaultdict(lambda: defaultdict(Counter))
        self._files_by_language: Dict[str, set[str]] = defaultdict(set)
        self._repo_files: Dict[str, Dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
        self._recent_activity: Deque[dict] = deque(maxlen=50)
        self._lock = asyncio.Lock()
        self._condition = asyncio.Condition(self._lock)
        self._version = 0
        self._started_at = time.time()
        self._repo_progress: Dict[str, dict] = {}

    async def reset(self) -> None:
        """Clears all counters (invoked on startup for a clean slate)."""
        async with self._condition:
            self._counts.clear()
            self._repo_counts.clear()
            self._repo_language_totals.clear()
            self._repo_language_words.clear()
            self._files_by_language.clear()
            self._repo_files.clear()
            self._recent_activity.clear()
            self._repo_progress.clear()
            self._version += 1
            self._started_at = time.time()
            self._condition.notify_all()

    async def record_word(
        self,
        language: Optional[str],
        word: Optional[str],
        repo: Optional[str] = None,
        file_path: Optional[str] = None,
        function_name: Optional[str] = None,
    ) -> None:
        """Records a single word occurrence for the provided language."""
        normalized_word = (word or "").strip().lower()
        normalized_language = (language or "unknown").strip().lower()
        repo_name = (repo or "unknown").strip() or "unknown"
        normalized_file = (file_path or "").strip()
        if not normalized_word:
            return

        async with self._condition:
            self._counts[normalized_language][normalized_word] += 1
            self._repo_counts[repo_name][normalized_word] += 1
            self._repo_language_totals[repo_name][normalized_language] += 1
            self._repo_language_words[repo_name][normalized_language][normalized_word] += 1
            if normalized_file:
                file_token = f"{repo_name}:{normalized_file}"
                self._files_by_language[normalized_language].add(file_token)
                self._repo_files[repo_name][normalized_language].add(normalized_file)
            self._recent_activity.append({
                "repo": repo_name,
                "language": normalized_language,
                "word": normalized_word,
                "repo_word_total": self._repo_counts[repo_name][normalized_word],
                "timestamp": time.time(),
                "function_name": function_name or "",
                "file_path": normalized_file,
            })
            self._version += 1
            self._condition.notify_all()

    async def record_progress(self, data: dict) -> None:
        repo = (data.get("repo") or "unknown").strip()
        total_py = int(data.get("total_python_files") or 0)
        total_java = int(data.get("total_java_files") or 0)
        processed_py = int(data.get("processed_python_files") or 0)
        processed_java = int(data.get("processed_java_files") or 0)
        status = (data.get("status") or "in_progress").strip()
        timestamp = time.time()

        def _percent(done: int, total: int) -> float:
            return round((done / total) * 100, 1) if total > 0 else 0.0

        async with self._condition:
            self._repo_progress[repo] = {
                "repo": repo,
                "status": status,
                "total_python_files": total_py,
                "total_java_files": total_java,
                "processed_python_files": processed_py,
                "processed_java_files": processed_java,
                "percent_python": _percent(processed_py, total_py),
                "percent_java": _percent(processed_java, total_java),
                "percent_overall": _percent(processed_py + processed_java, total_py + total_java),
                "updated_at": timestamp,
            }
            self._version += 1
            self._condition.notify_all()

    async def get_top_words(self, language: str, limit: Optional[int] = None) -> List[Dict[str, int]]:
        """Returns the Top-N words for the selected language."""
        limit = limit or self.default_top_n
        normalized_language = (language or "unknown").strip().lower()
        async with self._lock:
            counter = self._counts.get(normalized_language)
            if not counter:
                return []
            return [
                {"word": word, "count": count}
                for word, count in counter.most_common(limit)
            ]

    async def get_snapshot(self, languages: Optional[List[str]] = None, limit: Optional[int] = None) -> Dict[str, List[Dict[str, int]]]:
        """Returns a snapshot for the requested languages."""
        limit = limit or self.default_top_n
        async with self._lock:
            selected_languages = [
                (lang or "unknown").strip().lower() for lang in (languages or self._counts.keys())
            ]
            snapshot: Dict[str, List[Dict[str, int]]] = {}
            for lang in selected_languages:
                counter = self._counts.get(lang)
                if not counter:
                    snapshot[lang] = []
                    continue
                snapshot[lang] = [
                    {"word": word, "count": count}
                    for word, count in counter.most_common(limit)
                ]
            return snapshot

    async def wait_for_update(self, last_seen_version: int) -> int:
        """Blocks until a new update occurs and returns the new version."""
        async with self._condition:
            await self._condition.wait_for(lambda: self._version > last_seen_version)
            return self._version

    async def get_language_metrics(self) -> Dict[str, Dict[str, int]]:
        async with self._lock:
            metrics: Dict[str, Dict[str, int]] = {}
            for lang, counter in self._counts.items():
                metrics[lang] = {
                    "total_words": sum(counter.values()),
                    "unique_words": len(counter),
                    "files_processed": len(self._files_by_language.get(lang, set())),
                }
            return metrics

    async def get_top_repos(self, limit: int = 5, top_words: int = 5) -> List[dict]:
        async with self._lock:
            entries: List[dict] = []
            for repo, counter in self._repo_counts.items():
                total_words = sum(counter.values())
                languages = self._repo_language_totals.get(repo, Counter())
                files_by_lang = self._repo_files.get(repo, {})
                language_top_words = self._repo_language_words.get(repo, {})
                entries.append({
                    "repo": repo,
                    "total_words": total_words,
                    "languages": {lang: count for lang, count in languages.items()},
                    "files_processed": {lang: len(paths) for lang, paths in files_by_lang.items()},
                    "language_top_words": {
                        lang: [
                            {"word": word, "count": count}
                            for word, count in counter.most_common(top_words)
                        ]
                        for lang, counter in language_top_words.items()
                    },
                    "top_words": [
                        {"word": word, "count": count}
                        for word, count in counter.most_common(top_words)
                    ],
                })
            entries.sort(key=lambda item: item["total_words"], reverse=True)
            return entries[:limit]

    async def get_recent_activity(self, limit: int = 10) -> List[dict]:
        async with self._lock:
            return list(reversed(list(self._recent_activity)[-limit:]))

    async def get_dashboard_payload(
        self,
        language: str,
        limit: int,
        combined_limit: Optional[int] = None,
        repo_limit: int = 5,
        activity_limit: int = 10,
        repo_top_words: int = 5,
    ) -> dict:
        normalized_language = (language or "unknown").strip().lower()
        limit = limit or self.default_top_n
        async with self._lock:
            language_counter = self._counts.get(normalized_language)
            top_words = []
            if language_counter:
                top_words = [
                    {"word": word, "count": count}
                    for word, count in language_counter.most_common(limit)
                ]
            language_metrics = {}
            top_words_by_language: Dict[str, List[Dict[str, int]]] = {}
            for lang, counter in self._counts.items():
                language_metrics[lang] = {
                    "total_words": sum(counter.values()),
                    "unique_words": len(counter),
                    "files_processed": len(self._files_by_language.get(lang, set())),
                }
                top_words_by_language[lang] = [
                    {"word": word, "count": count}
                    for word, count in counter.most_common(limit)
                ]
            repo_entries: List[dict] = []
            for repo, counter in self._repo_counts.items():
                total_words = sum(counter.values())
                languages = self._repo_language_totals.get(repo, Counter())
                files_by_lang = self._repo_files.get(repo, {})
                language_top_words = self._repo_language_words.get(repo, {})
                repo_entries.append({
                    "repo": repo,
                    "total_words": total_words,
                    "languages": {lang: count for lang, count in languages.items()},
                    "files_processed": {lang: len(paths) for lang, paths in files_by_lang.items()},
                    "language_top_words": {
                        lang: [
                            {"word": word, "count": count}
                            for word, count in counter.most_common(repo_top_words)
                        ]
                        for lang, counter in language_top_words.items()
                    },
                    "top_words": [
                        {"word": word, "count": count}
                        for word, count in counter.most_common(repo_top_words)
                    ],
                })
            repo_entries.sort(key=lambda item: item["total_words"], reverse=True)
            activity = list(reversed(list(self._recent_activity)[-activity_limit:]))
            combined_counter = Counter()
            for counter in self._counts.values():
                combined_counter.update(counter)
            combined_lim = combined_limit or limit
            combined_top_words = [
                {"word": word, "count": count}
                for word, count in combined_counter.most_common(combined_lim)
            ]
            global_metrics = {
                "repositories": len(self._repo_counts),
                "total_words": sum(sum(counter.values()) for counter in self._counts.values()),
                "total_files": sum(len(files) for files in self._files_by_language.values()),
                "runtime_seconds": int(time.time() - self._started_at),
            }
            current_progress = None
            if self._repo_progress:
                latest_repo = max(self._repo_progress.values(), key=lambda r: r["updated_at"])
                current_progress = latest_repo

        return {
            "language": normalized_language,
            "top_words": top_words,
            "top_words_by_language": top_words_by_language,
            "language_metrics": language_metrics,
            "global_metrics": global_metrics,
            "combined_top_words": combined_top_words,
            "top_repos": repo_entries[:repo_limit],
            "recent_activity": activity,
            "current_repo_progress": current_progress,
        }
