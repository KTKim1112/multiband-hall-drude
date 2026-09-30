# SDD Specification — Multiband Magnetotransport Fitting

## 1. System Goal

사용자가 제공한 `T, B, rho_xx, rho_xy` 데이터로 임의 개수의 electron/hole carrier를 갖는 multiband transport model을 fitting하고, 온도 의존 parameter와 fit-quality diagnostics를 재현 가능한 형태로 출력한다.

## 2. Functional Requirements

### FR-01 Input
- 단일 CSV에서 여러 온도를 읽을 수 있어야 한다.
- T/B/rho_xx/rho_xy column mapping은 configuration에서 지정 가능해야 한다.

### FR-02 Carrier topology
- electron/hole carrier 개수는 source code 수정 없이 configuration에서 바꿀 수 있어야 한다.
- 최소 1 carrier 이상을 허용한다.

### FR-03 Parameter specification
각 carrier에 대해 다음을 독립적으로 설정할 수 있어야 한다.
- density initial
- density lower/upper bound
- mobility initial
- mobility lower/upper bound

### FR-04 Fit channels
다음 세 모드를 제공한다.
- `both`
- `rhoxx`
- `rhoxy`

### FR-05 Fit space
- rho-space
- sigma-space
를 선택할 수 있어야 한다.

### FR-06 Temperature strategies
- `independent`
- `sequential`
- `global_smooth`
를 제공한다.

### FR-07 Temperature smoothing
- smoothing on/off
- density/mobility lambda independent control
- first-difference 또는 second-difference penalty
- carrier별 smoothing inclusion/exclusion
을 지원한다.

### FR-08 Optional monotonic prior
carrier별 density/mobility에 대해 none/increase/decrease prior를 지원한다.

### FR-09 Weighting
- rho_xx/rho_xy 상대 weight
- longitudinal low-field weight
를 지원한다.

### FR-10 Multistart
local minimum sensitivity를 줄이기 위해 random multistart를 지원한다.

### FR-11 Preprocessing
- Hall scale factor
- rho_xx symmetrization
- rho_xy antisymmetrization
을 선택 가능하게 한다.

### FR-12 Outputs
- 온도별 raw + fit + residual CSV
- parameter-vs-T CSV
- fit metric CSV
- plot
- resolved configuration
을 출력한다.

## 3. Numerical Requirements

### NR-01 Positive parameters
carrier density와 mobility는 양수이어야 한다.

### NR-02 Log-space optimization
수치 conditioning과 multiplicative scale consistency를 위해 density/mobility는 log-space에서 optimize한다.

### NR-03 Unit handling
- input density: cm^-3
- input mobility: cm^2/(V s)
- input/output rho: micro-ohm cm
- internal conductivity: S/m
을 사용한다.

### NR-04 Reproducibility
random multistart는 seed를 configuration으로 고정할 수 있어야 한다.

## 4. Physical Model Contract

각 carrier는 독립적인 classical Drude channel로 취급한다.

```text
sigma_xx,i = n_i e mu_i / [1 + (mu_i B)^2]
sigma_xy,i = s_i n_i e mu_i^2 B / [1 + (mu_i B)^2]
```

총 conductivity는 carrier contribution의 합이며 resistivity는 conductivity tensor inversion으로 계산한다.

## 5. Smoothness Contract

### First-order
인접 온도에서 `log(parameter)`의 변화량을 penalty한다.

### Second-order
`log(parameter)`의 temperature slope 변화량을 penalty한다.

Second-order를 기본 spike-suppression 방식으로 권장한다. 이유는 monotonic 또는 smooth trend 자체를 강하게 평탄화하지 않고 isolated jump를 억제하기 때문이다.

## 6. Acceptance / Validation Criteria — 권장 예

프로젝트별 수치는 반드시 사용자가 정해야 한다. 예:

- AC-01: `R2_rhoxx >= 0.995`
- AC-02: `R2_rhoxy >= 0.995`
- AC-03: fitted parameter가 hard bound의 0.5% 이내에 반복적으로 붙으면 warning
- AC-04: 인접 온도에서 density 또는 mobility가 factor 5 이상 jump하면 identifiability warning
- AC-05: initial-value sweep에서 서로 다른 parameter set이 동일한 R²를 만들면 non-unique warning
- AC-06: residual에 field-dependent systematic curvature가 남으면 model-mismatch warning

중요: AC 값은 물리적 사실이 아니라 project specification입니다.

## 7. Suggested Test Cases

### TC-01 One electron
synthetic 1-band data를 생성하고 원래 n, mu를 회복하는지 테스트.

### TC-02 2e + 2h
synthetic data에 대해 arbitrary carrier count 기능 테스트.

### TC-03 fit_mode
동일 데이터에서 both/rhoxx/rhoxy 세 모드가 정상 실행되는지 테스트.

### TC-04 bounds
true parameter를 bound 밖에 놓았을 때 boundary solution을 반환하는지 테스트.

### TC-05 sequential
이전 온도 fitted parameter가 다음 initial로 전달되는지 테스트.

### TC-06 global smoothing
한 온도의 initial value를 고의로 10배 틀리게 주고 second-order smoothing이 isolated spike를 억제하는지 테스트.

### TC-07 Hall scaling
raw rho_xy를 2배 만든 뒤 `rhoxy_scale=0.5`로 원래 parameter를 회복하는지 테스트.

### TC-08 sign convention
hall_polarity를 -1로 바꾸었을 때 Hall sign이 반전되는지 테스트.

## 8. Non-Goals / Model Limits

다음은 현재 version에서 모델링하지 않는다.

- field-dependent mobility
- anisotropic tau(k)
- explicit interband scattering matrix
- quantum correction
- effective-medium mixture
- mobility spectrum

이러한 효과가 필요하면 Drude parameter bounds를 더 강하게 거는 것이 아니라 별도의 model extension specification을 작성해야 한다.

## 9. Development Rule

새 fitting constraint를 추가할 때 다음을 반드시 기록한다.

1. 왜 필요한가?
2. hard constraint인가 soft prior인가?
3. 어떤 데이터/외부 측정이 근거인가?
4. fit quality를 얼마나 바꾸는가?
5. conclusion이 constraint 제거 후에도 유지되는가?

이 원칙은 “curve를 잘 맞추기 위해 물리적으로 임의의 constraint를 추가하는 것”을 방지하기 위한 핵심 SDD rule이다.
