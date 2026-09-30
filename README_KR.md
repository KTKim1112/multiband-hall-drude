# Multiband Magnetotransport Fitter — 상세 설명서

## 1. 목적

이 프로그램은 자기수송(magnetotransport) 데이터셋

- 온도 `T`
- 자기장 `B`
- longitudinal resistivity `rho_xx`
- Hall resistivity `rho_xy`

를 입력으로 받아, 임의 개수의 electron carrier와 hole carrier로 구성된 classical multiband Drude 모델을 피팅하기 위한 범용 Python 프로그램입니다.

이 버전은 특히 **Spec-Driven Development(SDD)** 에서 요구사항을 명시적으로 분리할 수 있도록 설계했습니다. 데이터 형식, carrier 구성, 각 carrier의 초기값 및 bounds, 어떤 채널을 피팅할지, 온도별 피팅 전략, smoothing 강도, monotonicity, weighting 등을 모두 JSON configuration으로 외부화했습니다.

핵심 원칙은 다음과 같습니다.

1. **모델 코드와 실험별 설정을 분리**합니다.
2. carrier 개수는 코드에 고정하지 않습니다.
3. density와 mobility의 initial value 및 bounds를 carrier별로 설정합니다.
4. `rho_xx + rho_xy`, `rho_xx only`, `rho_xy only`를 선택할 수 있습니다.
5. 각 온도를 독립적으로 피팅하거나, 직전 온도 결과를 초기값으로 사용하거나, 모든 온도를 동시에 fitting하면서 temperature smoothness penalty를 줄 수 있습니다.
6. 출력에는 fitted curve, residual, parameter-vs-T, R², RMSE를 포함합니다.
7. 실제 피팅에서는 density와 mobility의 scale 차이가 매우 크기 때문에 **log-parameter space**에서 optimization합니다.

---

## 2. 실행 방법

```bash
pip install -r requirements.txt
python multiband_transport_fitter.py \
    --data your_data.csv \
    --config example_config_2e2h.json \
    --out results
```

`results/` 안에는 온도별 fitted CSV, plot, parameter summary, metric summary, 실제 사용한 resolved config가 생성됩니다.

---

## 3. 입력 데이터 형식

가장 기본적인 CSV 형식은 다음과 같습니다.

```text
T(K),B(T),rhoxx(microohm cm),rhoxy(microohm cm)
5,-9.0,15.2,2.8
5,-8.9,15.1,2.7
...
10,-9.0,...,...
```

한 파일 안에 여러 온도의 데이터가 들어가는 방식을 기본으로 합니다.

실제 column 이름이 다르면 config의 `columns`만 변경하면 됩니다.

```json
"columns": {
  "T": "Temperature",
  "B": "Field",
  "rhoxx": "Rxx",
  "rhoxy": "Rxy"
}
```

---

## 4. 물리 모델

각 carrier `i`에 대해 다음을 정의합니다.

- `n_i`: carrier density [cm^-3]
- `mu_i`: mobility [cm^2/(V s)]
- `s_i`: Hall sign
  - electron: `-1`
  - hole: `+1`

프로그램 내부에서는 SI 단위로 변환한 뒤 다음 conductivity tensor를 계산합니다.

### 4.1 Longitudinal conductivity

```text
sigma_xx(B) = Sum_i [ n_i e mu_i / (1 + (mu_i B)^2) ]
```

### 4.2 Hall conductivity

```text
sigma_xy(B) = Sum_i [ s_i n_i e mu_i^2 B / (1 + (mu_i B)^2) ]
```

### 4.3 Conductivity -> resistivity tensor inversion

```text
rho_xx =  sigma_xx / (sigma_xx^2 + sigma_xy^2)
rho_xy = -sigma_xy / (sigma_xx^2 + sigma_xy^2)
```

Hall wiring convention이 반대인 실험에서는 `model.hall_polarity`를 `-1`로 바꿀 수 있습니다.

---

## 5. carrier 개수 설정

carrier 개수는 제한되지 않습니다. 예를 들어 2 electron + 2 hole이면 config에 carrier 4개를 정의합니다.

```json
"carriers": [
  {
    "name": "e1",
    "kind": "electron",
    "density": {"init": 1e19, "min": 1e16, "max": 1e22},
    "mobility": {"init": 6000, "min": 1, "max": 50000}
  },
  ...
]
```

2 electron + 1 hole로 하고 싶으면 `h2` 항목을 제거하면 됩니다. 3 electron + 2 hole도 동일하게 항목을 추가하면 됩니다.

즉 **band 수는 Python source code를 수정하지 않고 config만 수정해서 변경**합니다.

---

## 6. 초기값과 범위(bounds)

각 carrier별로 density와 mobility에 대해 세 값을 정합니다.

```json
"density": {
  "init": 1e19,
  "min": 1e16,
  "max": 1e22
}
```

- `init`: optimizer 시작점
- `min`: hard lower bound
- `max`: hard upper bound

mobility도 동일합니다.

### 왜 bounds가 중요한가?

multiband transport는 매우 ill-conditioned한 inverse problem입니다. 특히 저자기장에서

```text
sigma_xx ~ Sum(n_i mu_i)
sigma_xy ~ B Sum(s_i n_i mu_i^2)
```

이므로 서로 다른 `n_i`, `mu_i` 조합이 비슷한 curve를 만들 수 있습니다. 따라서 좋은 curve fitting이 반드시 unique한 carrier decomposition을 의미하지 않습니다.

bounds는 단순한 numerical trick이 아니라 **물리적으로 허용할 parameter domain을 specification으로 선언하는 역할**을 합니다.

---

## 7. 특정 온도별 초기값 지정

기본 initial value와 별도로 특정 온도에서 직접 초기값을 줄 수도 있습니다.

```json
"initial_by_temperature": {
  "5": {
    "e1": {"density": 1.5e19, "mobility": 6000},
    "e2": {"density": 9.0e20, "mobility": 500},
    "h1": {"density": 9.0e18, "mobility": 6100},
    "h2": {"density": 1.0e21, "mobility": 265}
  }
}
```

이 옵션은 이미 알고 있는 저온 피팅 결과, ARPES/DFT 기반 예상값, 이전 sample의 결과 등을 starting point로 사용할 때 유용합니다.

---

## 8. 세 가지 fitting mode

`optimization.fit_mode`로 지정합니다.

### 8.1 `both`

```json
"fit_mode": "both"
```

`rho_xx`와 `rho_xy`를 동시에 피팅합니다. 일반적인 multiband analysis에서는 이것을 기본값으로 권장합니다.

### 8.2 `rhoxx`

```json
"fit_mode": "rhoxx"
```

longitudinal channel만 objective function에 포함합니다. Hall curve는 예측되지만 optimizer가 Hall residual을 줄이려고 하지는 않습니다.

### 8.3 `rhoxy`

```json
"fit_mode": "rhoxy"
```

Hall channel만 피팅합니다. Hall curve에서 carrier sign/curvature 정보를 우선 조사하는 diagnostic fitting에 사용할 수 있습니다.

---

## 9. rho-space와 sigma-space

`fit_space`도 선택할 수 있습니다.

```json
"fit_space": "rho"
```

또는

```json
"fit_space": "sigma"
```

### rho-space

측정한 `rho_xx`, `rho_xy` 자체를 objective에 사용합니다.

장점:
- 사용자가 보고 있는 실제 resistivity curve와 fit quality가 직접 연결됩니다.

### sigma-space

측정 resistivity를 conductivity tensor로 변환한 뒤 `sigma_xx`, `sigma_xy`를 fit합니다.

장점:
- multiband Drude model은 conductivity에서 각 band contribution이 합으로 나타납니다.
- 일부 데이터에서는 numerical convergence가 더 안정적일 수 있습니다.

주의:
- `fit_mode="rhoxx"` + `fit_space="sigma"`이면 실제 objective channel은 `sigma_xx`입니다.
- `fit_mode="rhoxy"` + `fit_space="sigma"`이면 objective channel은 `sigma_xy`입니다.

---

## 10. rhoxx/rhoxy 상대 가중치

```json
"weight_rhoxx": 1.0,
"weight_rhoxy": 1.0
```

두 데이터의 단위/크기가 달라도 프로그램은 각 channel의 robust scale로 정규화합니다. 그 위에 사용자가 추가적인 상대 weight를 지정합니다.

예를 들어 longitudinal MR을 우선하고 싶다면

```json
"weight_rhoxx": 2.0,
"weight_rhoxy": 0.5
```

처럼 설정할 수 있습니다.

너무 극단적인 weighting은 한 채널의 fit을 개선하면서 다른 채널을 물리적으로 의미 없게 만들 수 있으므로 최종 residual을 반드시 확인해야 합니다.

---

## 11. low-field weighting

저자기장 curvature를 더 중요하게 보고 싶다면 다음을 켭니다.

```json
"low_field_weight": {
  "enabled": true,
  "alpha": 5.0,
  "B0_T": 1.0
}
```

프로그램은 longitudinal residual에

```text
w(B) = 1 + alpha * exp[-(|B|/B0)^2]
```

형태의 weight를 줍니다.

이 옵션은 저자기장 MR curvature가 중요한 경우 유용하지만, high-field를 희생할 수 있으므로 diagnostic option으로 보는 것이 좋습니다.

---

## 12. 온도별 fitting strategy

가장 중요한 SDD 옵션 중 하나입니다.

### 12.1 `independent`

각 온도를 완전히 독립적으로 fitting합니다.

```json
"temperature_strategy": "independent"
```

장점:
- 특정 온도 데이터가 요구하는 최적해를 최대한 자유롭게 찾음

단점:
- 같은 sample임에도 parameter가 온도별로 심하게 jump할 수 있음

이 방식은 **데이터가 실제로 얼마나 underdetermined인지 확인하는 baseline**으로 좋습니다.

### 12.2 `sequential`

```json
"temperature_strategy": "sequential"
```

낮은 온도부터 fitting하고, 직전 온도의 fitted parameter를 다음 온도의 initial guess로 사용합니다.

우리가 대화 중 여러 번 사용했던 방식과 가장 가깝습니다.

`smoothing.enabled=true`이면 추가로 직전 온도와의 log-parameter difference penalty도 들어갑니다.

### 12.3 `global_smooth`

```json
"temperature_strategy": "global_smooth"
```

모든 온도의 모든 parameter를 하나의 큰 optimization problem으로 동시에 fitting합니다.

이 방식이 **특정 온도 하나에서 parameter가 갑자기 튀는 것을 억제**하는 데 가장 적합합니다.

SDD에서 최종 production mode로 가장 권장합니다. 다만 parameter 수가 많아지므로 계산량이 증가합니다.

---

## 13. temperature smoothing

### 왜 log-space smoothing인가?

예를 들어 density가

```text
1e19 -> 2e19
```

로 바뀌는 것과

```text
1e20 -> 1.1e20
```

로 바뀌는 것을 단순 절대차로 penalty하면 전자가 훨씬 작은 변화처럼 보입니다. 하지만 물리적으로는 전자가 100% 변화이고 후자는 10% 변화입니다.

따라서 프로그램은

```text
log(n_T) - log(n_previous)
log(mu_T) - log(mu_previous)
```

에 penalty를 줍니다.

### smoothing order = 1

```json
"order": 1
```

인접 온도의 parameter 차이를 억제합니다.

```text
Penalty ~ [log p(T_i) - log p(T_i-1)]^2
```

효과:
- 전체적으로 parameter 변화가 작아지는 방향
- 실제 parameter가 온도에 따라 크게 변해야 하는 경우 bias가 생길 수 있음

### smoothing order = 2

```json
"order": 2
```

parameter 자체의 변화가 아니라 **온도 방향 slope의 변화**, 즉 curvature를 억제합니다.

개념적으로

```text
Penalty ~ [d(log p)/dT at i+1 - d(log p)/dT at i]^2
```

입니다.

이 옵션은 전체적인 증가/감소 trend는 허용하면서 **특정 온도에서만 갑자기 튀는 spike**를 억제하므로 현재 목적에 더 적합합니다.

권장 기본값은 `order=2`입니다.

---

## 14. density와 mobility smoothing을 따로 조절

```json
"smoothing": {
  "enabled": true,
  "order": 2,
  "lambda_density": 1.0,
  "lambda_mobility": 1.0
}
```

- `lambda_density`: density smoothness strength
- `lambda_mobility`: mobility smoothness strength

0이면 해당 종류는 사실상 smoothing하지 않습니다.

각 carrier별로도 smoothing 적용 여부를 정할 수 있습니다.

```json
"smooth_density": true,
"smooth_mobility": false
```

예를 들어 큰 Fermi surface의 carrier density는 거의 일정하다고 보고 강하게 smoothing하고, 작은 pocket의 mobility는 자유롭게 두는 식의 실험이 가능합니다.

---

## 15. monotonicity 옵션

각 carrier별로

```json
"monotonic_density": "decrease"
```

또는

```json
"monotonic_density": "increase"
```

를 지정할 수 있습니다.

가능한 값:

- `none`
- `increase`
- `decrease`

현재 구현에서 `global_smooth`의 monotonicity는 **soft penalty** 방식입니다.

```json
"monotonic_penalty": {
  "enabled": true,
  "lambda": 10.0
}
```

중요: 단조성은 데이터가 요구하는 결과가 아니라 사용자가 추가하는 물리적 prior입니다. 근거 없이 강하게 적용하면 좋은 R²를 얻더라도 잘못된 parameter를 만들 수 있으므로 SDD에서는 반드시 **optional constraint**로 남겨두는 것이 좋습니다.

---

## 16. multi-start

multiband fitting은 local minimum이 매우 많습니다. 따라서 한 initial guess만 사용하면 결과가 initial condition에 강하게 의존할 수 있습니다.

```json
"multi_start": 3,
"multi_start_log_sigma": 0.20
```

첫 번째 fit은 지정 initial value에서 시작하고, 이후 fit은 log-space에서 random perturbation된 starting point를 사용합니다.

계산 시간이 허용된다면 5~20 이상의 multi-start를 사용해 robustness를 확인하는 것이 좋습니다.

---

## 17. robust loss

기본은 ordinary least squares입니다.

```json
"loss": "linear"
```

SciPy `least_squares`가 지원하는

- `soft_l1`
- `huber`
- `cauchy`
- `arctan`

등을 사용할 수 있습니다.

outlier가 있는 데이터에서는 `soft_l1`이 유용할 수 있습니다. 하지만 systematic model mismatch를 outlier로 숨길 수 있으므로 최종 분석에서는 linear loss와 비교하는 것을 권장합니다.

---

## 18. 전처리 옵션

### Hall scaling

raw `rho_xy`가 실제 값의 2배라면

```json
"rhoxy_scale": 0.5
```

로 설정합니다.

### rho_xx symmetrization

```json
"symmetrize_rhoxx": true
```

가능한 경우

```text
rho_xx_sym(B) = [rho_xx(B) + rho_xx(-B)] / 2
```

를 사용합니다.

### rho_xy antisymmetrization

```json
"antisymmetrize_rhoxy": true
```

```text
rho_xy_asym(B) = [rho_xy(B) - rho_xy(-B)] / 2
```

를 사용합니다.

이 두 과정은 contact misalignment에 의한 longitudinal/Hall mixing을 줄이는 데 중요합니다.

---

## 19. 출력 파일

### 온도별 `{T}K_fit.csv`

포함 항목:

- raw `rho_xx`
- raw `rho_xy`
- fitted `rho_xx`
- fitted `rho_xy`
- raw-converted `sigma_xx`, `sigma_xy`
- fitted `sigma_xx`, `sigma_xy`
- rho residuals

따라서 사용자가 Origin, Igor, Python 등에서 직접 plot할 수 있습니다.

### `fit_parameters_vs_T.csv`

각 온도에서 carrier별

- density
- mobility

를 저장합니다.

### `fit_metrics_vs_T.csv`

각 온도별

- R²(rho_xx)
- R²(rho_xy)
- RMSE(rho_xx)
- RMSE(rho_xy)

를 저장합니다.

### `resolved_config.json`

실제 사용한 설정을 그대로 저장합니다. 이는 reproducibility와 SDD에서 특히 중요합니다.

---

## 20. R²를 해석할 때 주의점

R²는 **높을수록** 좋은 fit입니다.

```text
R² = 1 - SSE/SST
```

따라서 목표는 R²를 '낮추는 것'이 아니라 residual 또는 RMSE를 낮추고 R²를 1에 가깝게 만드는 것입니다.

하지만 multiband problem에서는 R²가 매우 높아도 parameter가 물리적으로 unique하지 않을 수 있습니다.

따라서 최소한 다음을 함께 봐야 합니다.

1. R² / RMSE
2. residual의 systematic structure
3. parameter가 bounds에 붙는지
4. initial guess를 바꿔도 비슷한 해가 나오는지
5. temperature continuity
6. carrier label swapping 여부
7. density와 mobility 간 compensation 여부

---

## 21. 권장 fitting workflow

### Stage A — unconstrained diagnostic

```text
temperature_strategy = independent
smoothing = off
monotonic = off
```

목적: 데이터가 각 온도에서 독립적으로 어떤 해를 선호하는지 확인.

### Stage B — sequential continuity check

```text
temperature_strategy = sequential
smoothing = weak
```

목적: 직전 온도 solution으로부터 안정적으로 이어지는지 확인.

### Stage C — production global fit

```text
temperature_strategy = global_smooth
smoothing.order = 2
```

목적: 전체 온도 series에 일관된 parameter trajectory를 얻기.

### Stage D — sensitivity analysis

- initial value 변경
- bounds 확대/축소
- rho-space vs sigma-space
- fit_mode 변경
- smoothing lambda scan
- multi-start 증가

을 통해 conclusion이 설정에 robust한지 확인합니다.

---

## 22. SDD 관점에서 반드시 분리해야 할 것

### Requirement

예:

> 프로그램은 임의 개수의 electron/hole carrier를 지원해야 한다.

### Configuration

예:

> 이번 dataset에서는 electron 2개 + hole 2개를 사용한다.

### Prior / Constraint

예:

> ne1은 온도 증가에 따라 감소할 것으로 가정한다.

### Acceptance criterion

예:

> 각 온도에서 R²_xx > 0.995이고, fitted parameter가 hard bound에 붙지 않아야 한다.

### Diagnostic rule

예:

> R²는 높지만 carrier density가 인접 온도 대비 10배 이상 jump하면 parameter-identifiability warning을 발생시킨다.

이 다섯 종류를 섞지 않는 것이 중요합니다.

---

## 23. 이 프로그램의 한계

이 프로그램은 **classical independent-carrier Drude/Boltzmann model**입니다. 따라서 다음 현상이 강하면 좋은 curve fit 또는 물리적으로 유일한 carrier parameter를 보장하지 않습니다.

- strongly anisotropic scattering `tau(k)`
- field-dependent scattering rate
- strong interband scattering
- effective-medium / phase mixture
- quantum interference correction
- hydrodynamic or nonlocal transport
- magnetic scattering
- open-orbit effects
- Fermi-surface topology가 단순한 independent pockets로 환원되지 않는 경우

특히 parameter가 온도별로 비정상적으로 튀는데 curve 자체는 잘 맞는 경우에는 **더 강한 constraint를 걸기 전에 모델의 identifiability와 validity를 먼저 의심**해야 합니다.

---

## 24. 향후 확장하기 좋은 기능

SDD 다음 iteration에서는 다음 기능을 추가하기 좋습니다.

1. bootstrap uncertainty / confidence interval
2. covariance/Jacobian 기반 parameter uncertainty
3. AIC/BIC를 이용한 band-number comparison
4. mobility spectrum inversion
5. automatic residual-pattern diagnostic
6. automatic lambda scan / L-curve
7. parameter-boundary warning
8. carrier label matching across temperature
9. 2-stage low-field -> full-field fitting
10. global fit의 parallel multi-start

현재 코드는 이 기능들을 추가하기 쉽도록 carrier 정의, residual, smoothing, output을 분리해 두었습니다.
