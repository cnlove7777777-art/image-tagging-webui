"""Runtime safety patch for ZIP uploads.

The legacy upload pipeline extracts archives in ``app.tasks.processing.prepare_task``
with ``zipfile.ZipFile.extract(member, unpack_dir)``. That is convenient, but the
raw ZipInfo filename can contain absolute paths, ``..`` segments, Windows drive
letters, mixed slashes, or non-UTF-8 Chinese filenames.

This module is imported automatically by Python when the backend directory is on
``sys.path``. It patches ``ZipFile.extract`` once so the existing pipeline gets:

- path traversal protection;
- normalized portable relative paths;
- best-effort GBK filename recovery for older Windows ZIP files;
- clearer errors for unsafe archive members.

Keep this patch small and conservative. A future cleanup should replace it with
an explicit ``safe_extract_zip`` helper inside ``processing.py``.
"""

from __future__ import annotations

import os
import posixpath
import re
import zipfile
from pathlib import PurePosixPath, PureWindowsPath
from typing import Union

_ORIGINAL_EXTRACT = zipfile.ZipFile.extract
_PATCHED_FLAG = "_image_tagging_safe_extract_patched"


def _maybe_decode_legacy_zip_name(info: zipfile.ZipInfo) -> str:
    name = info.filename or ""
    # UTF-8 flag set by the ZIP spec. When absent, Python decodes as cp437.
    # Many Chinese Windows archives were actually encoded in GBK/CP936, so try
    # to recover readable names. ASCII names are unchanged by this path.
    if info.flag_bits & 0x800:
        return name
    try:
        return name.encode("cp437").decode("gbk")
    except Exception:
        return name


def _safe_zip_member_name(info: zipfile.ZipInfo) -> str:
    raw_name = _maybe_decode_legacy_zip_name(info)
    name = raw_name.replace("\\", "/").strip()
    name = name.lstrip("/")

    # Drop Windows drive/UNC prefixes by parsing as a Windows path first.
    win_path = PureWindowsPath(name)
    if win_path.drive or str(name).startswith(("//", "\\\\")):
        raise ValueError(f"Unsafe absolute ZIP path: {raw_name!r}")

    normalized = posixpath.normpath(name)
    if normalized in ("", "."):
        raise ValueError(f"Empty ZIP member path: {raw_name!r}")

    path = PurePosixPath(normalized)
    if path.is_absolute() or any(part in ("..", "") for part in path.parts):
        raise ValueError(f"Unsafe ZIP path traversal: {raw_name!r}")

    # Avoid characters that are invalid or painful on Windows. Preserve Chinese
    # and normal punctuation; just replace control/reserved path characters.
    safe_parts = []
    for part in path.parts:
        safe_part = re.sub(r'[<>:"|?*\x00-\x1f]', "_", part).strip()
        safe_part = safe_part.rstrip(". ")
        if not safe_part or safe_part in (".", ".."):
            raise ValueError(f"Unsafe ZIP path component: {raw_name!r}")
        safe_parts.append(safe_part)
    return "/".join(safe_parts)


def _safe_extract(self: zipfile.ZipFile, member: Union[str, zipfile.ZipInfo], path=None, pwd=None):
    info = self.getinfo(member) if isinstance(member, str) else member
    safe_name = _safe_zip_member_name(info)

    # Mutate only for this extraction call. The caller in processing.py appends
    # member.filename after extraction, so this keeps DB paths aligned with the
    # actual extracted path.
    original_name = info.filename
    info.filename = safe_name
    try:
        return _ORIGINAL_EXTRACT(self, info, path, pwd)
    finally:
        # Keep the sanitized name when extraction succeeded so legacy callers
        # that read member.filename immediately after extract get the real path.
        # If extraction itself failed, restoring is less surprising for logs.
        if not os.path.exists(os.path.join(path or os.getcwd(), safe_name)):
            info.filename = original_name


if not getattr(zipfile.ZipFile, _PATCHED_FLAG, False):
    zipfile.ZipFile.extract = _safe_extract  # type: ignore[method-assign]
    setattr(zipfile.ZipFile, _PATCHED_FLAG, True)
