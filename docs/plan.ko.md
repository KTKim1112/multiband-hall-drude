# 계획 — 어떤 기술로, 어떻게

Feature 001 · 2026-08-26

> **번역본입니다.** 정본은 `specs/001-multiband-drude/plan.md` 입니다.

`spec.md` 는 **무엇을** 만드는지 말하고 기술 이름을 쓰지 않는다. 이 문서는 그
기술을 전부 이름으로 부르며, 여기서 **무엇을 만들지는 다시 열지 않는다.**

---

## 1. 기술 선택과 이유

| 선택 | 이유 | 헌법 제IX조 정당화 |
| --- | --- | --- |
| Python 3.12 | 이미 설치되어 있고, 아래 생태계가 수치 물리 작업이 사는 곳 | 불필요 |
| `numpy` | 배열 연산. 물리 core가 허용하는 유일한 의존성 | 제I조 |
| `scipy.optimize.least_squares` | residual **벡터**를 받고, 상자형 bound를 지원하며, robust loss를 고를 수 있는 신뢰영역 최소제곱. FR-014·FR-035·FR-025 가 함께 요구하는 세 가지. research §5.2 | 불필요 |
| `pandas` | 데이터 표 읽기와 출력 표 쓰기. **두 모듈에만** 국한 | 국한이 곧 정당화. §2.2 |
| `matplotlib` | 그림 (FR-041) | 불필요 |
| `pytest` | 테스트 | 불필요 |
| 설정은 JSON | 의존성 없음, 손으로 편집 가능, 정확한 왕복이 되어 FR-037 이 실행을 재현 | YAML 검토 후 기각. 주석 문법 하나를 위해 의존성을 사는 것은 제IX조 위반 |
| 출력은 CSV | 유지보수자가 이미 쓰는 Origin, Igor, Excel, 모든 plot 도구에서 열림 | 불필요 |

**이 표를 개정하지 않고는 다른 것을 추가하지 않는다.**

---

## 2. 모듈 배치

### 2.1 물리 core — `mbfit/core/`

헌법 제I조: 이 모듈들은 `numpy` 와 표준 라이브러리만 import한다. 파일 접근 없음,
인자 처리 없음, 표 없음, 그림 없음.

| 모듈 | 담는 것 | 요구사항 |
| --- | --- | --- |
| `constants.py` | 기본 전하량 | research §1 |
| `units.py` | 경계 단위와 SI 사이의 모든 변환. **여기서만** | NR-004, 제V조 |
| `drude.py` | 전도도 텐서, 저항률 역변환, 그 역방향 | PM-001, PM-002 |
| `canonical.py` | 부호별 이동도 내림차순 정렬, 순서 변경 검출 | PM-003, FR-047 |
| `metrics.py` | 결정계수, RMSE, robust 채널 척도, 자기장 순서 잔차의 runs test 점수 | FR-020, FR-040, AC-007 |
| `residual.py` | residual 벡터 조립: 자기장 창에 의한 레코드 수용, 채널 선택, 공간 선택, 정규화, 가중치, 저자기장 강조 | FR-018 ~ FR-022, FR-049 |
| `penalties.py` | 온도 결합 penalty, 단조 penalty. 정규 순서 carrier 에 적용하고 선언된 절단선에서 끊는다 | FR-027 ~ FR-032, FR-052, FR-053, NR-003 |
| `errors.py` | 코드를 실은 예외 형 | 제IV조 |

**core는 온도가 파일에서 읽혔다는 것도, 파일이라는 것이 존재한다는 것도
모른다.** 배열을 받아 배열을 반환한다. 이것이 round trip(AC-008)을 입출력 없이
시험할 수 있게 하는 것이다.

### 2.2 나머지 — `mbfit/`

| 모듈 | 담는 것 | import 가능 |
| --- | --- | --- |
| `config.py` | 스키마, 기본값, 검증, `ResolvedConfig` | core |
| `dataio.py` | 데이터 읽기, 전처리, 온도별 묶기 | core, `pandas` |
| `fitting.py` | 세 가지 strategy, multistart, log 파라미터 벡터, 수렴한 도함수의 특이값 | core, `scipy` |
| `diagnostics.py` | `D_*` 규칙들 | core |
| `report.py` | 출력 파일과 그림 쓰기 | core, `pandas`, `matplotlib` |
| `messages.py` | 에러·진단 코드를 키로 한 한국어 문구 | 없음 |
| `cli.py` | 명령줄, FR-057 의 `--no-priors` 스위치. **문장이 보이는 유일한 곳** | 전부 |

`pandas` 는 `dataio.py` 와 `report.py` 에만 나타난다 — 표를 읽는 경계와 쓰는
경계, 두 곳뿐이다. 그 사이의 모든 것은 `numpy` 배열이거나 단순 구조다.
제IX조가 요구하는 정당화: `pandas` 의 group-by 와 CSV 처리는 **경계에서는**
값어치를 하고, **중간에서는** 배열의 shape을 라벨 뒤에 숨기는 부채다.

### 2.3 테스트 — `tests/`

| 파일 | 강제하는 것 |
| --- | --- |
| `test_core_purity.py` | 제I조. `core/` 모든 모듈의 import를 파싱 |
| `test_ascii.py` | 제IV조. `messages.py` 와 `cli.py` 밖의 비ASCII 거부 |
| `test_units.py` | NR-004. 각 변환과 그 역 |
| `test_drude_known.py` | research §2.3 의 K1 ~ K8 |
| `test_canonical.py` | PM-003, FR-047 |
| `test_residual.py` | FR-018 ~ FR-022 |
| `test_penalties.py` | FR-027 ~ FR-032, FR-052, FR-053, 불균등 간격 FR-031 포함 |
| `test_config.py` | 모든 `E_CONFIG_*` 코드 |
| `test_dataio.py` | 모든 `E_DATA_*` 코드, FR-005, FR-007 ~ FR-010 |
| `test_roundtrip.py` | **AC-008** |
| `test_strategies.py` | FR-023 ~ FR-026 |
| `test_diagnostics.py` | 모든 `D_*` 코드 |
| `test_legacy_agreement.py` | 새 코드가 `legacy/` 숫자를 재현하되 `rho_xy` 는 부호를 뒤집어서. §4 참조 |
| `test_cli.py` | `example_input.csv` 로 end-to-end |

---

## 3. 파라미터 벡터

carrier를 벡터로 바꾸는 방식을 한 곳에서 정하고, `fitting.py` 의 두 strategy가
모두 그것을 쓴다.

```text
단일 온도:   [log n_1, log mu_1, log n_2, log mu_2, ...]
global:      위 벡터를 온도 오름차순으로 이어 붙임.
             온도 i 는 [i*2N : (i+1)*2N] 구간을 차지
```

로그 공간은 NR-002. bound는 선언된 bound의 로그다. 출력 시, log-bound로부터
부동소수점 거리 이내인 성분은 **선언된 bound 그 자체**로 대체한다 (NR-006).

global strategy는 `2 N n_T` 개의 파라미터를 갖는다. carrier 4개, 온도 20개면
160개로, 차분 Jacobian을 쓰는 신뢰영역법이 충분히 다루는 규모다. 대가는
Jacobian 하나당 모델 평가 `161` 회다.

---

## 4. `legacy/` 를 어떻게 쓸 것인가

`legacy/` 의 프로토타입은 **알려진 결함 하나(Hall 부호, research §2.1)를 가진
정답지**다. `test_legacy_agreement.py` 는 그것을 실제로 실행하여 새 코드가
다음을 재현하도록 요구한다:

- `rho_xx` 를 상대 `1e-12` 로, 그대로;
- `rho_xy` 를 상대 `1e-12` 로, **부호를 뒤집은 뒤**.

이것은 **부호 수정이 의도적이고, 단 하나이며, 문서화된 변경**임을 못박는다.
다른 무언가가 함께 움직였을 가능성을 남기지 않는다. 이 테스트는 legacy 파일을
지울 때 함께 지우며, 그 전에는 지우지 않는다.

프로토타입은 현재 end-to-end로 실행할 수 없다. `README_KR.md` 가 지칭하는
설정 문서가 애초에 전달되지 않았기 때문이다. **함수들만** 사용한다.

---

## 5. 만드는 순서

아래에서 위로. 각 층이 다른 무엇도 그것에 의존하기 전에 알려진 정답에 대해
검증되도록. 자세한 것은 `tasks.md`. 본질적 제약은 하나다:
**어떤 strategy·진단·출력도 존재하기 전에 `test_roundtrip.py` 가 통과해야
한다.** 그것이 통과하지 않으면 이후의 모든 결과가 무의미하기 때문이다.

---

## 6. 일부러 만들지 않는 것

- 해석적 Jacobian 없음 (research §5.2).
- 병렬화 없음. **먼저 측정한다.**

### 6.1 2026-09-15 에 뒤집음: 웹 계층, 서버, 패키징된 빌드

이 절은 원래 *"그래픽 인터페이스 없음, 웹 계층 없음, 서버 없음"* 과 *"저장소에서
실행하는 것 이상의 패키징·설치 없음"* 도 적고 있었고, 유지보수자가 명령을 돌리고
CSV 를 읽는다는 것이 근거였습니다. 유지보수자에게는 둘 다 옳았고, 이 프로그램이
이제 갖게 된 사용자에게는 틀립니다. 제IX조는 의존성을 더하기 **전에** 그 근거를
여기 적으라고 요구하므로 적습니다.

**무엇이 바뀌었나.** 유지보수자가 Python 도 Node 도 관리자 권한도 없는 동료에게
이 프로그램을 건네기로 결정했습니다. 그들에게 명령줄과 CSV 폴더는 프로그램이
아닙니다. 형제 프로젝트 `nodeless-sc-gap` 이 그 사용자에게 통하는 길의 값을 이미
치르고 기록해 두었습니다. Python 프로세스가 띄우는 로컬 웹 페이지를 Windows 폴더
하나로 얼린 것입니다.

**무엇을 더하고, 각각이 왜 그 일을 하는 가장 단순한 것인가.**

| 의존성 | 더 작은 것으로는 왜 안 되나 |
| --- | --- |
| `fastapi` | 요청 본문을 검증하고 결과를 직렬화합니다. 대안은 둘 다 손으로 쓰는 것이고, 코드도 버그도 더 많습니다 |
| `uvicorn` | `fastapi` 가 올라가는 서버. loopback 전용, 사용자 한 명 |
| `python-multipart` | `fastapi` 가 업로드 파일을 받는 데 필요 |
| `pyinstaller` | Python, numpy, scipy 를 받는 사람이 돌릴 수 있는 폴더로 얼림 |
| 패키징 시점에 빌드되는 Vite + React 프런트엔드 | 화면이 온도마다의 판정과 그 근거, 열 매핑, 진행률이 있는 긴 작업을 보여줘야 합니다. 정적 페이지로는 그 상태를 정직하게 담을 수 없습니다 |

**일부러 넣지 않는 것.**

- **웹 계층은 `mbfit/` 밖**, `app/` 과 `frontend/` 에 둡니다. 라이브러리는
  제I조와 제IV조를 그대로 지킵니다. `mbfit/` 은 여전히 웹 프레임워크를 import
  하지 않고, `cli.py` 와 `messages.py` 밖에 한국어가 없습니다. 서버는 명령줄과
  같은 표현 계층입니다.
- **데이터베이스, 큐, 계정 없음.** 한 기계의 한 사용자. 작업은 dict 에 살고
  재시작하면 잊힙니다. `nodeless-sc-gap` 과 같습니다.
- **명령줄이 여전히 먼저입니다.** 페이지가 하는 모든 일은 페이지 없이도 닿을 수
  있고, 시험은 계속 라이브러리에 대고 돕니다.

**단일 파일이 아니라 폴더 하나.** `nodeless-sc-gap` 에서 측정했습니다. 단일 파일
빌드는 실행할 때마다 54 MB 를 임시 폴더에 풀고, 12.6 초 대 5.0 초로 늦게 뜨며,
dropper 의 모양이라 백신 휴리스틱에 걸립니다. 폴더 빌드를 zip 으로 보냅니다.
