"""Search XBRL VALUE facts and export the closest matching sentence per company."""

from __future__ import annotations

import csv

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .matching import nearest_pair, nearest_sentence
from .sources import iter_value_rows

KEYWORDS = ("자기주식", "소각")
DEFAULT_YEARS = ("2025", "2026")
NAME_ELEMENT = "EntityRegistrantName"


@dataclass
class CompanyResult:
    cik: str
    company_name: str
    closest_distance: int
    sentence: str


def _official_company_names() -> dict[str, str]:
    """Load the bundled Korean company-name snapshot without calling an API."""
    names_path = Path(__file__).resolve().parents[1] / "skills" / "opendart-keyword-csv" / "assets" / "company_names.tsv"
    if not names_path.exists():
        return {}
    with names_path.open("r", encoding="utf-8-sig", newline="") as stream:
        return {
            row["CIK"].strip().zfill(8): row["회사명"].strip()
            for row in csv.DictReader(stream, delimiter="\t")
            if row.get("CIK") and row.get("회사명")
        }


def search_dataset(
    sources: Iterable[str | Path], years: Iterable[str] | None = DEFAULT_YEARS
) -> list[CompanyResult]:
    """Return companies ranked by nearest two-keyword sentence distance."""
    year_set = None if years is None else {str(year) for year in years}
    names: dict[str, str] = {}
    results: dict[str, CompanyResult] = {}

    for source in sources:
        for row in iter_value_rows(source):
            cik = (row.get("CIK") or "").strip().zfill(8)
            if not cik or cik == "00000000":
                continue

            element = (row.get("ELEMENT_ID") or "").split("_")[-1]
            if element == NAME_ELEMENT or (row.get("ELEMENT_ID") or "").endswith("_" + NAME_ELEMENT):
                name = (row.get("VALUE") or "").strip()
                if name:
                    names[cik] = name

            report_date = (row.get("REPORT_DATE") or "").strip()
            if len(report_date) < 4 or (year_set is not None and report_date[:4] not in year_set):
                continue
            value = row.get("VALUE") or ""
            if nearest_pair(value, *KEYWORDS) is None:
                continue

            result = results.get(cik)
            sentence_match = nearest_sentence(value, *KEYWORDS)
            if sentence_match is None:
                continue
            sentence, match = sentence_match

            if result is None:
                results[cik] = CompanyResult(
                    cik=cik,
                    company_name="",
                    closest_distance=match.distance,
                    sentence=sentence,
                )
            elif match.distance < result.closest_distance:
                result.closest_distance = match.distance
                result.sentence = sentence

    official_names = _official_company_names()
    for cik, result in results.items():
        result.company_name = official_names.get(cik) or names.get(cik, f"기업명 미확인 ({cik})")

    return sorted(
        results.values(),
        key=lambda item: (item.closest_distance, item.company_name.casefold(), item.cik),
    )


def write_csv(results: Iterable[CompanyResult], path: str | Path) -> None:
    """Write the user-facing two-column CSV."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["회사명", "문장"])
        writer.writerows((result.company_name, result.sentence) for result in results)
