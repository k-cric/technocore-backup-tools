#!/usr/bin/env python3
"""Read-only JSONL backups for retained Technocore room exports."""

from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import os
import re
import sys
import tempfile
from datetime import UTC, datetime
from http.client import HTTPException
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

DEFAULT_BASE_URL = "https://technocore.chat"
DEFAULT_ROOMS = ("dev", "technocore-pulse")
MAX_EXPORT_BYTES = 16 * 1024 * 1024
REQUEST_TIMEOUT_SECONDS = 20
ROOM_NAME = re.compile(r"^[a-z0-9][a-z0-9_-]{0,47}$")
WORKSPACE = Path(__file__).resolve().parents[1]
OUTPUTS_DIR = WORKSPACE / "outputs"


class BackupError(Exception):
    """An expected backup failure that can be shown to the user."""


class _RejectRedirects(HTTPRedirectHandler):
    """Exports must remain a read of the approved host and route."""

    def redirect_request(self, *args: Any, **kwargs: Any) -> None:
        return None


def validate_room(room: str) -> str:
    if not ROOM_NAME.fullmatch(room):
        raise BackupError("방 이름이 올바르지 않습니다: " + repr(room))
    return room


def validate_base_url(base_url: str) -> str:
    try:
        parsed = urlsplit(base_url)
        port = parsed.port
    except ValueError as exc:
        raise BackupError("서버 주소 형식이 올바르지 않습니다.") from exc
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise BackupError("서버 주소 형식이 올바르지 않습니다.")
    if parsed.path not in ("", "/"):
        raise BackupError("서버 주소에는 경로를 넣을 수 없습니다.")
    host = parsed.hostname
    if not host:
        raise BackupError("서버 주소에 호스트가 없습니다.")
    if parsed.scheme == "https" and host.lower() == "technocore.chat":
        if port not in (None, 443):
            raise BackupError("공식 서버는 기본 HTTPS 포트만 사용할 수 있습니다.")
        return DEFAULT_BASE_URL
    if parsed.scheme == "http" and _is_loopback(host):
        if port is None:
            raise BackupError("연습용 로컬 서버 포트가 필요합니다.")
        return base_url.rstrip("/")
    raise BackupError(
        "공식 HTTPS 서버 또는 연습용 로컬 HTTP 서버만 사용할 수 있습니다."
    )


def _is_loopback(host: str) -> bool:
    if host.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def validate_backup_root(backup_root: Path, outputs_dir: Path = OUTPUTS_DIR) -> Path:
    """Allow backup folders only below this workspace's outputs directory."""
    root = backup_root.resolve()
    allowed = outputs_dir.resolve()
    try:
        root.relative_to(allowed)
    except ValueError as exc:
        raise BackupError(
            "백업 위치는 이 작업 폴더의 outputs 안에 있어야 합니다."
        ) from exc
    if root == allowed:
        raise BackupError("백업 위치는 outputs 안의 전용 폴더여야 합니다.")
    return root


def make_backup_directory(backup_root: Path) -> Path:
    backup_root.mkdir(parents=True, exist_ok=True)
    # Microseconds make ordinary runs distinct; the suffix also handles a collision.
    stem = datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ")
    for number in range(1000):
        name = stem if number == 0 else f"{stem}-{number:03d}"
        candidate = backup_root / name
        try:
            candidate.mkdir()
            return candidate
        except FileExistsError:
            continue
    raise BackupError("새 백업 폴더를 만들 수 없습니다. 잠시 후 다시 시도해 주세요.")


def _parse_export(data: bytes) -> tuple[int, int | None, int | None]:
    if not data:
        return 0, None, None
    if not data.endswith(b"\n"):
        raise BackupError("내보내기 데이터의 마지막 줄이 완전하지 않습니다.")
    first_seq: int | None = None
    last_seq: int | None = None
    count = 0
    for line_number, line in enumerate(data.splitlines(), start=1):
        if not line:
            raise BackupError(f"내보내기 {line_number}번째 줄이 비어 있습니다.")
        try:
            record = json.loads(line.decode("utf-8"), parse_int=int)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise BackupError(
                f"내보내기 {line_number}번째 줄이 올바른 JSON이 아닙니다."
            ) from exc
        if (
            not isinstance(record, dict)
            or not isinstance(record.get("seq"), int)
            or isinstance(record["seq"], bool)
        ):
            raise BackupError(f"내보내기 {line_number}번째 줄에 정수 seq가 없습니다.")
        seq = record["seq"]
        if first_seq is None:
            first_seq = seq
        last_seq = seq
        count += 1
    return count, first_seq, last_seq


def _read_export(url: str) -> tuple[bytes, str]:
    request = Request(
        url,
        headers={
            "Accept": "application/x-ndjson",
            "User-Agent": "technocore-room-backup/1",
        },
    )
    try:
        opener = build_opener(_RejectRedirects())
        with opener.open(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            if response.status != 200:
                raise BackupError(f"서버가 HTTP {response.status} 응답을 보냈습니다.")
            content_length = response.headers.get("Content-Length")
            if (
                content_length
                and content_length.isdigit()
                and int(content_length) > MAX_EXPORT_BYTES
            ):
                raise BackupError("내보내기 데이터가 16MiB 제한보다 큽니다.")
            generation = response.headers.get("X-Room-Generation")
            if generation is None:
                raise BackupError("응답에 X-Room-Generation 헤더가 없습니다.")
            chunks: list[bytes] = []
            total = 0
            while True:
                chunk = response.read(64 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_EXPORT_BYTES:
                    raise BackupError("내보내기 데이터가 16MiB 제한보다 큽니다.")
                chunks.append(chunk)
            data = b"".join(chunks)
            if (
                content_length
                and content_length.isdigit()
                and len(data) != int(content_length)
            ):
                raise BackupError(
                    "내보내기 데이터가 Content-Length보다 짧아 중간에 끊겼습니다."
                )
            return data, generation
    except HTTPError as exc:
        raise BackupError(f"서버가 HTTP {exc.code} 오류를 보냈습니다.") from exc
    except (HTTPException, URLError, TimeoutError, OSError) as exc:
        raise BackupError(
            f"서버에 연결하지 못했습니다: {exc.reason if isinstance(exc, URLError) else exc}"
        ) from exc


def _atomic_write(path: Path, data: bytes) -> None:
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    except Exception:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def backup_rooms(
    rooms: tuple[str, ...] = DEFAULT_ROOMS,
    base_url: str = DEFAULT_BASE_URL,
    backup_root: Path | None = None,
    *,
    outputs_dir: Path = OUTPUTS_DIR,
) -> tuple[Path, list[dict[str, Any]]]:
    """Back up rooms and return the created folder plus every result record."""
    base_url = validate_base_url(base_url)
    checked_rooms = tuple(validate_room(room) for room in rooms)
    if not checked_rooms:
        raise BackupError("백업할 방이 없습니다.")
    if len(set(checked_rooms)) != len(checked_rooms):
        raise BackupError("같은 방을 두 번 백업하도록 지정할 수 없습니다.")
    root = validate_backup_root(backup_root or outputs_dir / "backups", outputs_dir)
    destination = make_backup_directory(root)
    results: list[dict[str, Any]] = []
    for room in checked_rooms:
        source_url = f"{base_url}/r/{quote(room, safe='')}/export"
        fetched_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        try:
            data, generation = _read_export(source_url)
            record_count, first_seq, last_seq = _parse_export(data)
            file_name = f"{room}.jsonl"
            _atomic_write(destination / file_name, data)
            results.append(
                {
                    "room": room,
                    "status": "success",
                    "file": file_name,
                    "source_url": source_url,
                    "fetched_at": fetched_at,
                    "generation": generation,
                    "sha256": hashlib.sha256(data).hexdigest(),
                    "bytes": len(data),
                    "record_count": record_count,
                    "first_seq": first_seq,
                    "last_seq": last_seq,
                }
            )
        except (BackupError, OSError) as exc:
            results.append(
                {
                    "room": room,
                    "status": "failed",
                    "source_url": source_url,
                    "fetched_at": fetched_at,
                    "error": str(exc),
                }
            )
    manifest = {
        "created_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "base_url": base_url,
        "read_only": True,
        "max_export_bytes": MAX_EXPORT_BYTES,
        "rooms": results,
    }
    _atomic_write(
        destination / "manifest.json",
        json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8") + b"\n",
    )
    return destination, results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Technocore 방의 보존된 대화를 읽기 전용으로 백업합니다."
    )
    parser.add_argument(
        "--base-url", default=DEFAULT_BASE_URL, help="기본값: 공식 Technocore 서버"
    )
    parser.add_argument(
        "--room", action="append", help="백업할 방 이름 (여러 번 지정 가능)"
    )
    parser.add_argument("--output-dir", type=Path, help="outputs 안의 백업 폴더")
    args = parser.parse_args(argv)
    try:
        destination, results = backup_rooms(
            tuple(args.room or DEFAULT_ROOMS), args.base_url, args.output_dir
        )
    except (BackupError, OSError) as exc:
        print("백업을 시작할 수 없습니다:", exc, file=sys.stderr)
        return 2
    succeeded = [item for item in results if item["status"] == "success"]
    failed = [item for item in results if item["status"] == "failed"]
    print(f"백업 폴더: {destination}")
    for item in succeeded:
        print(f"완료: {item['room']} ({item['record_count']}개 기록)")
    for item in failed:
        print(f"실패: {item['room']} — {item['error']}", file=sys.stderr)
    print("기록: manifest.json")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
