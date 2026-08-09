"""
Orchestration layer for the traversal pipeline.

The TraversalPipeline class wires together the individual stages and
provides parallel execution of independent CPU / I/O bound stages via
ThreadPoolExecutor while preserving deterministic output ordering.
"""

from __future__ import annotations

import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Iterable, Optional

from .stages import (
    PipelineContext,
    FilteredFile,
    FileMetadata,
    DocumentResult,
    ProgressCallback,
    ProgressEventType,
    TraversalProgressEvent,
    discover_files,
    filter_file,
    extract_file_metadata,
    detect_file_language,
    create_document,
    load_file_content,
)


class TraversalPipeline:
    """
    Modular repository traversal pipeline.

    Stages
    ------
    1. discover  – walk the directory tree, collect file paths
    2. filter    – apply include/exclude/size/gitignore rules per file
    3. load      – read file content (I/O bound, parallelised)
    4. metadata  – extract file metadata
    5. language  – detect programming language
    6. document  – build final DocumentResult

    Thread safety
    -------------
    Shared structures (skipped list, errors list) are protected by locks.
    Output ordering is deterministic: documents are returned in the same
    order as discovered files, regardless of worker scheduling.

    Progress reporting
    ------------------
    Pass an optional ``progress_callback`` to receive
    :class:`TraversalProgressEvent` notifications while ``run()`` is
    processing. Events are emitted from the thread that calls ``run()``
    (never from pool worker threads) so the callback needs no locking.
    The callback is strictly optional — when omitted, behavior is identical
    to previous releases. See ``TraversalProgressEvent`` for details.
    """

    def __init__(
        self,
        folder_path: str,
        include_patterns: Iterable[str] | None = None,
        exclude_patterns: Iterable[str] | None = None,
        max_file_size_kb: int | None = 200,
        respect_gitignore: bool = False,
        max_workers: int | None = None,
        progress_callback: ProgressCallback | None = None,
    ):
        self.folder_path = folder_path
        self.include_patterns = include_patterns
        self.exclude_patterns = exclude_patterns
        self.max_file_size_kb = max_file_size_kb
        self.respect_gitignore = respect_gitignore
        self.max_workers = max_workers
        self.progress_callback = progress_callback

        # Thread-safe shared state
        self._lock = threading.Lock()
        self._skipped: list[tuple[str, str]] = []
        self._errors: list[str] = []

    def run(
        self,
    ) -> tuple[list[DocumentResult], PipelineContext]:
        """
        Execute the full pipeline.

        Returns
        -------
        (documents, context)
            documents – list of DocumentResult in deterministic order.
            context   – PipelineContext with root_path, skipped, errors.

        Progress
        --------
        When a ``progress_callback`` was registered, a
        ``FILES_DISCOVERED`` event is emitted once discovery completes and
        exactly one terminal event (``FILE_COMPLETED``, ``FILE_SKIPPED`` or
        ``FILE_FAILED``) is emitted per discovered file, so the final
        ``completed`` count equals ``total`` and progress is never
        double-counted.
        """
        # Reset state for each run
        self._errors.clear()
        self._skipped.clear()

        # Stage 1: Discover files (sequential, I/O bound via os.walk)
        discovered, ctx = discover_files(
            self.folder_path,
            include_patterns=self.include_patterns,
            exclude_patterns=self.exclude_patterns,
            max_file_size_kb=self.max_file_size_kb,
            respect_gitignore=self.respect_gitignore,
        )
        self._skipped = ctx.skipped

        # The total workload is now known — notify once so callers can set
        # up progress displays. All counters below are only ever mutated on
        # this (the caller's) thread, never on pool worker threads.
        total_work = len(discovered)
        self._emit(
            ProgressEventType.FILES_DISCOVERED,
            completed=0,
            total=total_work,
        )

        if not discovered:
            return [], PipelineContext(
                root_path=self.folder_path,
                skipped=self._skipped,
                errors=self._errors,
            )

        # Stage 2: Filter files (can be parallelised, but filtering is cheap;
        # we batch it with loading for efficiency)
        filtered: list[FilteredFile] = []
        completed_count = 0
        for abs_path in discovered:
            ff, reason = filter_file(
                abs_path,
                self.folder_path,
                include_patterns=self.include_patterns,
                exclude_patterns=self.exclude_patterns,
                max_file_size_kb=self.max_file_size_kb,
                respect_gitignore=self.respect_gitignore,
            )
            if ff is not None:
                filtered.append(ff)
            else:
                with self._lock:
                    rel = os.path.relpath(abs_path, self.folder_path).replace(
                        "\\", "/"
                    )
                    self._skipped.append((rel, reason or "filtered"))
                completed_count += 1
                self._emit(
                    ProgressEventType.FILE_SKIPPED,
                    completed=completed_count,
                    total=total_work,
                    relative_path=rel,
                    detail=reason or "filtered",
                )

        if not filtered:
            return [], PipelineContext(
                root_path=self.folder_path,
                skipped=self._skipped,
                errors=self._errors,
            )

        # Stages 3-6: Load content, extract metadata, detect language,
        # create document – parallelised per file.
        documents: list[Optional[DocumentResult]] = [None] * len(filtered)
        worker_count = self._resolve_worker_count(len(filtered))

        def process_file(index: int, ff: FilteredFile) -> Optional[str]:
            """Process a single file through stages 3-6.

            Returns the skip reason when the file cannot be loaded, or
            ``None`` on success (the document is placed in ``documents``).
            """
            # Stage 3: Load content (I/O bound)
            content, error = load_file_content(ff.absolute_path)
            if error is not None:
                with self._lock:
                    self._errors.append(
                        f"Error loading {ff.relative_path}: {error}"
                    )
                    self._skipped.append((ff.relative_path, error))
                return error

            # Stage 4: Extract metadata
            metadata = extract_file_metadata(ff, content)

            # Stage 5: Detect language
            language = detect_file_language(metadata, content)
            metadata = FileMetadata(
                absolute_path=metadata.absolute_path,
                relative_path=metadata.relative_path,
                file_name=metadata.file_name,
                file_type=metadata.file_type,
                file_size=metadata.file_size,
                language=language,
            )

            # Stage 6: Create document
            doc = create_document(metadata, content)

            # Place result at the correct index for ordering
            documents[index] = doc
            return None

        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = {
                executor.submit(process_file, i, ff): i
                for i, ff in enumerate(filtered)
            }
            for future in as_completed(futures):
                # Emit exactly one terminal progress event per file.
                # `as_completed` is consumed on the calling thread, so
                # `completed_count` (and the callbacks themselves) never
                # run on pool worker threads.
                idx = futures[future]
                ff = filtered[idx]
                completed_count += 1
                exc = future.exception()
                if exc is not None:
                    with self._lock:
                        self._errors.append(
                            f"Unexpected error processing {ff.relative_path}: {exc}"
                        )
                        self._skipped.append((ff.relative_path, f"unexpected_error: {exc}"))
                    self._emit(
                        ProgressEventType.FILE_FAILED,
                        completed=completed_count,
                        total=total_work,
                        relative_path=ff.relative_path,
                        detail=f"unexpected_error: {exc}",
                    )
                else:
                    skip_reason = future.result()
                    if skip_reason is not None:
                        self._emit(
                            ProgressEventType.FILE_SKIPPED,
                            completed=completed_count,
                            total=total_work,
                            relative_path=ff.relative_path,
                            detail=skip_reason,
                        )
                    else:
                        self._emit(
                            ProgressEventType.FILE_COMPLETED,
                            completed=completed_count,
                            total=total_work,
                            relative_path=ff.relative_path,
                        )

        # Filter out None entries (failed files) while preserving order
        result = [doc for doc in documents if doc is not None]

        return result, PipelineContext(
            root_path=self.folder_path,
            skipped=self._skipped,
            errors=self._errors,
        )

    def _emit(
        self,
        event_type: ProgressEventType,
        completed: int,
        total: int,
        relative_path: str | None = None,
        detail: str | None = None,
    ) -> None:
        """
        Build a progress event and forward it to the registered callback.

        Callbacks are always invoked from the thread calling ``run()``,
        never from pool worker threads. An exception raised by the callback
        is handled deliberately: the failure is recorded in ``ctx.errors`` so
        it stays visible to the caller, and traversal continues so a buggy
        observer can never corrupt pipeline state or prevent completion.
        """
        if self.progress_callback is None:
            return

        event = TraversalProgressEvent(
            event_type=event_type,
            completed=completed,
            total=total,
            relative_path=relative_path,
            detail=detail,
        )
        try:
            self.progress_callback(event)
        except Exception as exc:  # noqa: BLE001 - observer failures are isolated
            with self._lock:
                self._errors.append(f"Progress callback error: {exc}")

    def _resolve_worker_count(self, total_files: int) -> int:
        """Determine the number of worker threads to use."""
        if self.max_workers is not None:
            return max(1, self.max_workers)
        # Default: use up to 4 workers, but no more than the file count
        return min(4, max(1, total_files))