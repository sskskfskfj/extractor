import csv
import subprocess
import sys
import tempfile
import unittest
import zipfile
from unittest.mock import patch

from pathlib import Path

from disclosure_search.matching import nearest_pair
from disclosure_search.search import search_dataset, write_csv
from disclosure_search import cli


HEADER = "CIK\tREPORT_DATE\tELEMENT_ID\tTAXONOMY_ID\tCONTEXT_ID\tUNIT_ID\tDECIMALS\tVALUE\n"


def row(cik, date, element, value):
    return f"{cik}\t{date}\t{element}\ttax\tctx\t\t\t{value}\n"


class MatchingTests(unittest.TestCase):
    def test_nearest_distance_and_reversed_order(self):
        match = nearest_pair("자기주식 취득 후 즉시 소각", "자기주식", "소각")
        self.assertEqual(match.distance, 9)
        self.assertEqual(nearest_pair("소각: 자기주식", "자기주식", "소각").distance, 2)

    def test_selects_nearest_repeated_occurrences(self):
        match = nearest_pair("자기주식 보유; 소각 예정 자기주식소각", "자기주식", "소각")
        self.assertEqual(match.distance, 0)

    def test_requires_both_terms_in_same_value(self):
        self.assertIsNone(nearest_pair("자기주식만 있음", "자기주식", "소각"))

    def test_nearest_sentence_requires_both_terms_in_same_sentence(self):
        from disclosure_search.matching import nearest_sentence

        self.assertIsNone(nearest_sentence("자기주식을 취득했습니다. 다음 해에 소각했습니다.", "자기주식", "소각"))
        sentence, pair = nearest_sentence("관련 내용입니다. 자기주식소각을 완료했습니다.", "자기주식", "소각")
        self.assertEqual(sentence, "자기주식소각을 완료했습니다.")
        self.assertEqual(pair.distance, 0)


class DatasetSearchTests(unittest.TestCase):
    def test_year_scope_company_ranking_and_csv(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "val.tsv"
            path.write_text(
                HEADER
                + row("00000001", "20251231", "dart-gcd_EntityRegistrantName", "가까운회사")
                + row("00000001", "20251231", "elem", "자기주식 취득분을 소각했습니다")
                + row("00000002", "20251231", "dart-gcd_EntityRegistrantName", "먼회사")
                + row("00000002", "20251231", "elem", "자기주식 취득분을 이사회 결의에 따라 모두 소각했습니다")
                + row("00000003", "20241231", "dart-gcd_EntityRegistrantName", "제외회사")
                + row("00000003", "20241231", "elem", "자기주식 소각")
                + row("00000004", "20251231", "elem", "자기주식만 있음")
                , encoding="utf-8"
            )
            results = search_dataset([path], ["2025"])
            self.assertEqual([r.cik for r in results], ["00000001", "00000002"])
            self.assertEqual(results[0].company_name, "가까운회사")
            self.assertEqual(results[0].closest_distance, 6)
            output = Path(temp) / "result.csv"
            write_csv(results, output)
            with output.open(encoding="utf-8-sig", newline="") as stream:
                reader = csv.DictReader(stream)
                rows = list(reader)
            self.assertEqual(reader.fieldnames, ["회사명", "문장"])
            self.assertEqual(rows[0]["회사명"], "가까운회사")

    def test_reads_val_tsv_from_zip(self):
        with tempfile.TemporaryDirectory() as temp:
            archive = Path(temp) / "sample.zip"
            with zipfile.ZipFile(archive, "w") as zipped:
                zipped.writestr("bundle/val.tsv", HEADER + row("00000001", "20260101", "e", "자기주식소각"))
            results = search_dataset([archive], ["2026"])
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0].closest_distance, 0)


class InputReuseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "project"
        self.output = Path(self.temp.name) / "out.csv"

    def tearDown(self):
        self.temp.cleanup()

    def _value_tsv(self):
        return (
            HEADER
            + row("00000001", "20251231", "dart-gcd_EntityRegistrantName", "가나다기업")
            + row("00000001", "20251231", "fact", "가나다기업은 자기주식소각을 완료했습니다.")
            + row("00000002", "20251231", "dart-gcd_EntityRegistrantName", "라마기업")
            + row("00000002", "20251231", "fact", "라마기업은 자기주식 취득분을 모두 소각했습니다.")
        )

    def test_company_count_option_is_removed(self):
        with self.assertRaises(SystemExit):
            cli.build_parser().parse_args(["--count", "1"])

    def test_existing_tsv_exports_all_matching_companies(self):
        data = self.root / "data"
        data.mkdir(parents=True)
        (data / "val.tsv").write_text(self._value_tsv(), encoding="utf-8")
        with patch.object(cli, "project_root", return_value=self.root), patch.object(
            cli, "download_official_bundles", side_effect=AssertionError("unexpected download")
        ):
            status = cli.main(["--output", str(self.output)])
        self.assertEqual(status, 0)
        with self.output.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            rows = list(reader)
        self.assertEqual(reader.fieldnames, ["회사명", "문장"])
        self.assertEqual(len(rows), 2)

    def test_standalone_skill_exports_all_matching_companies(self):
        dataset = self.root / "val.tsv"
        dataset.parent.mkdir(parents=True)
        dataset.write_text(self._value_tsv(), encoding="utf-8")
        skill_script = Path(__file__).resolve().parents[1] / "skills" / "opendart-keyword-csv" / "scripts" / "collect.py"

        completed = subprocess.run(
            [sys.executable, str(skill_script), "--dataset", str(dataset), "--output", str(self.output)],
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        with self.output.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            rows = list(reader)
        self.assertEqual(reader.fieldnames, ["회사명", "문장"])
        self.assertEqual(len(rows), 2)

        limited = subprocess.run(
            [sys.executable, str(skill_script), "--dataset", str(dataset), "--count", "1"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(limited.returncode, 0)

    def test_existing_zip_is_reused_with_no_download(self):
        archive = self.root / "opendart_dataset" / "existing.zip"
        archive.parent.mkdir(parents=True)
        with zipfile.ZipFile(archive, "w") as zipped:
            zipped.writestr("bundle/val.tsv", self._value_tsv())
        with patch.object(cli, "project_root", return_value=self.root), patch.object(
            cli, "download_official_bundles", side_effect=AssertionError("unexpected download")
        ):
            status = cli.main(["--no-download", "--output", str(self.output)])
        self.assertEqual(status, 0)
        with self.output.open(encoding="utf-8-sig", newline="") as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual(len(rows), 2)

    def test_partial_zip_set_requests_missing_bundles(self):
        archive = self.root / "opendart_dataset" / "2025_1Q_20261001021129.zip"
        archive.parent.mkdir(parents=True)
        with zipfile.ZipFile(archive, "w") as zipped:
            zipped.writestr("bundle/val.tsv", self._value_tsv())
        with patch.object(cli, "project_root", return_value=self.root), patch.object(
            cli, "download_official_bundles", return_value=[archive]
        ) as downloader:
            status = cli.main(["--output", str(self.output)])
        self.assertEqual(status, 0)
        downloader.assert_called_once_with(self.root / "opendart_dataset")


if __name__ == "__main__":
    unittest.main()
