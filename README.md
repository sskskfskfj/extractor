# OpenDART 자기주식 소각 검색

`자기주식`과 `소각`이 같은 문장에 나오는 기업을 가까운 순으로 찾고 CSV로 저장합니다. 초보자용 설명은 [검색 과정 안내](docs/검색_과정_안내.md)를 참고하세요.

## 빠른 실행

```sh
uv sync
source .venv/bin/activate
python search_keyword_sentences.py
```

기본으로 2025년과 2026년 데이터를 검색해 상위 30개 기업을 저장합니다. 40개가 필요하면:

```sh
python search_keyword_sentences.py --count 40
```

결과는 `results/keyword_proximity_bulk_2025_2026.csv`에 저장되며 컬럼은 `회사명`, `문장` 두 개입니다. OpenDART API 키는 필요하지 않습니다.

## 데이터 사용

실행기는 다음 순서로 데이터를 찾습니다.

1. `--dataset`으로 지정한 ZIP, `val.tsv`, 또는 데이터 폴더
2. `data/opendart_xbrl_notes/`에 이미 있는 ZIP
3. `data/val.tsv` 또는 프로젝트 옆 `queryEngineDataset/val.tsv`
4. 위 자료가 하나도 없을 때 OpenDART 공개 ZIP 다운로드

기존 ZIP이나 `val.tsv`가 있으면 새 ZIP을 받지 않습니다. 일부 ZIP만 있으면 있는 파일만 검색하고 누락 묶음을 결과에 표시합니다. 다운로드를 막으려면 `--no-download`를 사용하세요.

```sh
python search_keyword_sentences.py --no-download
python search_keyword_sentences.py --dataset /path/to/val.tsv --count 40
python search_keyword_sentences.py --dataset /path/to/report.zip --report-year 2025
```

현재 공식 묶음에는 2026년 2분기 파일이 포함되어 있지 않습니다. 결과는 실제 검색에 사용한 파일 범위만 나타냅니다.

## 개발 확인

```sh
source .venv/bin/activate
python -m unittest discover -s tests -v
```
