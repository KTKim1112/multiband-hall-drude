# 자료 모형 — 구조, 설정 문서, 에러 코드

Feature 001 · 2026-08-26

> **번역본입니다.** 정본은 `specs/001-multiband-drude/data-model.md` 입니다.

---

## 1. 구조

언어 문법이 아니라 **내용**으로 기술한다. 필드 이름은 소스에서 쓸 이름이다.

### 1.1 `CarrierSpec` — 선언된 carrier 하나

| 필드 | 형 | 제약 | 요구사항 |
| --- | --- | --- | --- |
| `name` | 문자열 | 비어 있지 않고, 실행 내에서 유일 | FR-012 |
| `kind` | `electron` 또는 `hole` | | FR-012 |
| `n_init_cm3`, `n_min_cm3`, `n_max_cm3` | 수 | `0 < min <= init <= max` | FR-014, FR-015 |
| `mu_init_cm2Vs`, `mu_min_cm2Vs`, `mu_max_cm2Vs` | 수 | `0 < min <= init <= max` | FR-014, FR-015 |
| `smooth_density`, `smooth_mobility` | 참/거짓 | | FR-030 |
| `monotonic_density`, `monotonic_mobility` | `none`, `increase`, `decrease` | | FR-032 |

저장하지 않고 유도하는 것: `sign` = electron이면 `-1`, hole이면 `+1`.
모든 수치 필드가 이름에 단위를 싣는 이유는 헌법 제V조다.

### 1.2 `ResolvedConfig` — 기본값이 채워진 뒤의 설정

실행이 실제로 사용한 모든 값. 사용자가 쓰지 않은 기본값과 실제로 뽑힌 seed를
포함한다. 그대로 기록되며(FR-037), 다시 넣으면 실행이 비트 단위로 재현된다
(NR-005). 내용은 §2.

### 1.3 `TemperatureGroup` — 자기장 sweep 하나

| 필드 | 뜻 |
| --- | --- |
| `T_K` | 이 묶음의 온도 |
| `B_T` | 자기장 값들, 오름차순 |
| `rhoxx_uohmcm`, `rhoxy_uohmcm` | 전처리 후 측정값 |
| `in_fit_window` | 비교에 들어가면 참, FR-049 가 제외했으면 거짓. **제외된 레코드는 묶음에 그대로 남는다.** 삭제하지 않는다 (FR-049, FR-050) |
| `n_records_dropped` | FR-005 로 버린 레코드 수 |
| `n_mirror_interpolated`, `n_mirror_absent` | FR-010 의 각 경우 개수 |

### 1.4 `StartResult` — 시작점 하나의 결과

| 필드 | 뜻 | 요구사항 |
| --- | --- | --- |
| `start_index` | 0 은 선언된 초기값, 나머지는 섭동된 것 | FR-033 |
| `params` | fit된 밀도와 이동도, 경계 단위로 | |
| `cost` | 도달한 목적함수 값 | |
| `converged` | 최적화기가 성공을 보고했는지 | |

**최적 하나가 아니라 전부 보관한다** (FR-036). 그렇지 않으면 FR-045 가 비교할
대상이 없다.

### 1.5 `TemperatureFit` — 한 온도에서의 답

| 필드 | 뜻 | 요구사항 |
| --- | --- | --- |
| `T_K` | | |
| `params` | 채택된 최적해, 경계 단위 | FR-039 |
| `params_canonical` | 같은 값을 부호별 이동도 내림차순으로 정렬 | research §4.4 |
| `starts` | 모든 `StartResult` | FR-036 |
| `channel_scales` | 각 채널에 실제 적용된 정규화 | research §5.4 |
| `r2_rhoxx`, `r2_rhoxy`, `rmse_rhoxx`, `rmse_rhoxy` | fit 창 안쪽에 대해 | FR-040 |
| `r2_outside`, `rmse_outside` | FR-049 가 제외한 레코드에 대한 같은 값. 제외가 없으면 없음 | FR-051 |
| `singular_values`, `condition_number` | 해에서의 residual 도함수의 특이값과 그 비. 로그 파라미터 기준 | FR-055 |
| `at_bound` | 어떤 파라미터가 어느 bound에 붙었는지 | FR-043 |

### 1.6 `Diagnostic` — 검출된 위반 하나

헌법 제VI조는 결과가 위반 사항을 달고 다닐 것을, FR-048 은 각 진단이 무엇을
측정했고 임계가 어디서 왔는지 밝힐 것을 요구한다.

| 필드 | 뜻 |
| --- | --- |
| `code` | 안정적 식별자, §3.4 |
| `severity` | `warning` 또는 `note` |
| `where` | 해당되는 온도, carrier, 양 |
| `measured` | 발동시킨 숫자 |
| `threshold` | 넘어선 숫자 |
| `threshold_source` | 어느 합격 기준인지, 예: `AC-004` |

**여기에는 사람이 읽을 문장이 없다.** 헌법 제IV조: 한국어 문구는 `code` 를 키로
하여 표현 계층에 있다.

### 1.7 `RunResult` — 실행이 만들어 낸 전부

`ResolvedConfig`, 온도별 `TemperatureFit`, 모든 `Diagnostic`, 소요 시간, 사용한
seed (헌법 제VII조).

---

## 2. 설정 문서

사용자가 제공하는 문서 하나. **모르는 필드는 무시하지 않고 거부**한다.
옵션 이름의 오타가 기본값을 조용히 살려 두는 일이 없도록 하기 위함이다.
`carriers` 와 `columns` 를 제외한 모든 필드에 기본값이 있다.

```text
schema_version            문자열, "1.0"

_run                      프로그램이 쓰고 결코 읽지 않는다.        FR-037
                          출처 정보: 실행한 strategy, 온도들,
                          seed, 조건수. 방출된 문서가 그대로
                          다시 들어갈 수 있도록 입력에서는
                          받아들이고 무시한다

columns                   데이터에 나타나는 네 이름
  T, B, rhoxx, rhoxy                                          FR-003

model
  hall_polarity           +1 또는 -1, 기본 +1                 PM-002

preprocess
  rhoxy_scale             수, 기본 1.0                        FR-007
  symmetrize_rhoxx        기본 false                          FR-008
  antisymmetrize_rhoxy    기본 false                          FR-009
  mirror_interpolate      기본 true                           FR-010
  mirror_tolerance_T      기본 1e-9. 어떤 자기장을 다른
                          자기장의 정확한 거울로 볼지

carriers                  목록, 최소 1개                      FR-011
  name, kind
  density   { init, min, max }                                FR-014
  mobility  { init, min, max }                                FR-014
  smooth_density, smooth_mobility        기본 true            FR-030
  monotonic_density, monotonic_mobility  기본 "none"          FR-032

initial_by_temperature    선택, 온도를 키로                   FR-016
  <T> : { <carrier 이름> : { density, mobility } }

overrides_by_temperature  선택, 온도를 키로                   FR-054
  <T> : { <carrier 이름> : { density  { init, min, max },
                             mobility { init, min, max } } }
                          어느 항목이든 생략 가능. 지정된 것
                          하나하나가 D_BOUND_OVERRIDE 발생

optimization
  fit_mode                "both" | "rhoxx" | "rhoxy"          FR-018
  fit_space               "rho" | "sigma"                     FR-019
  weight_rhoxx            기본 1.0                            FR-021
  weight_rhoxy            기본 1.0                            FR-021
  low_field_weight                                            FR-022
    enabled               기본 false
    alpha                 기본 5.0
    B0_T                  기본 1.0
  fit_field_range                                             FR-049
    enabled               기본 false
    abs_min_T             기본 0.0
    abs_max_T             기본 null. 상한 없음을 뜻한다.
                          JSON 에 무한대가 없고, resolved
                          문서는 왕복해야 하기 때문
  temperature_strategy    "independent" | "sequential"
                          | "global_smooth"                   FR-023~26
  multi_start             정수 >= 1, 기본 8                   FR-033
  multi_start_log_sigma   기본 0.25                           FR-034
  random_seed             정수, 기본 12345                    NR-005
  loss                    "linear" | "soft_l1" | "huber"
                          | "cauchy" | "arctan", 기본
                          "linear"                            FR-035
  f_scale                 기본 1.0                            FR-035
  max_nfev, ftol, xtol, gtol   최적화기 한계

smoothing                                                     FR-027~31
  enabled                 기본 false. temperature_strategy
                          가 global_smooth 여야 함     FR-024, FR-025
  order                   1 또는 2, 기본 2                    FR-029
  lambda_density          기본 0.0                            FR-028
  lambda_mobility         기본 0.0                            FR-028
  breaks_K                온도 목록, 기본 빈 목록.          FR-053
                          어떤 penalty 항도 절단선을 넘지 않음

monotonic_penalty                                             FR-032
  enabled                 기본 false
  lambda                  기본 10.0

acceptance                                                    spec §7
  r2_rhoxx_min            기본 0.995                          AC-001
  r2_rhoxy_min            기본 0.995                          AC-002
  bound_fraction          기본 0.005                          AC-003
  jump_factor             기본 5.0                            AC-004
  cost_equivalence        기본 0.01                           AC-005
  parameter_difference    기본 0.20                           AC-006
  residual_runs_z         기본 -3.0                           AC-007
  excluded_rms_ratio      기본 3.0                            AC-009
  condition_number_max    기본 1000.0                         AC-010

output
  make_plots              기본 true                           FR-041
  plot_dpi                기본 180
```

명령줄의 `--no-priors` 는 문서가 무엇을 선언했든 `smoothing.enabled`,
`monotonic_penalty.enabled`, `low_field_weight.enabled` 를 false 로,
`optimization.loss` 를 `linear` 로 만든다 (FR-057). 방출되는
`resolved_config.json` 은 **실제로 작동한 값**을 담으므로, 그것을 되먹이면
스위치 없이 같은 실행이 재현된다.

**기본값은 아무것도 하지 않도록 골랐다.** `smoothing.enabled`,
`monotonic_penalty`, `low_field_weight` 는 전부 꺼짐이고, 두 smoothing 강도는
모두 0이다. carrier와 columns만 선언한 사용자는 권장 workflow의 **stage A —
제약 없는 진단 fit** 을 얻는다. 그것이 정직한 출발점이다. 이들 중 무엇이든
켜는 순간 헌법 제X조가 적용된다.

---

## 3. 에러 코드

헌법 제IV조: 함수는 실패를 **코드**로 알리고, 결코 문장으로 알리지 않는다.
테스트는 코드를 확인한다. 한국어 문구는 코드를 키로 표현 계층에 있으며,
테스트를 건드리지 않고 다시 쓸 수 있다.

### 3.1 설정 — `E_CONFIG_*`

| 코드 | 발생 조건 | 요구사항 |
| --- | --- | --- |
| `E_CONFIG_UNREADABLE` | 문서를 파싱할 수 없음 | |
| `E_CONFIG_SCHEMA_VERSION` | `schema_version` 이 없거나 지원되지 않음 | |
| `E_CONFIG_UNKNOWN_FIELD` | §2 에 없는 필드 이름 | |
| `E_CONFIG_MISSING_FIELD` | `columns` 또는 `carriers` 없음 | FR-003, FR-011 |
| `E_CONFIG_BAD_VALUE` | 값이 허용 집합/범위를 벗어남 | |
| `E_CONFIG_NO_CARRIERS` | carrier 목록이 비어 있음 | FR-011 |
| `E_CONFIG_DUPLICATE_CARRIER` | 두 carrier가 이름을 공유 | FR-012 |
| `E_CONFIG_BAD_CARRIER_KIND` | `kind` 가 electron도 hole도 아님 | FR-012 |
| `E_CONFIG_BOUNDS_INVALID` | `min <= 0` 이거나 `min > max` | NR-001, FR-014 |
| `E_CONFIG_INIT_OUT_OF_BOUNDS` | 초기값이 bounds 밖 | FR-015 |
| `E_CONFIG_EMPTY_FIELD_WINDOW` | FR-049 의 범위가 어떤 온도 묶음에서 레코드를 하나도 남기지 않음 | FR-049 |
| `E_CONFIG_COUPLING_WITHOUT_GLOBAL` | global 이 아닌 strategy 에서 결합/단조 penalty 를 켰음 | FR-024, FR-025 |
| `E_CONFIG_BREAK_OUTSIDE_RANGE` | 선언된 결합 절단선이 존재하는 온도 범위 밖 | FR-053 |
| `E_CONFIG_UNKNOWN_CARRIER` | `initial_by_temperature` 가 선언되지 않은 carrier를 지칭 | FR-016 |

### 3.2 데이터 — `E_DATA_*`

| 코드 | 발생 조건 | 요구사항 |
| --- | --- | --- |
| `E_DATA_UNREADABLE` | 데이터를 읽을 수 없음 | |
| `E_DATA_MISSING_COLUMN` | 선언된 컬럼 이름이 없음. **없는 이름을 모두 나열** | FR-004 |
| `E_DATA_EMPTY` | 쓸 수 있는 레코드가 하나도 남지 않음 | FR-005 |
| `E_DATA_UNDERDETERMINED` | 어떤 온도 묶음의 레코드가 자유 파라미터보다 적음 | FR-006 |

### 3.3 Fitting — `E_FIT_*`

| 코드 | 발생 조건 |
| --- | --- |
| `E_FIT_NO_START` | 모든 시작점이 실패 |
| `E_FIT_SINGULAR` | `sigma_xx^2 + sigma_xy^2` 가 0에 도달하여 텐서를 역변환할 수 없음 |

### 3.4 진단 — `D_*`

실패가 아니다. `RunResult` 에 실려(헌법 제VI조) 보고서에 나열된다.

| 코드 | 뜻 | 임계 | 요구사항 |
| --- | --- | --- | --- |
| `D_R2_BELOW` | 채널이 합격 기준에 미달 | AC-001, AC-002 | FR-042 |
| `D_AT_BOUND` | 파라미터가 bound에 붙음 | AC-003 | FR-043 |
| `D_JUMP` | 인접 온도 사이에서 파라미터가 도약 | AC-004 | FR-044 |
| `D_NON_UNIQUE` | 동등한 cost의 서로 다른 정규화 해들 | AC-005, AC-006 | FR-045 |
| `D_RESIDUAL_STRUCTURE` | residual이 자기장에 대한 구조를 유지 (runs test) | AC-007 | FR-046 |
| `D_LABEL_SWAP` | 인접 온도 사이에서 정규 순서가 바뀜 | 없음 | FR-047 |
| `D_MIRROR_ABSENT` | 대칭화가 거울 레코드를 찾지 못함 | 없음 | FR-010 |
| `D_RECORDS_DROPPED` | 수용 단계에서 레코드가 버려짐 | 없음 | FR-005 |
| `D_LOW_MU_B` | fit된 carrier의 `mu B` 가 측정 범위 전체에서 1 미만이어서 research §4.3 이 그 carrier에 적용됨 | `1` | FR-048 |
| `D_EXCLUDED_MISMATCH` | FR-049 작동 중, 창 바깥 잔차가 안쪽 잔차를 허용 배율 이상으로 초과 | AC-009 | FR-051 |
| `D_FIELD_RANGE_ACTIVE` | 자기장 범위 제한이 작동했음. 경계와 제외된 레코드 수를 밝힌다 | 없음 | FR-049, FR-050 |
| `D_ILL_CONDITIONED` | residual 도함수의 최대/최소 특이값 비가 허용값 초과 | AC-010 | FR-055 |
| `D_BOUND_OVERRIDE` | 한 온도에서 bound 나 초기값을 덮어썼음. 기본값과 덮어쓴 값을 밝힌다 | 없음 | FR-054 |
| `D_PRIORS_ACTIVE` | 작동 중인 soft prior 하나당 한 항목. 이름·강도·적용 범위를 밝힌다. soft prior 가 하나도 작동하지 않을 때만 없다 | 없음 | FR-056 |
| `D_PRIORS_DISABLED` | FR-057 스위치를 썼음. 침묵시킨 prior 와 각각의 선언값을 나열한다 | 없음 | FR-057 |

`D_LOW_MU_B` 는 받으신 명세서에 없다. research §4.3 이 **바로 그런 carrier에서
R² 가 0.9995 를 넘은 채로 35 % 오차**를 측정했기 때문에 추가했다. 그리고 이것은
답을 신뢰하기 **전에** 평가할 수 있는 유일한 진단이다 (나머지는 fit 결과가
나온 뒤에야 판정할 수 있다).

---

## 4. 출력 파일

| 파일 | 내용 | 요구사항 |
| --- | --- | --- |
| `resolved_config.json` | §1.2 | FR-037 |
| `<T>K_fit.csv` | 자기장, 두 채널의 측정·fit·residual, 두 공간 모두 | FR-038 |
| `fit_parameters_vs_T.csv` | 온도별 carrier별 밀도와 이동도. 선언 순서와 정규 순서를 나란히 | FR-039 |
| `fit_metrics_vs_T.csv` | 온도별 채널별 R² 와 RMSE | FR-040 |
| `<T>K_rhoxx.png`, `<T>K_rhoxy.png`, `parameters_vs_T.png` | | FR-041 |
| `diagnostics.csv` | 모든 `Diagnostic` 을 한 행씩, 임계와 출처와 함께 | FR-042, FR-048 |
| `multistart_<T>K.csv` | 모든 `StartResult` | FR-036 |
