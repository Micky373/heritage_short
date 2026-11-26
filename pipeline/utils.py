"""Shared validation, caching, retry, and run-logging utilities."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
import time
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TypeVar

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STORYBOARD = ROOT / "storyboard.json"
DEFAULT_SCHEMA = ROOT / "schema" / "storyboard.schema.json"
DEFAULT_CACHE = ROOT / ".cache" / "pipeline_cache.json"
DEFAULT_RUN_LOG = ROOT / "runs.jsonl"

T = TypeVar("T")


def validate_storyboard(
    storyboard_path: str | Path = DEFAULT_STORYBOARD,
    schema_path: str | Path = DEFAULT_SCHEMA,
) -> dict[str, Any]:
    """Load and strictly validate a storyboard against its JSON Schema."""
    storyboard_file = Path(storyboard_path)
    schema_file = Path(schema_path)
    with storyboard_file.open(encoding="utf-8") as file:
        storyboard = json.load(file)
    with schema_file.open(encoding="utf-8") as file:
        schema = json.load(file)

    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    errors = sorted(
        validator.iter_errors(storyboard),
        key=lambda error: tuple(str(part) for part in error.absolute_path),
    )
    if errors:
        details = "\n".join(
            f"- {'/'.join(str(part) for part in error.absolute_path) or '<root>'}: "
            f"{error.message}"
            for error in errors
        )
        raise ValueError(f"{storyboard_file} failed schema validation:\n{details}")
    return storyboard


def input_hash(inputs: Any) -> str:
    """Return a stable SHA-256 hash for JSON-serializable stage inputs."""
    serialized = json.dumps(
        inputs,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()


def file_hash(path: str | Path) -> str:
    """Return the SHA-256 hash of a file's contents."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _cache_key(stage: str, shot_id: str | None) -> str:
    return json.dumps([stage, shot_id], ensure_ascii=False, separators=(",", ":"))


def _stage_hash(stage: str, inputs: Any, shot_id: str | None) -> str:
    return input_hash({"stage": stage, "shot_id": shot_id, "inputs": inputs})


def _read_cache(cache_path: str | Path) -> dict[str, Any]:
    path = Path(cache_path)
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as file:
        cache = json.load(file)
    if not isinstance(cache, dict):
        raise ValueError(f"Pipeline cache must contain a JSON object: {path}")
    return cache


def is_cached(
    stage: str,
    inputs: Any,
    *,
    shot_id: str | None = None,
    cache_path: str | Path = DEFAULT_CACHE,
) -> bool:
    """Check whether this stage or shot already ran with identical inputs."""
    entry = _read_cache(cache_path).get(_cache_key(stage, shot_id))
    return isinstance(entry, dict) and entry.get("input_hash") == _stage_hash(
        stage, inputs, shot_id
    )


def mark_cached(
    stage: str,
    inputs: Any,
    *,
    shot_id: str | None = None,
    cache_path: str | Path = DEFAULT_CACHE,
) -> None:
    """Record successful stage inputs in the local JSON cache."""
    path = Path(cache_path)
    cache = _read_cache(path)
    cache[_cache_key(stage, shot_id)] = {
        "input_hash": _stage_hash(stage, inputs, shot_id),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f"{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as file:
            temporary_path = file.name
            json.dump(cache, file, ensure_ascii=False, indent=2)
            file.write("\n")
        os.replace(temporary_path, path)
    finally:
        if temporary_path is not None and os.path.exists(temporary_path):
            os.unlink(temporary_path)


def run_cached(
    stage: str,
    inputs: Any,
    operation: Callable[[], T],
    *,
    shot_id: str | None = None,
    cache_path: str | Path = DEFAULT_CACHE,
) -> tuple[bool, T | None]:
    """Skip an unchanged stage/shot, otherwise run it and cache success."""
    validate_storyboard()
    if is_cached(stage, inputs, shot_id=shot_id, cache_path=cache_path):
        return True, None
    result = operation()
    mark_cached(stage, inputs, shot_id=shot_id, cache_path=cache_path)
    return False, result


def retry_api_call(
    operation: Callable[[], T],
    *,
    retryable_exceptions: tuple[type[Exception], ...],
    max_attempts: int = 3,
    base_delay_sec: float = 1.0,
    sleep: Callable[[float], None] = time.sleep,
    should_retry: Callable[[Exception], bool] | None = None,
    on_attempt: Callable[[int], None] | None = None,
) -> T:
    """Retry specified API exceptions with exponential backoff."""
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")
    if base_delay_sec < 0:
        raise ValueError("base_delay_sec cannot be negative")
    if not retryable_exceptions:
        raise ValueError("retryable_exceptions cannot be empty")

    for attempt in range(max_attempts):
        if on_attempt is not None:
            on_attempt(attempt + 1)
        try:
            return operation()
        except retryable_exceptions as error:
            if attempt == max_attempts - 1 or (
                should_retry is not None and not should_retry(error)
            ):
                raise
            sleep(base_delay_sec * (2**attempt))
    raise RuntimeError("API retry loop exited unexpectedly")


def log_run(
    *,
    stage: str,
    shot_id: str | None,
    model: str,
    parameters: Mapping[str, Any],
    seed: int | None,
    latency_ms: float,
    cost_usd_est: float | None,
    status: str,
    log_path: str | Path = DEFAULT_RUN_LOG,
) -> None:
    """Append one structured record to the JSONL run log."""
    if latency_ms < 0:
        raise ValueError("latency_ms cannot be negative")
    if cost_usd_est is not None and cost_usd_est < 0:
        raise ValueError("cost_usd_est cannot be negative")

    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "stage": stage,
        "shot_id": shot_id,
        "model": model,
        "parameters": dict(parameters),
        "seed": seed,
        "latency_ms": round(latency_ms, 3),
        "cost_usd_est": cost_usd_est,
        "status": status,
    }
    path = Path(log_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n")


def run_logged_call(
    operation: Callable[[], T],
    *,
    stage: str,
    shot_id: str | None,
    model: str,
    parameters: Mapping[str, Any],
    seed: int | None = None,
    cost_usd_est: float | None = None,
    log_path: str | Path = DEFAULT_RUN_LOG,
) -> T:
    """Run an API call and append a success or error record."""
    started_at = time.perf_counter()
    try:
        result = operation()
    except Exception:
        log_run(
            stage=stage,
            shot_id=shot_id,
            model=model,
            parameters=parameters,
            seed=seed,
            latency_ms=(time.perf_counter() - started_at) * 1000,
            cost_usd_est=cost_usd_est,
            status="error",
            log_path=log_path,
        )
        raise
    log_run(
        stage=stage,
        shot_id=shot_id,
        model=model,
        parameters=parameters,
        seed=seed,
        latency_ms=(time.perf_counter() - started_at) * 1000,
        cost_usd_est=cost_usd_est,
        status="success",
        log_path=log_path,
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Storyboard pipeline utilities")
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate_parser = subparsers.add_parser(
        "validate", help="validate storyboard.json against its JSON Schema"
    )
    validate_parser.add_argument("--storyboard", type=Path, default=DEFAULT_STORYBOARD)
    validate_parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    args = parser.parse_args()

    if args.command == "validate":
        validate_storyboard(args.storyboard, args.schema)
        print(f"Valid storyboard: {args.storyboard}")
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
