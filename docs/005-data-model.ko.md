# data model 005 — feature 005 가 더하는 것

> **정본은 `specs/005-app/data-model.md` 입니다.** 이 문서는 그 번역이며,
> 둘이 어긋나면 영어 쪽이 맞습니다.
>
> feature 001 부터 004 까지의 data model 을 확장합니다. 서버는 명령줄처럼 표현
> 계층입니다. 프로세스보다 오래 사는 상태를 갖지 않습니다.
>
> *2026-09-19 개정:* 이 문단은 서버가 설정 문서에 설정을 더하지 않는다고도 적고
> 있었습니다. FR-112 가 확정된 답을 명령줄에서 재현할 수 있게 만드는데, 결합된
> 구간은 문서가 실어 나를 형태가 없었습니다. 그래서 `workflow.smooth_band` 를
> feature 004 의 data model 에 `workflow.fixed_counts` 옆에 선언합니다. 양쪽에서
> 닿을 수 있는 절차의 설정이며, 그것이 FR-107 이 요구하는 바입니다.

---

## 1. 요청과 응답

업로드와 두 다운로드를 빼면 모든 본문은 JSON 입니다. 모든 실패는 문장이 들어 있지
않은 `{"code": ..., "params": {...}}` 입니다 (FR-105).

| 메서드와 경로 | 본문 | 돌려주는 것 |
| --- | --- | --- |
| `GET /api/health` | | `{"version"}` |
| `POST /api/files` | 파일 하나 이상, multipart | `{"files": [미리보기, ...]}` |
| `POST /api/analyses` | 분석 요청 | `202`, `{"job_id"}` |
| `GET /api/jobs/{job_id}` | | 작업 |
| `POST /api/jobs/{job_id}/stop` | | `202`, `{"job_id"}` |
| `POST /api/jobs/{job_id}/precise` | `{"T_K"}` | `202`, 새 작업의 `{"job_id"}` |
| `POST /api/jobs/{job_id}/recount` | `{"temperatures", "holes", "electrons"}` | `202`, 새 작업의 `{"job_id"}` |
| `POST /api/jobs/{job_id}/smooth` | 끝난 재적합에 대고 `{"strength"}` | `202`, 새 작업의 `{"job_id"}` |
| `POST /api/jobs/{job_id}/confirm` | `{"fixed_counts", "smooth_band"}` | `202`, 새 작업의 `{"job_id"}` |
| `GET /api/jobs/{job_id}/report.html` | | FR-092 의 페이지 |
| `GET /api/jobs/{job_id}/tables.zip` | | FR-091 의 표 세 개 |

### 1.1 미리보기, 올린 파일마다 하나

```text
file_id          이 업로드의 불투명 식별자
name             보낸 그대로의 파일 이름
skipped_lines    머리글 위의 줄 수, FR-094
columns          머리글 이름, 순서대로
rows             처음 AC-034 개의 데이터 행, 문자열로
row_count        파일의 데이터 행 수
proposal
  B              열 이름 또는 null
  rhoxx          열 이름 또는 null
  rhoxy          열 이름 또는 null
  T_column       열 이름 또는 null
  T_from_name    이름에서 읽은 켈빈 온도, 또는 null
  field_unit     머리글에서 제안, 아무것도 안 적혀 있으면 "T"
  resistivity_unit   머리글에서 제안, 아무것도 안 적혀 있으면 "uOhm_cm"
temperatures     제안된 열 지정으로 본 이 파일의 온도들. 두 업로드가 같은 sweep 을
                 담는 것을 페이지가 보여 줄 수 있도록 (FR-096)
```

### 1.2 분석 요청

```text
files            파일마다 열 지정 하나
  file_id
  B, rhoxx, rhoxy          열 이름
  T_column                 열 이름, 또는 null
  T_K                      숫자, T_column 이 null 이면 필수
  field_unit               "T" | "mT" | "kOe" | "Oe"
  resistivity_unit         "uOhm_cm" | "mOhm_cm" | "Ohm_cm" | "uOhm_m" | "Ohm_m"
count            "data" | "peaks"; 생략하면 "data" (FR-099)
symmetrize_rhoxx         주지 않으면 false (FR-100)
antisymmetrize_rhoxy     주지 않으면 false (FR-100)
document         설정 문서, 또는 공급된 예비 모형을 쓰려면 null (FR-102)
```

테슬라와 마이크로옴 센티미터로의 변환 인수 (FR-095):

| 단위 | 인수 | | 단위 | 인수 |
| --- | --- | --- | --- | --- |
| `T` | `1` | | `uOhm_cm` | `1` |
| `mT` | `1e-3` | | `mOhm_cm` | `1e3` |
| `kOe` | `0.1` | | `Ohm_cm` | `1e6` |
| `Oe` | `1e-4` | | `uOhm_m` | `1e2` |
| | | | `Ohm_m` | `1e8` |

### 1.3 작업

```text
job_id
kind             "analysis" | "precise" | "recount" | "smooth" | "confirm"
state            "pending" | "running" | "succeeded" | "failed" | "stopped"
progress
  stage          "prepare" | "spectrum" | "temperature" | "search" |
                 "release" | "peaks" | "fixed" | "smooth" | "resample" |
                 "beyond" | "island" | "done"
  T_K, index, total, holes, electrons, iteration, done      해당하는 곳에서
error            실패했으면 {"code", "params"}, 아니면 null
result           성공했을 때, 또는 끝난 온도가 있는 채로 멈췄을 때
preliminary      잡음 수준을 공급한 carrier 집합 (FR-102)
```

분석 결과는 FR-092 의 보고서 payload 입니다 — 모든 온도의 판정, carrier, 후보,
곡선. 재적합 결과(FR-109)는 그 payload 의 항목 하나입니다. 읽는 사람이 고정한
개수로 다시 맞춘 그 온도를, 페이지가 이미 그릴 줄 아는 모양 그대로 돌려주며,
**혼자 답합니다.** FR-109 의 결합은 이미 끝난 재적합에 대고 따로 요청하므로, 느리거나
멈춰진 결합이 재적합을 붙들어 두는 일이 없습니다. 확정 결과는 분석 결과입니다.
확정은 절차를 다시 돌리는 것이기 때문입니다(FR-112). 정밀 점검 결과는 온도
하나입니다.

```text
T_K, resamples, block_length, seed, lower_bound
parameters       [{name, value, low, high, sigma}], 정준 순서
derived          같은 것, FR-061 의 파생량에 대해
```

---

## 2. 코드

서버 자신의 코드. data model 001 의 모든 `E_CONFIG_*` 와 `E_DATA_*` 는 그대로
통과합니다.

| 코드 | 파라미터 | 언제 |
| --- | --- | --- |
| `E_UPLOAD_EMPTY` | | 파일이 없거나 빈 파일뿐 |
| `E_UPLOAD_UNREADABLE` | `file` | 구분자로 나뉜 텍스트 표가 아님 |
| `E_UPLOAD_NO_TABLE` | `file` | 숫자 행이 뒤따르는 행이 없음 |
| `E_UPLOAD_SPREADSHEET` | `file` | 스프레드시트 파일. 텍스트로 저장해야 함, FR-096 |
| `E_FILE_UNKNOWN` | `file_id` | 서버가 갖고 있지 않은 업로드를 열 지정이 가리킴 |
| `E_MAPPING_INCOMPLETE` | `file`, `missing` | 필수 열이나 온도가 주어지지 않음 |
| `E_MAPPING_UNKNOWN_COLUMN` | `file`, `column` | 파일에 없는 열을 열 지정이 가리킴 |
| `E_MAPPING_BAD_UNIT` | `file`, `unit` | §1.2 목록 밖의 단위 |
| `E_TEMPERATURE_DUPLICATE` | `T_K`, `files` | FR-096 |
| `E_COUNT_RULE_UNKNOWN` | `count` | `data`, `peaks` 가 아닌 개수 규칙, FR-099 |
| `E_JOB_NOT_FOUND` | `job_id` | |
| `E_JOB_NOT_FINISHED` | `job_id` | 분석이 성공하기 전의 다운로드·정밀 점검·재적합 |
| `E_PRECISE_NO_ANSWER` | `T_K` | 재샘플링할 fit 이 없는 온도, FR-101 |
| `E_PRECISE_UNKNOWN_TEMPERATURE` | `T_K` | 분석에 없는 온도. 정밀 점검과 재적합 모두 |
| `E_RECOUNT_INVALID` | `holes`, `electrons`, `most` | carrier 가 하나도 없거나, AC-036 이 허용하는 것보다 많은 고정 개수, FR-109 |
| `E_SMOOTHING_TOO_FEW` | `given`, `needed` | 온도가 셋 미만인 구간에 결합을 요청함. 제약할 곡률이 없다. FR-109 |
| `E_SMOOTHING_UNKNOWN` | `smooth`, `known` | 제공되지 않는 결합 강도 |
| `E_SMOOTH_NO_BAND` | | 끝난 재적합이 아닌 작업에 대고 결합을 요청함, FR-109 |
| `E_BAND_COUNTS_DIFFER` | `counts` | sweep 들이 하나의 carrier 개수를 공유하지 않는 구간의 결합. 묶을 것이 없음, FR-109 |
| `E_BUDGET_EXPIRED` | `seconds` | AC-039 의 예산에서 포기된 결합 재적합 |
| `E_CONFIRM_EMPTY` | | 확정할 조정이 없는 확정 요청, FR-112 |
| `E_REQUEST_INVALID` | `fields` | 모양이 틀린 본문. 어디인지만, 왜인지를 말로 하지 않음 |
| `E_INTERNAL` | `detail` | 예상하지 못한 모든 것, 그래도 코드로 |

---

## 3. 서버가 무엇을 얼마나 오래 갖고 있는가

| 무엇 | 어디 | 언제까지 |
| --- | --- | --- |
| 올린 파일 | 메모리 | 프로세스가 끝날 때까지 |
| 작업과 그 결과 | 메모리, 최근 `32` 개까지 | 프로세스가 끝나거나, 33개 중 가장 오래된 것이 될 때까지 |
| 합친 표와 써 둔 표·페이지 | 작업마다 임시 디렉터리 | 프로세스가 끝날 때까지 |
| 확정된 답: 그 표들, 페이지, 설정 문서, 그리고 그것이 돌아간 합친 표 | 자기 작업의 임시 디렉터리 | 프로세스가 끝날 때까지 |

시스템의 임시 디렉터리 밖에는 아무것도 쓰지 않습니다.
