"""Robust PDF downloader with retries, deduplication, and manifest tracking."""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from config import (
    DOWNLOAD_MANIFEST_PATH,
    DOWNLOAD_MAX_RETRIES,
    DOWNLOAD_RETRY_BACKOFF_SECONDS,
    DOWNLOAD_TIMEOUT_SECONDS,
    SOURCE_DIRS,
    USER_AGENT,
)
from pipeline.materials_catalog import MaterialResource, MATERIALS_CATALOG

logger = logging.getLogger(__name__)


def sanitize_filename(name: str) -> str:
    """Return a filesystem-safe, readable filename."""
    stem = Path(name).stem
    suffix = Path(name).suffix.lower() or ".pdf"
    cleaned = re.sub(r"[^\w.\-]+", "_", stem)
    cleaned = re.sub(r"_+", "_", cleaned).strip("._")
    return f"{cleaned}{suffix}"


def file_sha256(path: Path) -> str:
    """Compute SHA-256 hash of file contents."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


class DownloadManifest:
    """Tracks downloaded URLs and content hashes to prevent duplicates."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._data: dict[str, Any] = {"by_url": {}, "by_hash": {}}
        self._load()

    def _load(self) -> None:
        if self.path.exists():
            with self.path.open(encoding="utf-8") as handle:
                self._data = json.load(handle)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            json.dump(self._data, handle, indent=2)

    def has_url(self, url: str) -> bool:
        return url in self._data["by_url"]

    def has_hash(self, content_hash: str) -> bool:
        return content_hash in self._data["by_hash"]

    def register(self, resource: MaterialResource, dest: Path, content_hash: str) -> None:
        entry = {
            "url": resource.url,
            "path": str(dest),
            "sha256": content_hash,
            "title": resource.title,
            "topic": resource.topic,
            "institution": resource.institution,
        }
        self._data["by_url"][resource.url] = entry
        self._data["by_hash"][content_hash] = entry


class MaterialDownloader:
    """Downloads curated educational PDFs into topic folders."""

    def __init__(self) -> None:
        self.manifest = DownloadManifest(DOWNLOAD_MANIFEST_PATH)
        self.stats = {
            "attempted": 0,
            "downloaded": 0,
            "skipped_duplicate": 0,
            "failed": 0,
        }

    def run(self, catalog: list[MaterialResource] | None = None) -> dict[str, int]:
        """Download all resources in the catalog."""
        items = catalog or MATERIALS_CATALOG
        for resource in items:
            self.stats["attempted"] += 1
            try:
                self._download_one(resource)
            except Exception as exc:  # noqa: BLE001 — log and continue
                self.stats["failed"] += 1
                logger.error("Failed to download %s: %s", resource.title, exc)
        self.manifest.save()
        return self.stats

    def _download_one(self, resource: MaterialResource) -> None:
        dest_dir = SOURCE_DIRS[resource.topic]
        dest_dir.mkdir(parents=True, exist_ok=True)
        filename = sanitize_filename(resource.filename)
        dest_path = dest_dir / filename

        if self.manifest.has_url(resource.url) and dest_path.exists():
            self.stats["skipped_duplicate"] += 1
            logger.info("Skipping (already in manifest): %s", resource.title)
            return

        if dest_path.exists():
            existing_hash = file_sha256(dest_path)
            if self.manifest.has_hash(existing_hash):
                self.stats["skipped_duplicate"] += 1
                logger.info("Skipping duplicate content: %s", dest_path.name)
                return

        content = self._fetch_with_retries(resource.url)
        content_hash = hashlib.sha256(content).hexdigest()

        if self.manifest.has_hash(content_hash):
            self.stats["skipped_duplicate"] += 1
            logger.info("Skipping duplicate hash for: %s", resource.title)
            return

        if not content.startswith(b"%PDF"):
            raise ValueError(f"Response is not a valid PDF for {resource.url}")

        dest_path.write_bytes(content)
        self.manifest.register(resource, dest_path, content_hash)
        self.stats["downloaded"] += 1
        logger.info("Downloaded: %s → %s", resource.title, dest_path)

    def _fetch_with_retries(self, url: str) -> bytes:
        last_error: Exception | None = None
        for attempt in range(1, DOWNLOAD_MAX_RETRIES + 1):
            try:
                request = Request(url, headers={"User-Agent": USER_AGENT})
                with urlopen(request, timeout=DOWNLOAD_TIMEOUT_SECONDS) as response:
                    return response.read()
            except (HTTPError, URLError, TimeoutError) as exc:
                last_error = exc
                wait = DOWNLOAD_RETRY_BACKOFF_SECONDS * attempt
                logger.warning(
                    "Attempt %d/%d failed for %s: %s (retry in %.1fs)",
                    attempt,
                    DOWNLOAD_MAX_RETRIES,
                    url,
                    exc,
                    wait,
                )
                if attempt < DOWNLOAD_MAX_RETRIES:
                    time.sleep(wait)
        raise RuntimeError(f"Download failed after {DOWNLOAD_MAX_RETRIES} attempts: {url}") from last_error
