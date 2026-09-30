"""사용자에게 보이는 한국어 문구. 코드를 키로 한다.

헌법 제IV조와 제VIII조: 라이브러리는 실패를 코드로 알리고, 사람이 읽을 문장은
표현 계층에만 둔다. 이 모듈과 `cli.py` 만이 비ASCII 문자를 담을 수 있으며,
`tests/test_ascii.py` 가 그것을 강제한다.

여기의 문구를 다시 쓰더라도 테스트는 한 줄도 바뀌지 않는다. 테스트는
`E_DATA_MISSING_COLUMN` 을 확인하지, 문장을 확인하지 않기 때문이다.
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------- 실패 코드

ERROR_MESSAGES: dict[str, str] = {
    "E_CONFIG_UNREADABLE": "설정 파일을 읽을 수 없습니다.",
    "E_CONFIG_SCHEMA_VERSION": "설정의 schema_version 이 없거나 지원하지 않는 값입니다.",
    "E_CONFIG_UNKNOWN_FIELD": "설정에 모르는 항목이 있습니다. 오타가 기본값을 조용히 살려 두지 않도록 거부합니다.",
    "E_CONFIG_MISSING_FIELD": "설정에 반드시 있어야 할 항목이 없습니다.",
    "E_CONFIG_BAD_VALUE": "설정 값이 허용 범위나 허용 집합을 벗어났습니다.",
    "E_CONFIG_NO_CARRIERS": "carrier 를 최소 하나는 선언해야 합니다.",
    "E_CONFIG_DUPLICATE_CARRIER": "carrier 이름이 중복되었습니다.",
    "E_CONFIG_BAD_CARRIER_KIND": "carrier 의 kind 는 electron 또는 hole 이어야 합니다.",
    "E_CONFIG_BOUNDS_INVALID": "bounds 가 잘못되었습니다. min 은 0보다 커야 하고 max 이하여야 합니다.",
    "E_CONFIG_INIT_OUT_OF_BOUNDS": "초기값이 자기 bounds 밖에 있습니다. fitting 을 시작하기 전에 거부합니다.",
    "E_CONFIG_UNKNOWN_CARRIER": "선언되지 않은 carrier 이름을 지칭했습니다.",
    "E_CONFIG_EMPTY_FIELD_WINDOW": "자기장 창이 어떤 온도에서 레코드를 하나도 남기지 않습니다.",
    "E_CONFIG_COUPLING_WITHOUT_GLOBAL": (
        "결합 penalty 또는 단조 prior 는 temperature_strategy 가 global_smooth 일 때만 작동합니다. "
        "sequential 은 초기값만 이어 줄 뿐 penalty 를 걸지 않습니다."
    ),
    "E_CONFIG_BREAK_OUTSIDE_RANGE": "smoothing 절단선이 측정된 온도 범위 밖에 있어 아무것도 끊지 못합니다.",
    "E_DATA_UNREADABLE": "데이터 파일을 읽을 수 없습니다.",
    "E_DATA_MISSING_COLUMN": "데이터에 선언된 컬럼이 없습니다.",
    "E_DATA_EMPTY": "쓸 수 있는 레코드가 하나도 남지 않았습니다.",
    "E_DATA_UNDERDETERMINED": (
        "어떤 온도의 residual 개수가 자유 파라미터 개수보다 적습니다. "
        "residual 개수는 레코드 개수가 아니라 레코드 개수 곱하기 채널 수입니다."
    ),
    "E_FIT_NO_START": "모든 시작점이 실패했습니다.",
    "E_FIT_SINGULAR": "전도도 텐서를 역변환할 수 없습니다. sigma_xx^2 + sigma_xy^2 가 0 입니다.",
}

# ---------------------------------------------------------------- 진단 코드

DIAGNOSTIC_MESSAGES: dict[str, str] = {
    "D_R2_BELOW": "결정계수가 합격 기준에 미달했습니다.",
    "D_AT_BOUND": "파라미터가 bound 에 붙어 멈췄습니다. bound 를 넓히면 결과가 달라질 수 있습니다.",
    "D_JUMP": "인접 온도 사이에서 파라미터가 크게 도약했습니다. D_LABEL_SWAP 을 함께 보십시오.",
    "D_NON_UNIQUE": "구별할 수 없는 fit 품질로 서로 다른 파라미터 집합에 도달했습니다.",
    "D_RESIDUAL_STRUCTURE": (
        "잔차가 산포가 아니라 자기장에 대한 계통적 구조를 유지합니다. "
        "모델이 데이터를 완전히 표현하지 못한다는 뜻이며, R² 만으로는 보이지 않습니다."
    ),
    "D_LABEL_SWAP": (
        "같은 부호의 carrier 가 인접 온도 사이에서 순서를 바꿨습니다. "
        "모델은 이 교환에 대해 대칭이므로 비용이 0 입니다. 물리적 변화가 아닐 수 있습니다."
    ),
    "D_MIRROR_ABSENT": "대칭화에 필요한 반대 부호 자기장 레코드를 찾지 못해 그대로 둔 점이 있습니다.",
    "D_RECORDS_DROPPED": "값이 없거나 숫자가 아닌 레코드를 버렸습니다.",
    "D_LOW_MU_B": (
        "이 carrier 는 측정 범위 전체에서 mu*B 가 1 미만입니다. "
        "저자기장에서는 개별 carrier 가 아니라 몇 개의 모멘트만 결정되므로, "
        "R² 가 높아도 이 carrier 의 값은 크게 틀릴 수 있습니다."
    ),
    "D_EXCLUDED_MISMATCH": "자기장 창 바깥의 잔차가 창 안쪽보다 훨씬 큽니다. 제외한 영역을 모델이 설명하지 못합니다.",
    "D_FIELD_RANGE_ACTIVE": "자기장 범위 제한이 작동했습니다. 제외된 레코드도 예측과 잔차는 그대로 출력됩니다.",
    "D_ILL_CONDITIONED": (
        "문제의 조건수가 허용값을 넘었습니다. 데이터가 파라미터 조합 하나 이상을 결정하지 못합니다. "
        "이 값을 파라미터보다 먼저 보십시오."
    ),
    "D_BOUND_OVERRIDE": (
        "특정 온도에서 bound 또는 초기값을 덮어썼습니다. "
        "온도에 따라 변하는 bound 는 사람이 파라미터 궤적을 그릴 수 있는 설정입니다."
    ),
    "D_PRIORS_ACTIVE": "이 soft prior 가 작동했습니다. 결과는 이 prior 가 함께 빚은 것입니다.",
    "D_PRIORS_DISABLED": "--no-priors 로 soft prior 를 모두 껐습니다. 선언된 값은 그대로 두고 이번 실행에서만 무시합니다.",
    "D_HARMONIC_LADDER": (
        "이동도가 정수배 사다리를 이루고, 가중치가 단조 감소하며, 부호가 모두 같습니다. "
        "여러 밴드가 아니라 비원형 궤도 하나일 수 있습니다. 이 데이터는 둘을 구별하지 못합니다."
    ),
    "D_PARITY_VIOLATION": (
        "대칭화 전에 이 채널이 반대 패리티 성분을 상당량 담고 있었습니다. "
        "전압 접점이 정확히 마주 보지 않아 다른 채널이 혼입된 것이 흔한 원인입니다. "
        "대칭화가 제거하지만, 크기는 시료와 접점에 대한 증거입니다."
    ),
    "D_SINGLE_POLARITY": (
        "자기장 한쪽 극성만 있어 패리티 위반을 측정할 수 없었습니다. "
        "채널 혼입이 있더라도 그대로 남아 있고, 대칭화도 할 수 없습니다."
    ),
    "D_SPECTRUM_AMBIGUOUS": (
        "이 부호의 봉우리 개수가 정규화 세기에 따라 두 가지 이상으로 안정합니다. "
        "데이터가 두 해석을 모두 허용한다는 뜻이므로 봉우리 개수를 밴드 개수로 "
        "인용하지 마십시오. spectrum_stability_<T>K.csv 를 보십시오."
    ),
    "D_SPECTRUM_UNRESOLVED": (
        "이 부호의 봉우리 개수가 어느 정규화 세기에서도 안정되지 않습니다. "
        "이 데이터에서 스펙트럼은 이 부호에 대해 아무 개수도 지지하지 않습니다."
    ),
    "D_SPECTRUM_NOISE_UNREACHED": (
        "어떤 정규화 세기도 데이터를 선언된 잡음까지 맞추지 못했습니다. "
        "작동 중인 세기는 불일치 원리가 고른 값이 아니라 검토한 것 중 가장 작은 값이고, "
        "스펙트럼의 모양은 잡음이 아니라 모델이 놓친 것이 만들었습니다."
    ),
    "D_SPECTRUM_NEGATIVE_PART": (
        "분리된 전도도가 어딘가에서 부호를 잃었습니다. 전도도는 그럴 수 없으므로, "
        "Lorentzian 확장이 데이터를 설명하지 못했거나 자기장 범위가 확장이 필요로 한 "
        "이동도를 구속하지 못한 것입니다. 이 부호의 carrier 값은 인용하지 마십시오."
    ),
    "D_SPECTRUM_EXTENSION_UNDERFIT": (
        "Lorentzian 확장의 잔차가 잡음보다 훨씬 큽니다. 항의 개수가 데이터에 있는 "
        "서로 다른 이동도 수보다 적다는 뜻이며, 이후 단계 전체가 그 부족을 물려받습니다. "
        "spectrum.lorentzian_terms 를 늘리십시오. 높게 잡는 쪽은 대가가 없습니다."
    ),
    "D_SPECTRUM_EXTENSION_SATURATED": (
        "Lorentzian 확장의 항 하나가 선언된 이동도 범위의 끝에 붙었습니다. "
        "그 항의 위치는 데이터가 아니라 spectrum.mu_min_cm2Vs / mu_max_cm2Vs 가 정한 것입니다."
    ),
    "D_SPECTRUM_EXTENSION_MULTIMODAL": (
        "Lorentzian 확장의 시작점 중 절반 미만만 같은 해에 도달했습니다. "
        "이 확장은 여러 해 중 하나를 고른 것이므로, 항별 값을 개별적으로 읽지 마십시오. "
        "spectrum.lorentzian_multi_start 를 늘려 확인하십시오."
    ),
    "D_SPECTRUM_ROUNDTRIP": (
        "스펙트럼이 읽어낸 carrier 를 다시 Drude 모형에 넣었을 때 측정을 재현하지 "
        "못합니다. 이 값들을 밀도와 이동도로 인용하지 마십시오. 초기값으로만 쓰고, "
        "인용할 수치는 그 초기값으로 돌린 직접 fit 에서 가져오십시오. "
        "rhoxy 쪽이 먼저 어긋나는 것이 보통입니다. 밀도가 sigma_xx(0) 만으로 "
        "정해지므로 Hall 채널에는 그것을 붙드는 것이 없기 때문입니다."
    ),
    "D_SPECTRUM_UNCONSTRAINED": (
        "Lorentzian 확장의 비음수 제약을 껐습니다. 논문 방법을 그대로 재현하는 설정이지만, "
        "이동도가 거의 같은 두 항이 서로 상쇄하는 큰 가중치를 가질 수 있고 그것은 "
        "적합 품질로는 보이지 않습니다. 결과가 시작점 개수에 따라 달라질 수 있습니다."
    ),
    "D_INTERVAL_LOWER_BOUND": (
        "이 온도의 잔차가 구조적이므로, 보고된 구간은 잔차 재샘플링만 덮습니다. "
        "그 잔차를 만든 모델 부족은 덮지 않습니다. 구간은 하한으로 읽으십시오."
    ),
}

MESSAGES: dict[str, str] = {**ERROR_MESSAGES, **DIAGNOSTIC_MESSAGES}


def describe(code: str, detail: dict[str, Any] | None = None) -> str:
    """코드에 대응하는 한국어 문구와, 있으면 기계 판독 상세를 함께 돌려준다.

    상세는 번역하지 않는다. 경로 이름, 컬럼 이름, 숫자는 사용자가 설정 파일과
    데이터에서 그대로 마주치는 문자열이므로, 그대로 보여 주는 편이 찾기 쉽다.
    """
    text = MESSAGES.get(code, "알 수 없는 코드입니다.")
    if not detail:
        return f"[{code}] {text}"
    rendered = ", ".join(f"{key}={value!r}" for key, value in sorted(detail.items()))
    return f"[{code}] {text}\n         {rendered}"


# FR-092. Every label of the workflow report page. The generator in
# `workflow_report.py` stays ASCII and takes this table as an argument.
REPORT_TEXT = {
    "title": "다중밴드 분석 보고서",
    "lede": "온도마다 몇 개의 carrier 가 데이터로 결정되는지를 먼저, 그 값과 곡선을 그다음에 보여줍니다.",
    "count_notice_data": "개수 규칙 data: 스펙트럼 봉우리 수는 상한으로만 쓰고, 데이터가 요구하고 결정하는 가장 작은 조합을 fit 으로 골랐습니다. carrier 개수는 이 sweep 을 설명하는 데 필요한 전도 채널 수의 하한이고, 값은 그 채널들의 유효 밀도와 유효 이동도입니다.",
    "count_notice_peaks": "개수 규칙 peaks: carrier 개수를 스펙트럼 봉우리 수로 고정하고 fit 과 스펙트럼을 수렴할 때까지 되먹였습니다 (Liu et al. 의 절차). 이 개수는 데이터가 아니라 봉우리 찾기가 정한 것이므로, 자기수송 밖의 근거가 있을 때만 인용하십시오. 등급과 통과 못 한 시험이 파라미터가 결정되었는지를 말합니다.",
    "no_answer": "답 없음: 스펙트럼에 봉우리가 없거나 fit 이 예산 안에 끝나지 않았습니다",
    "verdict_heading": "1. 온도별 판정",
    "verdict_intro": "숫자보다 이것을 먼저 보십시오. 등급은 파라미터를 어디까지 믿어도 되는지, 통과 못 한 시험은 왜 그런지를 말합니다. 행을 누르면 아래 그림이 그 온도로 바뀝니다.",
    "curves_heading": "2. 측정과 fit",
    "curves_intro": "점은 측정, 선은 선택된 carrier 들로 계산한 모형입니다.",
    "params_heading": "3. 온도에 따른 파라미터",
    "params_intro": "세로축은 로그입니다. 온도마다 조합이 다르면 선이 이어지지 않으니, 계열을 볼 때는 개수를 고정하십시오.",
    "cands_heading": "4. 시도한 모든 조합",
    "cands_intro": "선택된 조합이 강조되어 있습니다. 예산을 넘긴 조합은 퇴화된 fit 이며 선택될 수 없습니다.",
    "col_T": "T (K)", "col_combo": "조합", "col_grade": "등급",
    "col_r2xx": "R² ρxx", "col_r2xy": "R² ρxy", "col_cond": "조건수",
    "col_failed": "통과 못 한 시험", "col_escaped": "창 이탈",
    "col_name": "carrier", "col_kind": "종류", "col_density": "밀도 (cm^-3)",
    "col_mobility": "이동도 (cm²/Vs)", "col_share": "전도 분담",
    "col_holes": "hole", "col_electrons": "electron", "col_rmse": "RMSE ρxx",
    "col_spread": "해의 퍼짐", "col_bound": "경계", "col_expired": "예산 초과", "col_starts": "완주 출발점",
    "col_seconds": "초",
    "grade_A": "A: 파라미터가 결정됨", "grade_B": "B: 추세는 쓸 수 있고 자릿수는 못 씀. 구간을 함께 인용",
    "grade_C": "C: 모양만", "grade_D": "D: 결정 안 됨", "grade_dash": "spectrum 모드에는 등급이 없습니다",
    "gate_fits": "데이터를 못 맞춤", "gate_reproducible": "재현 안 됨",
    "gate_earns": "일하지 않는 carrier", "gate_free": "경계에 붙음",
    "none": "없음", "yes": "예", "no": "아니오",
    "hole": "hole", "electron": "electron",
    "rhoxx": "ρxx (μΩ·cm)", "rhoxy": "ρxy (μΩ·cm)", "field": "B (T)",
    "measured": "측정", "fitted": "모형",
    "density": "밀도 (cm^-3)", "mobility": "이동도 (cm²/Vs)", "temperature": "온도 (K)",
    "no_curve": "그릴 곡선이 없습니다.", "no_candidates": "이 모드는 조합을 탐색하지 않습니다.",
    "out_of_budget": "예산 초과",
    "col_stop": "루프 종료",
    "col_undetermined": "더 잘 맞는 미결정 조합",
    "col_island": "이웃 양쪽이 공유하는 개수(섬)",
    "col_fit_ratio": "잔차/노이즈 ρxx / ρxy",
    "beyond_mark": "(MSA 상한 넘음)",
    "undetermined_times": "배 작은 잔차, 재현 안 됨",
    "island_times": "배 커지는 잔차",
    "stop_converged": "수렴", "stop_max_iterations": "반복 한도",
    "stop_fit_out_of_budget": "fit 이 예산 초과",
    "stop_no_peaks": "봉우리 없음",
    # FR-110. The spectrum that bounded the search.
    "spectrum_show": "이 온도의 이동도 스펙트럼 보기 (개수 상한과 창을 정한 근거)",
    "spectrum_note": "세로축은 스펙트럼이 푸는 규격화된 가중치이며 carrier 밀도가 아닙니다. 봉우리 높이를 carrier 개수나 농도로 읽지 마십시오. 가로축은 로그입니다. 점선은 찾은 봉우리, 음영은 그것을 바꿔 만든 이동도 창입니다.",
    "spectrum_weight": "규격화된 가중치",
    "spectrum_window": "이동도 창",
    "spectrum_peak": "봉우리",
    "no_spectrum": "이 온도에는 스펙트럼이 없습니다.",
    # FR-109. How far the band is from a smooth series.
    "roughness_label": "이 구간의 거칠기",
    "roughness_note": "결합 penalty 가 재는 것과 같은 양이며, 파라미터가 온도에 따라 얼마나 휘는지입니다. 작을수록 하나의 계열로 읽기 쉽습니다.",
    "roughness_none": "거칠기는 온도 3개 이상이고 carrier 개수가 같은 구간에서만 잴 수 있습니다.",
    "interval_notice": "등급과 해의 퍼짐은 모형 안에서의 재현성입니다. 모형 오차는 들어 있지 않습니다.",
    "effective_mobility": "추출된 이동도는 해당 전도 채널의 유효 이동도이며, 특정 Fermi pocket 의 미시적 이동도와 같지 않습니다.",
}
