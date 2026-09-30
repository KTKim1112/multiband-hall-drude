"""명령줄. 사람에게 보이는 문장이 나타나는 유일한 곳.

헌법 제IV조와 제VIII조: 라이브러리는 코드를 반환하고, 문구는 여기와
`messages.py` 에만 있다. `tests/test_ascii.py` 가 그것을 강제한다.
"""

from __future__ import annotations

import argparse
import math
import pathlib
import sys
import time

from . import config as config_module
from . import dataio, diagnostics, fitting, report, spectrum, uncertainty
from .core.errors import MbfitError
from .messages import describe


# FR-064. 매 실행마다 나가는 문장. cp949 가 담지 못하는 글자를 쓰지 않는다
# (`tests/test_console_encoding.py` 가 확인한다).
EFFECTIVE_MOBILITY_NOTICE = (
    "추출된 이동도는 해당 전도 채널의 유효 이동도입니다. "
    "특정 Fermi pocket 의 미시적 이동도와 같지 않습니다 ― "
    "불균일한 Fermi 속도와 궤도 곡률을 스칼라 하나로 압축한 값입니다."
)


# FR-076 과 FR-077. 스펙트럼을 낼 때마다 함께 나간다.
SPECTRUM_NOTICE = (
    "스펙트럼의 봉우리는 전도 채널이지 Fermi surface 의 밴드가 아닙니다. "
    "비원형 궤도 하나를 사이클로트론 조화 4개로 읽으면 봉우리 3개가 나오는 것을 "
    "측정했습니다 (research 003 §7). 봉우리 개수는 밴드 개수의 상한이지 추정값이 "
    "아닙니다. "
    "그리고 모든 봉우리는 Lorentzian 확장이 고른 이동도 위에 앉습니다 ― "
    "확장이 허용하지 않은 구조는 스펙트럼도 찾지 못합니다. "
    "carrier 개수를 정하는 것은 여전히 선생님이고, 스펙트럼은 제안만 합니다."
)


def _resilient_console() -> None:
    """콘솔 인코딩이 표현하지 못하는 글자 하나 때문에 죽지 않게 한다.

    한글 Windows 콘솔은 cp949 이고 cp949 에는 U+2014 EM DASH 가 없다. 그런
    글자 하나가 섞이면 `print` 가 UnicodeEncodeError 로 죽는데, 하필
    죽는 자리가 진단을 출력하기 직전이다. 진단은 이 프로그램이 존재하는
    이유이므로, 표현할 수 없는 글자는 대체 문자로 흘려보내고 나머지는 계속
    출력한다. `tests/test_console_encoding.py` 가 애초에 그런 글자가 소스에
    들어오지 못하게 막지만, 못 막았을 때 잃는 것이 크므로 여기서 한 번 더 받는다.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(errors="replace")
        except (ValueError, OSError):
            pass


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mbfit",
        description="Multiband magnetotransport analysis.",
    )
    parser.add_argument("--data", required=True, help="measurement table")
    parser.add_argument("--config", required=True, help="configuration document")
    parser.add_argument("--out", required=True, help="output directory")
    parser.add_argument(
        "--count",
        choices=("data", "peaks"),
        default=None,
        help=(
            "FR-080. 스펙트럼 → multiband fit 절차를 돌리고, carrier 개수를 무엇이 "
            "정할지 고릅니다. data 는 스펙트럼 봉우리 수를 상한으로만 쓰고 데이터가 "
            "결정하는 가장 작은 조합을 고릅니다 (기본). peaks 는 봉우리 수로 개수를 "
            "고정하고 fit 과 스펙트럼을 수렴할 때까지 되먹입니다 (Liu et al. 의 절차). "
            "생략하면 이 절차를 돌리지 않고 설정이 선언한 carrier 를 fit 합니다."
        ),
    )
    parser.add_argument(
        "--symmetrize-rhoxx",
        action="store_true",
        help=(
            "FR-008. rho_xx 를 자기장의 짝부분 [r(B)+r(-B)]/2 로 바꿉니다. "
            "짝이 없는 기록은 sweep 이 감싸면 보간하고, 아니면 그대로 둡니다 "
            "(FR-010). 기본은 꺼짐 ― 프로그램이 데이터를 조용히 바꾸지 않습니다."
        ),
    )
    parser.add_argument(
        "--antisymmetrize-rhoxy",
        action="store_true",
        help=(
            "FR-009. rho_xy 를 자기장의 홀부분 [r(B)-r(-B)]/2 로 바꿉니다. "
            "패리티 위반은 이 단계 **전에** 측정되므로 켜도 증거는 남습니다."
        ),
    )
    parser.add_argument(
        "--no-priors",
        action="store_true",
        help=(
            "disable every soft prior for this run without editing the "
            "configuration (FR-057): the temperature coupling, the monotonic "
            "expectation, the low-field emphasis and the robust loss. The "
            "declared bounds and any field window are left alone."
        ),
    )
    return parser


def run(arguments) -> int:
    started = time.monotonic()

    document = config_module.load_document(arguments.config)

    # FR-008 and FR-009 stay off unless asked for, here as on the page: a
    # program that replaces the measurement with its even and odd parts has
    # changed the data without being asked. The parity violation is measured
    # before the replacement either way, so switching it on hides nothing.
    if arguments.symmetrize_rhoxx or arguments.antisymmetrize_rhoxy:
        preprocess = document.setdefault("preprocess", {})
        if arguments.symmetrize_rhoxx:
            preprocess["symmetrize_rhoxx"] = True
        if arguments.antisymmetrize_rhoxy:
            preprocess["antisymmetrize_rhoxy"] = True
    if arguments.count is not None:
        document.setdefault("workflow", {})["count"] = arguments.count

    declared = config_module.resolve(document)
    effective = config_module.disable_soft_priors(declared) if arguments.no_priors else declared

    # FR-080. A count rule runs the procedure of feature 004 instead of the
    # declared-carrier fit; without one the program behaves as it always has.
    #
    # NR-013. The switch, and only the switch. `workflow.count` has a default,
    # so a document that has been through `resolve` declares it whether or not
    # anyone asked -- and every emitted `resolved_config.json` has been. Reading
    # the document instead sent a declared-carrier run's own emitted
    # configuration into the procedure on the way back, which is the round trip
    # NR-005 exists to protect. A configuration written beside a confirmed
    # answer therefore needs `--count` named alongside it, and the README says
    # so.
    if arguments.count is not None:
        # FR-057. The procedure re-resolves the document for every combination
        # it tries, so it has to be handed the document the switch produced.
        # Handing it the declared one dropped `--no-priors` without a word: the
        # run reported that the priors had been removed and minimised with the
        # robust loss and the low-field emphasis still in force.
        return _run_workflow(
            arguments,
            effective.as_document() if arguments.no_priors else document,
            started)

    dataset = dataio.load_dataset(arguments.data, effective)
    result = fitting.fit_dataset(dataset, effective)
    uncertainties = uncertainty.estimate(result, dataset)
    spectra = spectrum.estimate(result, dataset)
    found = diagnostics.collect(
        result, dataset, declared if arguments.no_priors else None,
        uncertainties, spectra,
    )
    written = report.write_everything(
        result, dataset, found, arguments.out, uncertainties, spectra
    )

    elapsed = time.monotonic() - started
    warnings = [entry for entry in found if entry.severity == diagnostics.WARNING]
    notes = [entry for entry in found if entry.severity == diagnostics.NOTE]

    print(f"온도 {len(result.fits)}개를 {result.strategy} 전략으로 fitting했습니다."
          f"  seed={result.seed}  {elapsed:.1f}초")
    print(f"파일 {len(written)}개를 {pathlib.Path(arguments.out).resolve()} 에 썼습니다.")

    if warnings:
        print(f"\n경고 {len(warnings)}건 ― 파라미터보다 이것을 먼저 보십시오.")
        seen = set()
        for entry in warnings:
            if entry.code not in seen:
                print()
                print(describe(entry.code, None))
                seen.add(entry.code)
            where = ", ".join(f"{k}={v}" for k, v in entry.where.items())
            print(f"    - {where or 'run'}: 측정 {entry.measured}"
                  f"  임계 {entry.threshold}  근거 {entry.threshold_source}")
    else:
        print("\n경고 없음. 그렇더라도 fit 품질은 파라미터 정확도의 증거가 아닙니다.")

    if notes:
        print(f"\n참고 {len(notes)}건: " + ", ".join(sorted({entry.code for entry in notes})))

    # FR-064. 결과가 어떻든 매 실행마다. 이 문장이 빠지면 채널 이동도가
    # pocket 의 미시적 이동도로 인용되고, 그것이 이 숫자들의 정직한 사용과
    # 부정직한 사용을 가르는 지점이다.
    print("\n" + EFFECTIVE_MOBILITY_NOTICE)
    if spectra:
        # FR-073 and FR-074, with every spectrum.
        print("\n" + SPECTRUM_NOTICE)
    print("\n자세한 내용은 diagnostics.csv 를 보십시오.")
    return 0


def _run_workflow(arguments, document, started) -> int:
    """FR-080 to FR-092. 절차를 돌리고, 판정을 숫자보다 먼저 보여준다."""
    from . import workflow, workflow_report
    from .messages import REPORT_TEXT as TEXT

    result = workflow.analyse(arguments.data, document, mode=arguments.count)
    out = pathlib.Path(arguments.out)
    written = workflow_report.write_tables(result, out)
    written.append(workflow_report.write_page(result, out, TEXT))

    elapsed = time.monotonic() - started
    print(f"온도 {len(result.outcomes)}개를 개수 규칙 '{result.mode}' 로 분석했습니다.  {elapsed:.1f}초")
    print(f"파일 {len(written)}개를 {out.resolve()} 에 썼습니다. report.html 을 먼저 여십시오.")
    print()
    # FR-081. 개수를 무엇이 정했는지가 답과 함께 나간다.
    print(TEXT["count_notice_peaks"] if result.mode == "peaks" else TEXT["count_notice_data"])
    print()

    gate = {"fits": TEXT["gate_fits"], "reproducible": TEXT["gate_reproducible"],
            "earns": TEXT["gate_earns"], "free": TEXT["gate_free"]}
    print(f"  {'T(K)':>6}  {'조합':<8} {'잔차/노이즈':>13} {'등급':<4} 판정")
    for item in result.outcomes:
        if not item.carriers:
            verdict = TEXT["no_answer"]
        elif item.failed_gates:
            verdict = "통과 못 함: " + ", ".join(gate.get(g, g) for g in item.failed_gates)
        else:
            verdict = TEXT["grade_" + item.grade] if ("grade_" + item.grade) in TEXT else item.grade
        if item.escaped_window:
            verdict += "  (창 이탈: " + ", ".join(item.escaped_window) + ")"
        if item.undetermined_better:
            # FR-085. 재현되지 않는 더 큰 모형이 더 잘 맞는다는 것은 조용히 넘기지 않는다.
            verdict += (f"  [경고: 결정 안 되는 {item.undetermined_better} 가 "
                        f"잔차 {item.undetermined_ratio:.2f}배 작음]")
        if item.mode == "peaks":
            reason = TEXT.get(f"stop_{item.stop_reason}", item.stop_reason)
            verdict += f"  ({TEXT['col_stop']}: {reason}, {item.iterations}회)"
        if item.beyond_bound:
            verdict += "  " + TEXT["beyond_mark"]
        if item.island_label:
            # FR-090. 양쪽 이웃이 공유하는 개수보다 carrier 가 많은 온도. 판정은
            # 그대로 두고, 이웃의 개수로 붙들었을 때의 대가만 알린다. 전이인지
            # 인공물인지는 읽는 사람이 판단한다.
            verdict += (f"  [섬: 이웃은 {item.island_label}, 그것으로 붙들면 "
                        f"잔차 {item.island_price:.2f}배]")
        ratio = (f"{item.residual_over_noise_xx:5.1f} / {item.residual_over_noise_xy:5.1f}"
                 if item.carriers else "")
        print(f"  {item.T_K:>6g}  {item.label:<8} {ratio:>13} {item.grade:<4} {verdict}")

    # FR-107, FR-109. The page of feature 005 can measure how far a band is
    # from a smooth series; a reader of the command line gets the same number
    # for the band they ran, from the same routine.
    print()
    roughness = workflow.roughness_of(result.outcomes)
    if math.isfinite(roughness):
        print(f"{TEXT['roughness_label']}: {roughness:.3f}. {TEXT['roughness_note']}")
    else:
        print(TEXT["roughness_none"])

    print()
    print(EFFECTIVE_MOBILITY_NOTICE)
    return 0


def main(argv=None) -> int:
    _resilient_console()
    arguments = build_parser().parse_args(argv)
    try:
        return run(arguments)
    except MbfitError as error:
        print(describe(error.code, error.detail), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
