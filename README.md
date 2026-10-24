# OpenDART 자기주식 소각 검색

`자기주식`과 `소각`이 같은 문장에 나오는 기업을 가까운 순으로 찾고 CSV로 저장합니다. 초보자용 설명은 [검색 과정 안내](docs/검색_과정_안내.md)를 참고하세요.

## 빠른 실행

```sh
uv sync
source .venv/bin/activate
python search_keyword_sentences.py
```

실행 시 프로젝트 루트에 `opendart_dataset/` 폴더를 만들고, 2025~2026년 공개 분기 ZIP을 순서대로 받습니다. 정상 ZIP은 재사용하며, 중단된 다운로드가 있으면 빠진 파일부터 다시 받습니다. 다운로드가 끝나면 분석을 이어서 실행합니다. ZIP 안의 `val.tsv`를 직접 읽으므로 별도 압축 해제는 하지 않습니다.

기본으로 사용 가능한 2025년 및 2026년 묶음을 검색해 조건에 맞는 전체 기업을 저장합니다. 2026년 2분기는 정상 다운로드 링크가 확인되지 않아 제외됩니다.

결과는 `results/keyword_proximity_bulk_2025_2026.csv`에 저장되며 컬럼은 `회사명`, `문장` 두 개입니다. OpenDART API 키는 필요하지 않습니다.

## 데이터 사용

실행기는 다음 순서로 데이터를 찾습니다.

1. `--dataset`으로 지정한 ZIP, `val.tsv`, 또는 데이터 폴더
2. `opendart_dataset/`에 이미 있는 공식 ZIP
3. `opendart_dataset/val.tsv`, `data/val.tsv`, 또는 프로젝트 옆 `queryEngineDataset/val.tsv`
4. 위 자료가 없거나 ZIP이 일부뿐이면 `opendart_dataset/`에 빠진 OpenDART 공개 ZIP을 순차 다운로드

`opendart_dataset/`에 정상 ZIP이 있으면 다시 받지 않습니다. 일부 ZIP만 있으면 누락 ZIP을 이어서 받습니다. 다운로드를 막으려면 `--no-download`를 사용하세요. 다른 환경에 스킬만 설치한 경우에도 현재 작업 폴더를 기준으로 `opendart_dataset/`과 `results/`를 만들기 때문에, 스킬 설치 경로에 쓰기 권한이 필요하지 않습니다.

```sh
python search_keyword_sentences.py --no-download
python search_keyword_sentences.py --dataset /path/to/val.tsv
python search_keyword_sentences.py --dataset /path/to/report.zip --report-year 2025
```

현재 공식 묶음에는 2026년 2분기 파일이 포함되어 있지 않습니다. 결과는 실제 검색에 사용한 파일 범위만 나타냅니다.

## 개발 확인

```sh
source .venv/bin/activate
python -m unittest discover -s tests -v
```
