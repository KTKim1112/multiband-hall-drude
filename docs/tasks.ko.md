# 작업 — 어떤 순서로, 그리고 넘어가기 전에 무엇이 성립해야 하는가

Feature 001 · 2026-08-26

> **번역본입니다.** 정본은 `specs/001-multiband-drude/tasks.md` 입니다.

모든 작업은 자신이 처리하는 요구사항을 명시한다. 앞 단계의 **gate**가 성립하기
전에는 다음 단계를 시작하지 않는다.

> **gate는 권고가 아니다.** gate가 없으면 "되는 것 같으니 넘어가자"가 반복되고,
> 결국 어디서 잘못됐는지 아무도 찾을 수 없게 된다.

---

## Phase 1 — 물리 core

여기서는 파일을 읽지도, 인자를 파싱하지도, 무엇을 그리지도 않는다.

| 작업 | 할 일 | 요구사항 |
| --- | --- | --- |
| T101 | `core/errors.py` — 안정적 코드와 기계 판독 상세를 실은 예외 형 하나 | 제IV조 |
| T102 | `core/constants.py` — 기본 전하량, 그것뿐 | research §1 |
| T103 | `core/units.py` — 모든 경계/SI 변환과 양방향 테스트 | NR-004, 제V조 |
| T104 | `core/drude.py` — 전도도 텐서, 저항률 역변환, 측정 저항률로부터 전도도, field polarity | PM-001, PM-002, NR-001 |
| T105 | `tests/test_drude_known.py` — research §2.3 의 K1 ~ K8, 각각 측정된 허용오차로 | PM-001, PM-002 |
| T106 | `core/canonical.py` — 부호별 이동도 내림차순 정렬, 순서 변경 보고 | PM-003, FR-047 |
| T107 | `core/metrics.py` — 결정계수, RMSE, 문서화된 대체 규칙을 갖춘 robust 채널 척도, runs test 점수 | FR-020, FR-040, AC-007 |
| T108 | `tests/test_core_purity.py` — `core/` 모든 모듈의 import를 파싱, `numpy` 와 표준 라이브러리 외에는 실패 | 제I조 |
| T109 | `tests/test_ascii.py` — `messages.py` 와 `cli.py` 밖의 비ASCII면 실패 | 제IV조, 제VIII조 |

> **Gate 1** — `pytest` 통과. 특히 K1 ~ K8. 이후의 모든 숫자가 여기에 기댄다.
> `test_core_purity.py` 와 `test_ascii.py` 는 **통과하기 전에 올바른 이유로
> 실패하는 것**을 한 번 확인한다: 각각에 대해 일부러 위반을 넣어 실패를
> 확인한 뒤 위반을 제거한다.

---

## Phase 2 — 설정과 데이터 수용

| 작업 | 할 일 | 요구사항 |
| --- | --- | --- |
| T201 | `config.py` — `data-model.md` §2 의 스키마. 모든 기본값을 채워 `ResolvedConfig` 를 만든다 | FR-003, FR-011, FR-013, FR-016, FR-018, FR-019, FR-021, FR-022, FR-026, FR-027, FR-028, FR-029, FR-030, FR-032, FR-033, FR-034, FR-035, AC-001 ~ AC-007 (AC-002 포함 전부) |
| T202 | 검증 — 모든 `E_CONFIG_*` 코드. 모르는 필드는 무시하지 않고 거부 | FR-012, FR-014, FR-015, FR-017 |
| T203 | `messages.py` — `data-model.md` §3 의 모든 코드에 대한 한국어 문구 | 제IV조, 제VIII조 |
| T204 | `dataio.py` — 표 읽기, 네 컬럼 매핑, 못 쓰는 레코드 버리고 세기, 온도별 묶기, 각 묶음을 자유 파라미터 수와 대조 | FR-001, FR-002, FR-004, FR-005, FR-006 |
| T205 | 전처리 — Hall scale, 대칭화, 반대칭화, 거울 보간 및 보간/부재 개수 | FR-007, FR-008, FR-009, FR-010 |
| T206 | `tests/test_config.py`, `tests/test_dataio.py` — 에러 코드마다 테스트 하나. **코드를 확인하고 문구는 결코 확인하지 않는다** | 제IV조 |

> **Gate 2** — `data-model.md` §3 의 모든 `E_CONFIG_*`, `E_DATA_*` 코드가 최소
> 하나의 테스트에서 발생하고, 소스가 발생시키는 모든 코드가 `data-model.md` 에
> 존재한다. **두 목록을 비교하는 테스트로 검사한다.**

---

## Phase 3 — 목적함수, 그리고 round trip

| 작업 | 할 일 | 요구사항 |
| --- | --- | --- |
| T301 | `fitting.py` — carrier를 log 파라미터 벡터로 싸고 푸는 것, log 공간의 bound, 출력 시 정확한 bound 값 | NR-001, NR-002, NR-006 |
| T302 | `core/residual.py` — 자기장 창에 의한 레코드 수용, 채널 선택, 공간 선택, robust 정규화, 채널 가중치, 저자기장 강조 | FR-018 ~ FR-022, FR-049 |
| T302b | 자기장 창은 **비교에서만** 레코드를 제외한다. 예측·출력·잔차는 여전히 모든 레코드를 덮고, fit 품질은 안쪽과 바깥쪽을 따로 계산한다 | FR-050, FR-051 |
| T303 | 단일 온도 solve + multistart: seed 고정, 모든 시작점 보존, 최적 채택, seed 기록 | FR-033 ~ FR-036, NR-005, 제VII조 |
| T304 | `tests/test_roundtrip.py` — 알려진 파라미터로 데이터를 생성하고, 그것을 되찾는다 | **AC-008** |

> **Gate 3 — 결정적인 관문.** `test_roundtrip.py` 가 단일 carrier 데이터의
> 생성 파라미터를 상대 `1e-6` 로, 2-carrier 데이터를 research §4.2 가 측정한
> 허용오차로 되찾는다. **이것이 통과하기 전에는 Phase 4~7 의 어떤 것도
> 시작하지 않는다.** 2배 인자, 뒤집힌 부호, 사라진 단위 변환은 다른 어떤
> 테스트에도 보이지 않기 때문이다.

---

## Phase 4 — 온도 strategy와 결합

| 작업 | 할 일 | 요구사항 |
| --- | --- | --- |
| T401 | Independent strategy | FR-023 |
| T402 | Sequential strategy — 한 온도의 결과가 다음을 seed | FR-024 |
| T403 | Global strategy — 모든 온도를 한 문제로. 어느 strategy를 썼는지 기록 | FR-025, FR-026 |
| T404 | `core/penalties.py` — `log p` 에 대한 결합, 1차·2차, carrier별 포함, 불균등 간격 보정 | FR-027 ~ FR-031, NR-003 |
| T405 | 단조 penalty. soft로, carrier별·양별 | FR-032 |
| T405b | 두 penalty 모두 정규 순서 carrier 에 작용하고, 선언된 절단선에서 끊겨 **어떤 항도 절단선을 넘지 않을 것** | FR-052, FR-053 |
| T405c | global 이 아닌 strategy 에서 결합/단조 penalty 를 요구하면 `E_CONFIG_COUPLING_WITHOUT_GLOBAL` 로 거부. sequential 은 seed 만 하고 그 외에는 아무것도 하지 않는다 | FR-024, FR-025 |
| T406 | 테스트: sequential seeding이 관측 가능할 것 / 고립된 이탈을 어느 차수든 결합이 억제할 것 / **로그가 온도에 선형인 파라미터를 2차는 보존하고 1차는 평탄화할 것** (둘을 가르는 사례) / FR-031 은 **두 간격이 한 계열에 섞인 경우** — 20 K 아래 2 K, 위 20 K — 에서 `log p` 의 온도 곡률이 일정한 파라미터가 두 구간에서 **같은 penalty 항**을 내야 할 것. 균등 계열을 다른 균등 계열로 바꾸는 것은 이를 시험하지 못하며, research §5.5 가 정정한 옛 수식도 통과시켰을 것 | FR-024, FR-029, FR-031 |

> **Gate 4** — `pytest` 통과, 그리고 **각 strategy를 차례로 선택한 상태에서
> Gate 3 이 여전히 통과**. **두 결합 차수를 가르는 테스트는 `order = 1` 에서
> 실패하고 `order = 2` 에서 통과해야 한다.** 그렇지 않으면 그 테스트는
> 주장하는 것을 시험하고 있지 않은 것이다.
>
> **2026-08-26 정정.** 그 요구는 T406 의 spike 억제 테스트를 두고 쓴 것인데,
> **그 테스트는 판별력이 없다**: 1차 penalty 도 고립된 이탈을 2차와 똑같이
> 억제하므로 두 차수 모두 통과하고, 차이에 대해 아무것도 증명하지 못한다.
> 둘을 가르는 것은 **추세**다. research §5.5 는 2차가 단조롭거나 매끄러운
> 추세를 평탄화하지 않고 통과시키는 반면 1차는 추세 자체를 벌한다고 말한다.
> 따라서 판별 사례는 **로그가 온도에 선형인 파라미터**다. 그때 2차 penalty 는
> 참값에서 정확히 0 이고 1차는 그렇지 않다. 두 테스트를 모두 두되,
> gate 는 두 번째 것만 진다.

---

## Phase 5 — 진단

| 작업 | 할 일 | 요구사항 |
| --- | --- | --- |
| T501 | `D_R2_BELOW`, `D_AT_BOUND` | FR-042, FR-043, AC-001, AC-002, AC-003 |
| T502 | `D_JUMP` 과 `D_LABEL_SWAP` 을 **함께** 평가하여, 이름표 교환이 물리적 도약으로 보고되지 않게 | FR-044, FR-047, AC-004 |
| T503 | `D_NON_UNIQUE` — 보존된 시작점들을 **정규화 후에만** 비교 | FR-045, AC-005, AC-006 |
| T504 | `D_RESIDUAL_STRUCTURE` | FR-046, AC-007 |
| T505 | `D_LOW_MU_B`, `D_MIRROR_ABSENT`, `D_RECORDS_DROPPED` | FR-005, FR-010 |
| T505b | `D_FIELD_RANGE_ACTIVE`, `D_EXCLUDED_MISMATCH` | FR-049, FR-050, FR-051, AC-009 |
| T506 | 모든 진단이 측정값·임계·출처 합격기준을 싣는다 | FR-048 |
| T507 | 수렴한 residual 도함수의 특이값에서 `D_ILL_CONDITIONED`. research §4.6 의 네 사례로 교정 | FR-055, AC-010 |
| T508 | `D_BOUND_OVERRIDE`, 그리고 `config.py` 의 온도별 bound 덮어쓰기 | FR-054 |
| T509 | `D_PRIORS_ACTIVE`, `D_PRIORS_DISABLED`. 작동 중인 soft prior 하나당 한 항목, 강도와 범위 포함 | FR-056, FR-057 |

> **Gate 5 조건수 확인** — `D_ILL_CONDITIONED` 가 research §4.6 을 재현한다:
> 기준 데이터에서는 research 가 기록한 값, 14 T 합성 사례에서 `4.0e2`, 3 T 사례에서 `5.2e3`,
> 같은 부호 carrier 두 개에 이동도 6000 과 6100 을 준 경우 `3.6e9`. 앞의 둘은
> AC-010 을 통과해야 하고 **뒤의 둘은 실패해야 한다.** 파라미터 정확도를 아는
> 사례들이기 때문이다.
>
> **Gate 5 추가 조건** — 자기장 창은 **기능이지 이 프로젝트가 쓰는 설정이
> 아니다**. research §6 의 C7 이 이를 측정하고 기준 데이터에는 적용하지
> 않기로 결정했다. 따라서 테스트는 **그 결정을 낳은 측정 자체**를 확인한다.
> 기준 데이터를 창 6 T 로 닫고 fitting하면 `D_FIELD_RANGE_ACTIVE` 와
> `D_EXCLUDED_MISMATCH` 가 발생하고, 파라미터가 C7 이 기록한 만큼 달라지며,
> 보지 않은 6~9 T 를 `R2 = 0.757` 로 예측한다 (전구간 fit 은 `0.959`).
> **비용이 테스트로 못박힌 기능은 실수로 켜질 수 없다.**
>
> **Gate 5** — 모든 `D_*` 코드가, 그것을 발동시키도록 만든 데이터로 된 최소
> 하나의 테스트에서 발생한다. 그리고 **research §4.3 의 2e+2h 사례를 3 T에서
> 돌렸을 때 두 저이동도 carrier에 대해 `D_LOW_MU_B` 가 발생하고
> `D_NON_UNIQUE` 는 발생하지 않는다.** 그 조합이 이 프로젝트가 보고하려고
> 존재하는 바로 그 측정이므로, 직접 확인한다.

---

## Phase 6 — 출력과 명령줄

| 작업 | 할 일 | 요구사항 |
| --- | --- | --- |
| T601 | 온도별 표, 선언 순서와 정규 순서를 함께 담은 파라미터 표, 지표 표, 특이값과 조건수 | FR-038, FR-039, FR-040, FR-055 |
| T602 | 온도별·채널별 그림, 파라미터 대 온도 그림 | FR-041 |
| T603 | `diagnostics.csv`, 온도별 모든 시작점 파일 | FR-036, FR-042 |
| T604 | `resolved_config.json` — 완전하게, seed 포함, 다시 넣으면 실행이 재현되게 | FR-037, NR-005 |
| T605 | `cli.py` — 문장이 나타나는 유일한 곳. 한국어, 코드를 키로. `--no-priors` 를 싣고, 선언된 soft prior 를 덮어쓴 사실을 기록 | 제IV조, 제VIII조, FR-057 |
| T606 | `tests/test_cli.py` — `example_input.csv` 로 end-to-end. 그 다음 나온 `resolved_config.json` 을 되먹여 **동일한 숫자**를 요구 | NR-005 |

> **Gate 6** — `example_input.csv` 실행이 `data-model.md` §4 의 모든 파일을
> 쓰고, 방출된 `resolved_config.json` 으로 다시 실행하면 모든 숫자가 정확히
> 재현된다. 그리고 `--no-priors` 로 만든 실행은 **스위치 없이** 자기 설정으로
> 재현된다. 이것이 FR-037 이 "선언된 값" 이 아니라 "작동한 값" 을 기록함을
> 확인하는 테스트다.

---

## Phase 7 — 정답지 대조, 예제, 문서

| 작업 | 할 일 | 요구사항 |
| --- | --- | --- |
| T701 | 예제 설정 2종: `example_input.csv` 용 2-carrier, 그리고 research §2.4 기준 데이터용 2-hole 2-electron | quickstart |
| T702 | `tests/test_legacy_agreement.py` — `rho_xx` 상대 `1e-12`, `rho_xy` 는 부호를 뒤집은 뒤 `1e-12` | plan §4 |
| T703 | `quickstart.md` — 실제로 실행해서 검증 | |
| T704 | `docs/` — 한국어 walkthrough. 제VIII조 예외 | 제VIII조 |
| T705 | `tests/test_reference_fit.py` — **K9**. research §2.4 기준 데이터를 PM-001 아래 2-hole 2-electron 으로 fitting하여, 거기 기록된 전역 최적해를 **모든 시작점에서** carrier별 1 % 이내로 요구 | PM-001, PM-003, FR-045, FR-046 |
| T706 | 기준 데이터를 수용 형식으로 준비: 원 파일에 온도 컬럼이 없으므로 온도를 붙인 파생 표를 `tests/data/` 에 쓰고, 그 변환을 기록 | FR-001, FR-002 |

> **Gate 7** — `test_legacy_agreement.py` 통과. 프로토타입과 새 코드 사이에
> **수치적으로 의미 있는 변경이 research §2.1 의 수정 하나뿐**임을 확인한다.
> 그리고 `test_reference_fit.py` 통과. 기준 데이터의 두 채널에 대해
> `D_RESIDUAL_STRUCTURE` 는 발생하고 `D_NON_UNIQUE` 는 발생하지 않는다 —
> research §4.5 가 각각 있음/없음으로 측정한 바로 그 두 진단이다.

---

## 요구사항 커버리지

읽어서가 아니라 **기계적으로** 확인한다. `tests/test_traceability.py` 가
`spec.md` 에 정의된 모든 `FR-`, `NR-`, `PM-`, `AC-` 식별자를 뽑아 이 파일에
없는 것이 있으면 실패한다. 이 테스트는 Phase 1 에서 작성하며, **작업 없이
요구사항이 추가되면 가장 먼저 깨지는 것**이다.
