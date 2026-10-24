"""Command-line interface for the keyword-to-sentence CSV workflow."""

from __future__ import annotations

import argparse
import zipfile

from pathlib import Path

from .bundles import OFFICIAL_BUNDLES, UNAVAILABLE_BUNDLES, download_official_bundles
from .search import DEFAULT_YEARS, search_dataset, write_csv
from .sources import has_value_table


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _resolve_sources(args: argparse.Namespace) -> tuple[list[Path], str, list[str]]:
    root = project_root()
    if args.dataset:
        sources = [Path(item).expanduser() for item in args.dataset]
        missing = [str(path) for path in sources if not path.exists()]
        if missing:
            raise FileNotFoundError("입력 데이터 경로가 없습니다: " + ", ".join(missing))
        return sources, "사용자가 지정한 데이터", []

    bulk_dir = root / "opendart_dataset"
    zip_paths = sorted(bulk_dir.rglob("*.zip")) if bulk_dir.exists() else []
    usable_zips: list[Path] = []
    invalid_zips: list[Path] = []
    for path in zip_paths:
        (usable_zips if has_value_table(path) else invalid_zips).append(path)

    tsv_candidates = [
        bulk_dir / "val.tsv",
        root / "data" / "val.tsv",
        root.parent / "queryEngineDataset" / "val.tsv",
    ]
    if args.no_download:
        if usable_zips:
            found = {path.name for path in usable_zips}
            missing = [name for name in OFFICIAL_BUNDLES if name not in found]
            warnings = []
            if missing:
                warnings.append(f"공식 ZIP 일부만 사용합니다. 누락: {', '.join(missing)}")
            if invalid_zips:
                warnings.append(f"val.tsv가 없거나 손상된 ZIP은 제외했습니다: {', '.join(path.name for path in invalid_zips)}")
            return usable_zips, "opendart_dataset의 기존 ZIP", warnings
        for tsv_path in tsv_candidates:
            if tsv_path.is_file():
                return [tsv_path], "기존 로컬 val.tsv", []
        if invalid_zips:
            raise ValueError("유효하지 않은 ZIP만 있습니다: " + ", ".join(path.name for path in invalid_zips))
        raise FileNotFoundError("사용 가능한 ZIP 또는 val.tsv가 없습니다. `--no-download`를 빼거나 `--dataset`을 지정하세요.")

    if not zip_paths:
        for tsv_path in tsv_candidates:
            if tsv_path.is_file():
                return [tsv_path], "기존 로컬 val.tsv", []

    # Download any missing official bundles even when a previous run left a partial set.
    print("opendart_dataset/을 준비하고 누락된 OpenDART ZIP을 순서대로 확인합니다.", flush=True)
    downloaded = download_official_bundles(bulk_dir)
    return downloaded, "opendart_dataset ZIP", []


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="같은 문장 안에서 '자기주식'과 '소각'이 가까이 나온 기업을 찾아 CSV로 저장합니다."
    )
    parser.add_argument(
        "--dataset",
        action="append",
        help="val.tsv 파일, 데이터셋 폴더 또는 val.tsv가 든 ZIP. 여러 번 지정할 수 있습니다.",
    )
    parser.add_argument(
        "--report-year",
        action="append",
        dest="years",
        help="보고기준일 연도 (기본 2025, 2026; 여러 번 지정 가능)",
    )
    parser.add_argument("--all-years", action="store_true", help="보고기준일 연도 제한을 해제합니다.")
    parser.add_argument(
        "--output", default="results/keyword_proximity_bulk_2025_2026.csv", help="CSV 저장 위치"
    )
    parser.add_argument("--no-download", action="store_true", help="로컬 ZIP/TSV만 사용하고 다운로드하지 않습니다.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    years = None if args.all_years else (args.years or list(DEFAULT_YEARS))
    try:
        sources, source_label, warnings = _resolve_sources(args)
        results = search_dataset(sources, years)
    except (FileNotFoundError, ValueError, RuntimeError, OSError) as exc:
        print(f"오류: {exc}")
        return 2

    write_csv(results, args.output)
    year_label = "모든 연도" if years is None else ", ".join(years)
    print(f"입력 자료: {source_label} ({len(sources)}개)")
    print(f"검색 연도: {year_label} | 검색어: 자기주식 + 소각")
    print(f"조건에 맞는 전체 기업: {len(results)}곳 | CSV에 저장: {len(results)}곳")
    print(f"CSV 파일: {args.output} (회사명, 문장)")
    for warning in warnings:
        print(f"범위 안내: {warning}")
    if not args.dataset and source_label != "기존 로컬 val.tsv":
        for bundle, reason in UNAVAILABLE_BUNDLES.items():
            print(f"자료 안내: {bundle} 묶음은 포함되지 않았습니다 — {reason}")
    return 0
