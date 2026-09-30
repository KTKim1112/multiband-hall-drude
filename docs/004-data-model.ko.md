# data model 004 — feature 004 이 더하는 것

> **정본은 `specs/004-workflow/data-model.md` 입니다.** 이 문서는 그 번역이며,
> 둘이 어긋나면 영어 쪽이 맞습니다.
>
> feature 001 부터 003 까지의 data model 을 확장합니다. 거기 선언된 것은
> 아무것도 바뀌지 않습니다. 워크플로우는 진단 코드를 더하지 않습니다. 워크플로우가
> 자기 자신에 대해 보고하는 것은 아래 열들에 실립니다. 떨어진 게이트는 사건이
> 아니라 한 온도의 한 조합의 성질이기 때문입니다.

---

## 1. 설정

```text
workflow
  count                 "data"     FR-080. "data" 또는 "peaks"
  peaks_multi_start     12         peaks 규칙: fit 의 출발점 수
  peaks_fit_budget_s    120        peaks 규칙: fit 의 초 (C16)
  max_per_sign          4          FR-082: 경계를 넘어 부호마다 이만큼까지
                                   개수를 늘릴 수 있음 (C17)
  window_factor         3          AC-030, 극단 봉우리 양옆으로
  residual_factor       2          AC-026
  spread_max            0.01       AC-027
  share_min             0.001      AC-028, 영자기장 전도에 대한 몫
  search_multi_start    12         탐색 중 조합마다의 출발점 수
  final_multi_start     24         경계를 푼 재적합의 출발점 수
  fit_budget_s          30         AC-029, fit 하나에 대한 초. 0 이면 없앰
  loop_tolerance        0.01       peaks 규칙: fit 된 밀도와 이동도가 이보다
                                   덜 움직이면 정지
  loop_max_iterations   10         peaks 규칙: 그리고 이보다 많이는 안 돎
  fixed_counts          {}         FR-090. {"<T>" 또는 "<low-high>": [hole 수,
                                   electron 수]}, 합쳐서 최대 8개. sweep 을
                                   덮는 가장 좁은 구간이 이깁니다
  smooth_band           []         FR-112. [{"range": "<T>" 또는 "<low-high>",
                                   "strength": weak|normal|strong}]. 각 구간은
                                   fixed_counts 로 하나의 개수에 묶인 뒤 온도에
                                   걸쳐 결합됩니다(FR-027). 온도가 셋 미만이거나
                                   sweep 들이 한 개수를 공유하지 않는 구간은
                                   거절합니다
  smooth_multi_start    1          AC-040. 결합 재적합의 출발점 수. 이미 찾은
                                   답에서 시작하므로, 무작위 출발점을 더 두면
                                   이미 푼 문제를 다시 푸는 것입니다

optimization
  fit_budget_s          30         FR-088, 어떤 fit 에나 같은 예산
  global_budget_s       1800       AC-039, 구간 전체를 한 번에 푸는 결합 fit 
                                   하나의 예산(초). 0 이면 없앱니다.
                                   fit_budget_s 와 별개입니다 — 그 30초는 결합
                                   fit 의 모든 출발점을 만료시킵니다
```

`count` 는 답에 이르는 방식이 아니라 답이 **무엇을 주장하는지**를 바꾸는 유일한
설정이며, 모든 결과는 개수를 정한 규칙과 그것이 주장할 수 있는 것과 함께
출력됩니다 (FR-081).

---

## 2. 출력 파일

개수 규칙을 요청했을 때만 씁니다. feature 001 부터 003 까지의 파일은 바뀌지 않고
여전히 씁니다.

| 파일 | 행 단위 | 담는 것 |
| --- | --- | --- |
| `workflow_summary.csv` | 온도 | 개수 규칙, 조합, 스펙트럼 경계를 넘었는지, 등급, 두 채널의 잔차/노이즈와 runs test, 각 채널의 노이즈, 두 채널의 `R^2`, 두 채널의 RMSE, 조건수, 퍼짐, 통과 못 한 게이트, 창을 벗어난 carrier, 재현되지 않지만 더 잘 맞는 조합과 몇 배인지, 되먹임 반복 수, 루프가 멈춘 이유, 초 |
| `workflow_carriers.csv` | fit 된 carrier | 온도, 이름, 종류, cm^-3 단위 밀도, cm^2/Vs 단위 이동도, 영자기장 전도 분담, 9 T 에서의 `mu B` |
| `workflow_candidates.csv` | 시도한 조합 | 온도, hole 수, electron 수, 두 채널의 RMSE, 조건수, 퍼짐, 가장 약한 분담, 경계에 붙음, 예산 초과, 초 |
| `report.html` | 실행 | FR-092 의 페이지 |

peaks 규칙에서 게이트는 계산해 보고하지만 아무것도 고르지 않습니다. 봉우리가
없었거나 fit 이 끝나지 않은 온도는 carrier 가 없으며 결코 통과가 아닙니다. 무한대 잔차는 모든 출발점이 예산을 넘긴 조합입니다.

---

## 3. 보고서 페이지

네트워크 없이 열리는 파일 하나. 순서가 요구사항의 일부입니다.

1. 온도별 판정: 조합, 등급, 통과 못 한 게이트
2. 고른 온도에서 두 채널의 측정 대 fit
3. 모든 carrier 의 밀도와 이동도 대 온도
4. 시도한 모든 조합

페이지의 모든 문구는 `mbfit/messages.py` 에서 와서 생성기에 넘겨지며, 그래서
생성기가 제IV조 아래 ASCII 로 남습니다.
