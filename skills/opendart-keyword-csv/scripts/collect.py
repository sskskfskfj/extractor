#!/usr/bin/env python3
"""Download OpenDART XBRL-note bundles and export closest keyword sentences."""

from __future__ import annotations

import argparse
import csv
import html
import io
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.request
import zipfile

from pathlib import Path


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
    "2026_2Q": "현재 알려진 다운로드 링크가 정상 ZIP을 반환하지 않습니다."
}
NAME_ELEMENT = "EntityRegistrantName"
CSV_LIMIT = min(sys.maxsize, 2**31 - 1)
csv.field_size_limit(CSV_LIMIT)


def clean_text(value: str) -> str:
    value = html.unescape(value or "")
    value = re.sub(r"<[^>]*>", " ", value)
    value = unicodedata.normalize("NFKC", value)
    return re.sub(r"\s+", " ", value).strip()


def nearest_pair(text: str, first: str, second: str) -> tuple[int, int, int] | None:
    """Return (gap, start, end) for the nearest literal occurrence pair."""
    a = [match.span() for match in re.finditer(re.escape(first), text)]
    b = [match.span() for match in re.finditer(re.escape(second), text)]
    if not a or not b:
        return None

    best: tuple[int, int, int] | None = None
    i = j = 0
    while i < len(a) and j < len(b):
        a_start, a_end = a[i]
        b_start, b_end = b[j]
        if a_end <= b_start:
            candidate = (b_start - a_end, a_start, b_end)
            i += 1
        elif b_end <= a_start:
            candidate = (a_start - b_end, b_start, a_end)
            j += 1
        else:
            candidate = (0, min(a_start, b_start), max(a_end, b_end))
            i += 1
            j += 1
        if best is None or candidate < best:
            best = candidate
    return best


def matching_sentence(value: str, first: str, second: str) -> tuple[str, int] | None:
    """Select the sentence containing the closest pair from the evidence VALUE."""
    sentences = [part.strip() for part in re.split(r"(?<=[.!?。！？])\s+", value) if part.strip()]
    candidates = []
    for sentence in sentences:
        pair = nearest_pair(sentence, first, second)
        if pair is not None:
            candidates.append((pair[0], pair[1], sentence))
    if not candidates:
        return None
    distance, _, sentence = min(candidates)
    return sentence, distance


def _zip_has_value_table(path: Path) -> bool:
    if not zipfile.is_zipfile(path):
        return False
    try:
        with zipfile.ZipFile(path) as archive:
            return any(Path(member).name.lower() == "val.tsv" for member in archive.namelist())
    except (OSError, zipfile.BadZipFile):
        return False


def download_bundles(data_dir: Path) -> list[Path]:
    """Create the data folder and fetch every missing official archive in order."""
    data_dir.mkdir(parents=True, exist_ok=True)
    downloaded = []
    total = len(OFFICIAL_BUNDLES)
    for index, (filename, url) in enumerate(OFFICIAL_BUNDLES.items(), start=1):
        target = data_dir / filename
        if target.exists() and _zip_has_value_table(target):
            downloaded.append(target)
            print(f"[{index}/{total}] 기존 ZIP 사용: {target}", flush=True)
            continue

        print(f"[{index}/{total}] ZIP 다운로드: {filename}", flush=True)
        partial = target.with_suffix(target.suffix + ".part")
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                request = urllib.request.Request(url, headers={"User-Agent": "opendart-keyword-csv/1.0"})
                with urllib.request.urlopen(request, timeout=90) as response, partial.open("wb") as output:
                    while chunk := response.read(1024 * 1024):
                        output.write(chunk)
                if not _zip_has_value_table(partial):
                    raise ValueError(f"val.tsv를 포함한 정상 ZIP이 아닙니다: {filename}")
                partial.replace(target)
                downloaded.append(target)
                print(f"다운로드 완료: {target} ({target.stat().st_size:,} bytes)", flush=True)
                last_error = None
                break
            except (OSError, urllib.error.URLError, ValueError) as exc:
                last_error = exc
                partial.unlink(missing_ok=True)
                if attempt < 2:
                    time.sleep(2**attempt)
        if last_error:
            raise RuntimeError(f"{filename} 다운로드 실패: {last_error}") from last_error
    return downloaded


def input_sources(args: argparse.Namespace) -> list[Path]:
    if args.dataset:
        sources = [Path(item).expanduser() for item in args.dataset]
    else:
        data_dir = args.data_dir.expanduser()
        local_tsvs = [data_dir / "val.tsv", Path("data/val.tsv"), Path("../queryEngineDataset/val.tsv")]
        existing_tsv = next((path for path in local_tsvs if path.is_file()), None)
        sources = sorted(data_dir.glob("*.zip"))
        if args.no_download:
            if sources:
                invalid = [path.name for path in sources if not _zip_has_value_table(path)]
                if invalid:
                    raise ValueError("val.tsv가 없거나 손상된 ZIP: " + ", ".join(invalid))
            elif existing_tsv:
                sources = [existing_tsv]
            else:
                raise FileNotFoundError(f"사용 가능한 ZIP 또는 val.tsv가 없습니다: {data_dir}")
        elif existing_tsv and not sources:
            sources = [existing_tsv]
        else:
            # Also fill gaps after an interrupted/partial download. Valid archives are reused.
            sources = download_bundles(data_dir)
    for source in sources:
        if not source.exists():
            raise FileNotFoundError(f"입력 경로가 없습니다: {source}")
    return sources


def iter_rows(source: Path):
    if source.is_dir():
        source = source / "val.tsv"
    if source.name.lower() == "val.tsv":
        with source.open("r", encoding="utf-8-sig", newline="") as stream:
            yield from csv.DictReader(stream, delimiter="\t")
        return
    if not zipfile.is_zipfile(source):
        raise ValueError(f"TSV 파일, 데이터셋 폴더 또는 ZIP이 아닙니다: {source}")
    with zipfile.ZipFile(source) as archive:
        members = [name for name in archive.namelist() if Path(name).name.lower() == "val.tsv"]
        if not members:
            raise ValueError(f"ZIP 안에 val.tsv가 없습니다: {source}")
        for name in members:
            with archive.open(name) as binary, io.TextIOWrapper(binary, encoding="utf-8-sig", newline="") as stream:
                yield from csv.DictReader(stream, delimiter="\t")


def extract_results(
    sources: list[Path], years: set[str], first: str, second: str
) -> tuple[list[dict[str, object]], int, int]:
    names: dict[str, str] = {}
    results: dict[str, dict[str, object]] = {}
    rows_scanned = 0
    matching_rows = 0

    for source in sources:
        print(f"검색 중: {source}", flush=True)
        for row in iter_rows(source):
            rows_scanned += 1
            cik = (row.get("CIK") or "").strip().zfill(8)
            if not cik or cik == "00000000":
                continue
            element = (row.get("ELEMENT_ID") or "").split("_")[-1]
            if element == NAME_ELEMENT or (row.get("ELEMENT_ID") or "").endswith("_" + NAME_ELEMENT):
                name = (row.get("VALUE") or "").strip()
                if name:
                    names[cik] = name

            report_date = (row.get("REPORT_DATE") or "").strip()
            if len(report_date) < 4 or report_date[:4] not in years:
                continue
            value = clean_text(row.get("VALUE") or "")
            sentence_match = matching_sentence(value, first, second)
            if sentence_match is None:
                continue
            sentence, distance = sentence_match
            matching_rows += 1
            current = results.get(cik)
            if current is None:
                results[cik] = {
                    "distance": distance,
                    "sentence": sentence,
                    "company_name": "",
                }
            elif distance < int(current["distance"]):
                current["distance"] = distance
                current["sentence"] = sentence

    official_names = load_official_names()
    for cik, item in results.items():
        item["company_name"] = official_names.get(cik) or names.get(cik, "")
        item["cik"] = cik
    ranked = sorted(
        results.values(),
        key=lambda item: (int(item["distance"]), str(item["company_name"]).casefold(), str(item["cik"])),
    )
    return ranked, rows_scanned, matching_rows


def load_official_names() -> dict[str, str]:
    """Read the bundled OpenDART Korean corporate-name snapshot when present."""
    names_path = Path(__file__).resolve().parent.parent / "assets" / "company_names.tsv"
    if not names_path.exists():
        return {}
    with names_path.open("r", encoding="utf-8-sig", newline="") as stream:
        return {
            row["CIK"].strip().zfill(8): row["회사명"].strip()
            for row in csv.DictReader(stream, delimiter="\t")
            if row.get("CIK") and row.get("회사명")
        }


def write_csv(results: list[tuple[str, str]], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["회사명", "문장"])
        writer.writerows(results)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="OpenDART XBRL에서 키워드 근접 문장을 찾아 CSV로 저장합니다.")
    parser.add_argument("--data-dir", type=Path, default=Path("opendart_dataset"), help="ZIP 저장/검색 폴더")
    parser.add_argument("--dataset", action="append", help="로컬 val.tsv, 데이터셋 폴더 또는 ZIP (반복 가능)")
    parser.add_argument("--no-download", action="store_true", help="기존 --data-dir ZIP만 사용")
    parser.add_argument("--output", type=Path, default=Path("results/keyword_proximity_bulk_2025_2026.csv"))
    parser.add_argument("--count", "--top", type=int, default=30, dest="count", help="내보낼 상위 회사 수 (기본 30)")
    parser.add_argument("--year", action="append", dest="years", default=None, help="보고기준일 연도 (기본: 2025, 2026)")
    parser.add_argument("--keyword", action="append", dest="keywords", help="두 키워드를 순서대로 두 번 지정")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.count < 1:
        print("오류: --count는 1 이상이어야 합니다.", file=sys.stderr)
        return 2
    keywords = args.keywords or ["자기주식", "소각"]
    if len(keywords) != 2 or not all(keywords):
        print("오류: --keyword는 비어 있지 않은 키워드를 정확히 두 번 지정하세요.", file=sys.stderr)
        return 2
    years = set(args.years or ["2025", "2026"])
    try:
        sources = input_sources(args)
        ranked, rows_scanned, matching_rows = extract_results(sources, years, keywords[0], keywords[1])
    except (OSError, ValueError, RuntimeError, zipfile.BadZipFile) as exc:
        print(f"오류: {exc}", file=sys.stderr)
        return 2

    export_rows: list[tuple[str, str]] = []
    missing_names = 0
    candidates = ranked[: args.count]
    for result in candidates:
        sentence = str(result["sentence"])
        name = str(result["company_name"]).strip()
        if not name:
            missing_names += 1
            name = f"기업명 미확인 ({result['cik']})"
        export_rows.append((name, sentence))

    write_csv(export_rows, args.output)
    print(f"검색 연도: {', '.join(sorted(years))}")
    print(f"검색 ZIP/데이터 소스: {len(sources)}개 | 스캔 행: {rows_scanned:,}개")
    print(f"두 키워드 일치 행: {matching_rows:,}개 | 기업: {len(ranked):,}곳")
    print(f"CSV 저장: {args.output} | 문장 {len(export_rows)}개 | 컬럼: 회사명, 문장")
    if args.no_download and not args.dataset and sources and all(source.suffix.lower() == ".zip" for source in sources):
        found = {source.name for source in sources}
        missing = [name for name in OFFICIAL_BUNDLES if name not in found]
        if missing:
            print(f"범위 경고: 일부 공식 ZIP만 사용했습니다. 누락: {', '.join(missing)}")
    if missing_names:
        print(f"주의: 데이터에서 기업명을 찾지 못한 기업: {missing_names}곳 (CIK를 표시함)")
    if not args.dataset and not args.no_download:
        for bundle, reason in UNAVAILABLE_BUNDLES.items():
            print(f"범위 안내: {bundle} 묶음은 검색하지 않았습니다 — {reason}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
