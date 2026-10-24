"""Streaming readers for local TSV datasets and ZIP archives."""

from __future__ import annotations

import csv
import io
import sys
import zipfile

from pathlib import Path
from collections.abc import Iterator


# XBRL narrative facts can be much larger than csv's 128 KiB default.
csv.field_size_limit(min(sys.maxsize, 2**31 - 1))


def iter_value_rows(source: str | Path) -> Iterator[dict[str, str]]:
    path = Path(source).expanduser()
    if path.is_dir():
        path = path / "val.tsv"
    if not path.exists():
        raise FileNotFoundError(f"데이터 파일을 찾을 수 없습니다: {path}")

    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as archive:
            names = [name for name in archive.namelist() if Path(name).name.lower() == "val.tsv"]
            if not names:
                raise ValueError(f"ZIP 안에 val.tsv가 없습니다: {path}")
            for name in names:
                with archive.open(name) as binary, io.TextIOWrapper(binary, encoding="utf-8-sig", newline="") as stream:
                    yield from csv.DictReader(stream, delimiter="\t")
        return

    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        yield from csv.DictReader(stream, delimiter="\t")
