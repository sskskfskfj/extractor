"""Official OpenDART XBRL note archives published on 2026-10-21."""

from __future__ import annotations

import time

from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

from .sources import has_value_table


OFFICIAL_BUNDLES = {
    "2025_1Q_20261001021129.zip": "https://opendart.fss.or.kr/xbrlNote/2025_1Q_20261001021129.zip",
    "2025_2Q_20261001014121.zip": "https://opendart.fss.or.kr/xbrlNote/2025_2Q_20261001014121.zip",
    "2025_3Q_20261001023825.zip": "https://opendart.fss.or.kr/xbrlNote/2025_3Q_20261001023825.zip",
    "2025_4Q_20261008010013.zip": "https://opendart.fss.or.kr/xbrlNote/2025_4Q_20261008010013.zip",
    "2026_1Q_20260929032749.zip": "https://opendart.fss.or.kr/xbrlNote/2026_1Q_20260929032749.zip",
    "2026_3Q_20261016015502.zip": "https://opendart.fss.or.kr/xbrlNote/2026_3Q_20261016015502.zip",
    "2026_4Q_20261008021129.zip": "https://opendart.fss.or.kr/xbrlNote/2026_4Q_20261008021129.zip",
}
UNAVAILABLE_BUNDLES = {
    "2026_2Q_20261021010008.zip": "목록에 표시되지만 다운로드 URL이 오류 페이지로 연결됨",
}


def download_official_bundles(destination: str | Path, retries: int = 3) -> list[Path]:
    """Download all published 2025/2026 bundles, atomically verifying each ZIP."""
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    downloaded: list[Path] = []
    total = len(OFFICIAL_BUNDLES)
    for index, (filename, url) in enumerate(OFFICIAL_BUNDLES.items(), start=1):
        target = destination / filename
        if target.exists() and has_value_table(target):
            downloaded.append(target)
            print(f"[{index}/{total}] 기존 ZIP 사용: {filename}", flush=True)
            continue
        print(f"[{index}/{total}] ZIP 다운로드: {filename}", flush=True)
        partial = target.with_suffix(target.suffix + ".part")
        last_error: Exception | None = None
        for attempt in range(retries):
            try:
                request = Request(url, headers={"User-Agent": "queryEngine/1.0"})
                with urlopen(request, timeout=90) as response, partial.open("wb") as output:
                    while chunk := response.read(1024 * 1024):
                        output.write(chunk)
                if not has_value_table(partial):
                    raise ValueError(f"val.tsv가 포함된 정상 ZIP이 아닙니다: {filename}")
                partial.replace(target)
                downloaded.append(target)
                print(f"완료: {filename} ({target.stat().st_size:,} bytes)", flush=True)
                last_error = None
                break
            except (OSError, URLError, ValueError) as exc:
                last_error = exc
                partial.unlink(missing_ok=True)
                if attempt + 1 < retries:
                    time.sleep(2 ** attempt)
        if last_error:
            raise RuntimeError(f"{filename} 다운로드 실패: {last_error}") from last_error
    return downloaded


def main() -> int:
    from .cli import project_root

    output_dir = project_root() / "opendart_dataset"
    print(f"OpenDART 주석 ZIP 저장 위치: {output_dir}")
    files = download_official_bundles(output_dir)
    print(f"준비된 공식 ZIP: {len(files)}/{len(OFFICIAL_BUNDLES)}")
    for filename, reason in UNAVAILABLE_BUNDLES.items():
        print(f"미지원 묶음: {filename} — {reason}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
