# 빠른 시작

Feature 001 · 2026-08-26

> **번역본입니다.** 정본은 `specs/001-multiband-drude/quickstart.md` 입니다.
> 코드가 존재하기 전에 쓴 것이므로, 이 문서는 **명령줄의 명세**이기도 합니다.
> Gate 7 (T703) 에서 실제로 실행해 검증합니다.

---

## 설치

```bash
python -m pip install -r requirements.txt
```

## 실행

```bash
python -m mbfit --data tests/data/synthetic_5K.csv --config configs/synthetic_5K.json --out results
```

필수 인자 셋, 그리고 필수가 아닌 하나: `--no-priors`. 아래 workflow 참조.
`--out` 바깥에는 아무것도 쓰지 않으며, 테스트가 그것을 확인한다.

저장소에 설정 두 개가 함께 있다. `configs/synthetic_5K.json` 은
`tests/data/synthetic_5K.csv` 용 hole 2 + electron 2 이고, 그것이 테스트가
맞추는 sweep 이다. `configs/example_1e1h.json` 은
`tests/data/synthetic_small.csv` 용 작은 1+1 fixture 로, 기계가 도는 것을 빨리
보기에 좋다. 그 데이터에 잘 맞지는 않고 **진단이 그렇게 말한다.** 그것을 한 번
보는 것 자체가 도움이 된다.

두 sweep 모두 측정값이 아니다. `tests/data/make_synthetic.py` 가 둘 다 만들고,
그것이 무엇이며 왜 그런 모양인지는 `tests/data/README.md` 에 적혀 있다. 시료의
측정 sweep 은 이 프로그램과 함께 공개하지 않는다.

## 무엇이 나오는가

```text
results/
  resolved_config.json        실제로 쓴 모든 설정과 seed
  diagnostics.csv             모든 경고. 임계와 출처와 함께
  fit_parameters_vs_T.csv     온도별 carrier별 밀도와 이동도.
                              선언 순서와 정규 순서 둘 다
  fit_metrics_vs_T.csv        R², RMSE, FR-055 의 조건수,
                              그리고 실제 적용된 채널 척도
  5K_fit.csv                  한 온도의 측정·fit·residual.
                              두 공간 모두, 자기장 창 바깥 레코드까지 전부
  5K_rhoxx.png  5K_rhoxy.png
  multistart_5K.csv           모든 시작점과 그것이 도달한 곳
  parameters_vs_T.png         온도가 둘 이상일 때만
```

> **파라미터보다 `diagnostics.csv` 를, 그중에서도 `D_ILL_CONDITIONED` 를 가장
> 먼저 읽으십시오.** 데이터가 답을 결정하기는 했는지를 말해 주는 유일한 줄입니다.
> R² 가 0.999 를 넘으면서 carrier 밀도가 3분의 1만큼 틀릴 수 있습니다.
> `research.md` §4.3 이 바로 그것을 측정했고, §4.6 은 조건수가 그 경우와
> 멀쩡한 경우를 13배로 갈라 놓는 것을 보여 줍니다.

## 동작하는 최소 설정

```json
{
  "schema_version": "1.0",
  "columns": {
    "T": "T(K)",
    "B": "B(T)",
    "rhoxx": "rhoxx(microohm cm)",
    "rhoxy": "rhoxy(microohm cm)"
  },
  "carriers": [
    {
      "name": "e1",
      "kind": "electron",
      "density":  {"init": 1e19, "min": 1e16, "max": 1e22},
      "mobility": {"init": 6000, "min": 1,    "max": 50000}
    },
    {
      "name": "h1",
      "kind": "hole",
      "density":  {"init": 1e19, "min": 1e16, "max": 1e22},
      "mobility": {"init": 6000, "min": 1,    "max": 50000}
    }
  ]
}
```

나머지는 전부 기본값을 따르며, **모든 기본값은 아무것도 하지 않습니다**:
온도 사이 결합 없음, 단조 기대 없음, 저자기장 강조 없음, 보통 최소제곱,
각 온도를 독립적으로 fitting. 이것이 아래 workflow의 **stage A** 이며,
정직한 출발점입니다.

## 권장 workflow

| 단계 | 설정 | 무엇을 위한 것인가 |
| --- | --- | --- |
| A | 기본값, `temperature_strategy: independent` | 아무것도 부과하지 않았을 때 각 온도가 무엇을 선호하는지 확인. **이후 모든 결과를 비교할 기준선** |
| B | `sequential` | 각 온도를 바로 아래 온도에서 seed 하고, 해가 튀지 않고 이어지는지 확인. **sequential 은 smoothing 을 하지 않는다.** 탐색이 시작하는 자리를 바꿀 뿐 최소화 대상을 바꾸지 않는다 |
| C | `global_smooth`, `smoothing.order: 2`, 0 보다 큰 결합 강도 | production fit. 그리고 **결합 penalty 가 작동하는 유일한 모드**. 전체 온도 계열에 일관된 파라미터 궤적. **계열이 충분히 길어야 한다** — 아래 註 참조 |
| D | stage C 를 `--no-priors` 로 한 번 더 돌린 뒤, 초기값·bounds·`fit_space`·`fit_mode`·결합 강도·`multi_start` 를 바꿔 가며 | **어떤 결론이 설정을 견디고, 어떤 것이 사실은 설정이었는지** 확인 |

> **stage C 에는 온도가 4~5개 필요하고, research §5.6 이 그 이유를 측정했다.**
> 2차 penalty 는 연속한 온도 3개마다 곡률 추정치 하나를 만든다. 따라서 온도
> 3개짜리 계열은 내부 마디가 하나뿐이고 penalty 는 평균 낼 대상이 없다. 이
> 프로젝트의 5, 20, 40 K sweep 3개에서 측정한 결과, 답이 바뀔 만큼 결합을 걸면
> 조건수가 좋은 5 K sweep 이 `19 %` 움직이고, 구해 주려던 조건수 나쁜 40 K sweep 은
> `65 %` 움직이면서 `R2` 가 떨어졌다. penalty 가 좋은 쪽의 정보를 나쁜 쪽에
> 빌려준 것이 아니라 양쪽을 중간에서 만나게 했다. 게다가 눈에 띄는 특징 —
> 20 K 와 40 K 사이의 Hall 부호 전환 — 에 break 를 두면 구간이 온도 2개와 1개로
> 갈리고 어느 쪽도 2차 항을 지탱하지 못해, penalty 가 소리 없이 아무것도 아닌 것이
> 된다.
>
> 계열이 짧으면 stage B 에서 멈추고 독립 fit 을 보고한다. 길면 결합을 `0.01`
> 부터 올리되, 조건수가 좋은 온도들이 research §4.8 의 정확도 예산 안에 남는 가장
> 큰 값에서 멈춘다.

**stage D 는 선택이 아닙니다.** 헌법 제X조는 모든 제약에 대해 "제거해도 결론이
유지되는가"를 묻습니다. stage D 가 그 답을 만드는 자리이고, `--no-priors` 가
그 질문의 **한 줄 형태**입니다:

```bash
python -m mbfit --data d.csv --config c.json --out results_nopriors --no-priors
```

soft prior 전부 꺼짐 — 결합, 단조 기대, 저자기장 강조, robust loss — 그 외에는
아무것도 건드리지 않습니다. bounds 와 자기장 창은 남습니다. 그것들은 정의역 안의
선호가 아니라 **허용 정의역 자체에 대한 진술**이기 때문입니다. 두 실행 사이에서
carrier 밀도가 유의미하게 움직인다면, **그 차이는 데이터가 아니라 prior 가
말하고 있는 것**입니다.

## 1년 뒤에 실행을 재현하기

```bash
python -m mbfit --data tests/data/synthetic_small.csv --config results/resolved_config.json --out results_check
```

모든 숫자가 동일해야 합니다. 그렇지 않다면 그것은 방법의 성질이 아니라
**결함**입니다 (NR-005).
