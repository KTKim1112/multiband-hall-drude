# data model 003 — feature 003 이 더하는 것

> **정본은 `specs/003-mobility-spectrum/data-model.md` 입니다.** 이 문서는 그
> 번역이며, 둘이 어긋나면 영어 쪽이 맞습니다.
>
> feature 001 과 002 의 data model 을 확장합니다. 거기 선언된 것은 아무것도
> 바뀌지 않습니다.

---

## 1. 설정

```text
spectrum
  enabled                false      켜야 합니다. 정규화 단계마다 역문제를 한 번씩 풉니다
  mu_min_cm2Vs           100        격자와 확장의 경계, 아래쪽 끝
  mu_max_cm2Vs           300000     그리고 위쪽 끝
  points_per_decade      40         AC-017
  lorentzian_terms       6          FR-069 의 확장 차수
  lorentzian_multi_start 12         확장의 출발점 개수, FR-068
  lorentzian_constrained true       NR-011. false 로 두면 논문 방식을 그대로 재현합니다
  zero_field_window_T    0.5        sigma_xx(0) 을 추정하는 구간, FR-067
  alpha_min              1e-16      검토할 정규화 세기, 아래쪽
  alpha_max              1e-2       그리고 위쪽. decade 당 한 단계
  noise_source           "residual" "residual" 이면 fit 잔차의 2차 차분에서 추정하고,
                                    숫자 쌍이면 채널별로 직접 선언합니다
  discrepancy_factor     1.1        AC-018
  peak_floor             0.02       AC-019. 해당 분지의 최댓값에 대한 비율이면서
                                    동시에 스펙트럼 전체에 대한 비율입니다
  plateau_decades        3          AC-020
  roundtrip_tolerance    0.05       AC-025
```

독자가 **반드시 생각해야 하는** 설정이 둘 있고, 선언되는 자리에서 문서가 각각
그렇게 말합니다. `lorentzian_terms` 는 FR-069 의 차수이며 프로그램이 스스로
정하지 않습니다. research 003 §3.3 이, 서로 다른 이동도의 개수보다 낮은 차수는
7배만큼 어긋나는 것을 측정했습니다. `noise_source` 는 불일치 원리가 무엇을
견주는지를 정하며, 이것을 잘못 고르면 그 뒤의 어떤 단계도 되돌릴 수 없습니다.

---

## 2. 진단 코드

아홉 개이고, 세 무리로 나뉩니다. **2단계의 확장이 무엇을 했는가**, **5단계의
역문제가 무엇을 결정할 수 있었는가**, 그리고 따로 떨어진 하나입니다. 마지막
것은 결과를 방법 자신의 기대가 아니라 **측정**과 견주는 유일한 코드입니다.
두 번째 무리는 **carrier 종류마다 따로** 보고됩니다. 분리한 뒤에는 hole 문제와 electron 문제가 서로 독립적으로 성공하고
실패하기 때문입니다.

| 코드 | 언제 발생하나 | 출처 |
| --- | --- | --- |
| `D_SPECTRUM_EXTENSION_UNDERFIT` | Lorentzian 잔차가 잡음의 10배를 넘음. 데이터가 가진 서로 다른 이동도보다 항이 적다는 뜻이고, 그 뒤의 모든 단계가 이 부족분을 물려받습니다 | FR-069, AC-021 |
| `D_SPECTRUM_EXTENSION_SATURATED` | 항 하나가 선언된 이동도 범위의 끝에 앉음. 데이터가 아니라 범위가 그 자리를 정한 것입니다 | FR-069 |
| `D_SPECTRUM_EXTENSION_MULTIMODAL` | 출발점의 절반 미만이 최선해에 도달함. 확장이 여럿 중 하나를 **고른** 것입니다 | FR-068 |
| `D_SPECTRUM_UNCONSTRAINED` | NR-011 의 비음수 제약을 껐음. 논문 방식을 그대로 재현하며, 그와 함께 상쇄 가중치 골짜기도 함께 허용합니다 | NR-011 |
| `D_SPECTRUM_NEGATIVE_PART` | 분리된 전도도가 어딘가에서 부호를 잃음. NR-011 아래에서는 불가능하므로 제약을 껐을 때만 발생합니다 | FR-071, AC-024 |
| `D_SPECTRUM_NOISE_UNREACHED` | 검토한 어느 세기도 이 carrier 종류를 선언된 잡음까지 맞추지 못함 | FR-073, AC-018 |
| `D_SPECTRUM_UNRESOLVED` | 이 carrier 종류에 선언된 길이의 고원이 아예 없음 | FR-073, AC-020 |
| `D_SPECTRUM_AMBIGUOUS` | 이 carrier 종류에 고원이 둘 이상. 둘 이상의 개수가 데이터에 맞습니다 | FR-073, AC-020 |
| `D_SPECTRUM_ROUNDTRIP` | 스펙트럼에서 읽어낸 carrier 를 모형에 되넣었을 때 이 채널의 sweep 을 재현하지 못함. 채널마다 따로 발생합니다 | FR-079, AC-025 |

어느 것도 스펙트럼이 틀렸다고 말하지 않습니다. 스펙트럼의 **어느 부분까지를
인용해도 되는지**를 말합니다.

---

## 3. 출력 파일

| 파일 | 행 단위 | 담는 것 |
| --- | --- | --- |
| `spectrum_<T>K.csv` | 격자점 | 이동도, 그리고 carrier 종류마다 전도도 밀도 열 하나씩 |
| `spectrum_peaks_<T>K.csv` | 봉우리 | carrier 종류, 이동도, 그것이 함의하는 밀도, 가중치, 나온 세기 |
| `spectrum_stability_<T>K.csv` | carrier 종류와 세기 | 세기, 잔차 노름, 견주는 목표값, 거칠기, 봉우리 개수 |
| `spectrum_extension_<T>K.csv` | Lorentzian 항 | 이동도, hole 가중치 `p`, electron 가중치 `q`, 그리고 원래의 `a`, `b` |
| `spectrum_roundtrip_<T>K.csv` | 채널 | 측정과, 스펙트럼의 carrier 를 모형에 되넣은 결과 사이의 최대 상대 차이, 그리고 그것을 견주는 허용값 |

`resolved_config.json` 에 `spectrum` 절이 더해지며, 선택된 세기와 사용한 잡음
수준을 포함합니다. 그래야 FR-037 이 계속 성립합니다.

---

## 4. 보고서 문구

스펙트럼을 낼 때마다 세 문장이 함께 나갑니다.

- 봉우리는 **전도 채널**이지 Fermi surface 의 밴드가 아닙니다. 비원형 궤도
  하나를 사이클로트론 조화 4개로 읽었을 때 봉우리 3개가 나오는 것을 research
  003 §7 이 측정했습니다. 따라서 봉우리 개수는 Fermi surface 개수의 **상한**이지
  추정값이 아닙니다.
- 모든 봉우리는 확장이 고른 이동도 위에 앉습니다. 확장이 허용하지 않은 구조는
  스펙트럼도 찾아내지 못합니다. FR-077.
- carrier 개수는 여전히 독자의 **선언**으로 남습니다. 스펙트럼은 제안할
  뿐입니다. FR-076.
