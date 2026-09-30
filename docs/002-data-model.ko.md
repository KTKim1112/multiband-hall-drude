# data model 002 — feature 002 가 설정·코드·출력에 더하는 것

> **정본은 `specs/002-uncertainty-and-discriminants/data-model.md` 입니다.** 이
> 문서는 그 번역이며, 둘이 어긋나면 영어 쪽이 맞습니다.
>
> 이 문서는 `specs/001-multiband-drude/data-model.md` 를 확장합니다. 거기
> 선언된 것은 아무것도 바뀌지 않습니다. feature 001 문서를 가진 독자는 그것을
> 다시 읽을 필요가 없습니다. 아래는 전부 새로 추가되는 것입니다.

---

## 1. 설정

새 절이며, feature 001 의 의미에서 **기본적으로 아무 일도 하지 않습니다.**
이 절을 언급하지 않는 설정은 이전과 정확히 같게 동작합니다. 다만 `spec.md`
§4.2 의 판별법은 충분히 싸서 항상 수행합니다.

```text
uncertainty
  enabled              false      재샘플링은 일이고, 켜야 합니다
  resamples            200        AC-011
  block_length         20         AC-012. FR-059 가 결과와 함께 기록하게 합니다
  interval_fraction    0.68       AC-013
  seed                 null       null 이면 실행 seed 에서 유도합니다
```

```text
discriminants
  harmonic_tolerance   0.05       AC-014
  parity_threshold     0.02       AC-015
```

`uncertainty.enabled` 의 기본값이 false 인 이유는 재샘플링 실행이 온도당
`resamples` 번의 fit 을 쓰기 때문이고, feature 001 의 계약이 **기본 실행은 가장
싼 정직한 일을 한다**이기 때문입니다. 나머지는 전부 임계값이고, 임계값은
구성상 아무 일도 하지 않습니다. **무엇이 보고되는지**를 정할 뿐 **무엇이
적합되는지**는 결코 바꾸지 않습니다.

---

## 2. 진단 코드

| 코드 | 언제 발생하나 | 출처 |
| --- | --- | --- |
| `D_HARMONIC_LADDER` | 적합된 이동도가 세 사다리 조건을 모두 만족. carrier 집합이 여러 밴드가 아니라 비원형 궤도 하나일 수 있음 | FR-063 |
| `D_PARITY_VIOLATION` | 대칭화 **전에** 측정한 어떤 채널의 잘못된 패리티 성분이 `discriminants.parity_threshold` 를 넘음 | FR-065, AC-015 |
| `D_SINGLE_POLARITY` | sweep 이 한쪽 극성만 담고 있어 패리티 위반을 측정할 수 없었고, 채널 혼입이 남아 있음 | FR-066 |
| `D_INTERVAL_LOWER_BOUND` | 잔차가 구조적인 fit 에 대해 재샘플링 구간을 계산했으므로, 그 구간이 불확실도를 과소진술함 | FR-060 |

`D_HARMONIC_LADDER` 는 경고이지 오류가 아닙니다. 사다리는 궤도 하나임을
**증명하지 않습니다.** 데이터가 그 해석과 다밴드 해석을 구별하지 못한다는
뜻이고, 이는 다르고 더 약한 진술입니다. 보고서는 세 조건을 따로 담아 독자가
무엇이 성립했는지 볼 수 있게 합니다.

---

## 3. 출력 파일

| 파일 | 행 단위 | 담는 것 |
| --- | --- | --- |
| `uncertainty_<T>K.csv` | 파라미터 | 값, 구간의 하한과 상한, 1시그마, 그 구간이 하한인지 여부 |
| `correlation_<T>K.csv` | 파라미터 | 다른 모든 파라미터와의 상관 |
| `derived_vs_T.csv` | 온도 | 각 부호의 총 밀도, 그 비, 그 차, 각각의 구간과 함께 |
| `harmonics_vs_T.csv` | 온도 | 각 채널의 가장 빠른 것에 대한 비, 가장 가까운 조화, 세 조건 중 무엇이 성립했는지 |

`resolved_config.json` 에 `uncertainty` 와 `discriminants` 절이 더해지며,
실제로 작동한 block 길이와 재샘플 횟수를 포함합니다. 그래야 FR-037 이 계속
성립합니다. 방출된 설정을 되먹이면 구간까지 포함해 실행이 재현됩니다.

---

## 4. 보고서 문구

결과가 어떻든 매 실행마다 두 문장이 나갑니다.

- FR-064, 항상: 적합된 이동도는 **유효 채널 이동도**이지 Fermi pocket 의 미시적
  이동도가 아닙니다.
- FR-060, 구조적 잔차에 구간이 동반될 때마다: 그 구간은 **잔차의 재샘플링을
  덮을 뿐** 그 잔차를 구조적으로 만든 모델 부족을 덮지 **않으며**, 따라서
  하한입니다.

둘 다 나머지 한국어 문구와 함께 표현 계층에 놓입니다. 헌법 제IV조와 제VIII조에
따릅니다.
