// Every Korean sentence on the page. FR-105.
//
// This file also defines the *shape* of a language: `en.ts` is typed against
// it, so a label added here and not there fails the build rather than showing
// a Korean sentence to an English reader.

import type { Progress } from '../api'

export const L = {
  title: 'Multiband Hall 분석',
  lede: 'ρxx(B) 와 ρxy(B) 로부터, 데이터가 몇 개의 carrier 를 결정하는지 먼저 판정하고 그 밀도와 이동도를 구합니다.',

  language_label: '언어',
  language_ko: '한국어',
  language_en: 'English',

  step_files: '1. 파일',
  step_mapping: '2. 열 지정',
  step_settings: '3. 절차',
  step_run: '4. 분석',
  step_results: '5. 결과',
  step_adjust: '6. 조정과 확정',
  // FR-112. 절차의 답은 5단계에 그대로 두고, 손보는 일은 여기서 합니다.
  adjust_heading: '6. 사후 조정과 확정',
  adjust_lede: '절차가 어느 온도에서 물리적으로 말이 안 되는 곳에 앉았거나, 계열이 하나로 읽히지 않을 때 여기서 손봅니다. 5단계의 답은 지워지지 않습니다.',
  adjust_back: '5. 결과로 돌아가기',
  adjust_moved: '밴드 개수를 바꿔 다시 맞추기와, 온도에 따라 매끄럽게 묶기는 6단계로 옮겼습니다. 거기서 여러 온도를 차례로 손보고, 만족스러우면 확정해서 내려받습니다.',
  adjust_go: '6. 조정과 확정으로',
  adjust_pick: '어느 온도부터 손볼지 고르십시오',
  adjust_working: '지금까지 쌓인 조정',
  adjust_nothing: '아직 아무것도 조정하지 않았습니다. 손대지 않은 온도는 절차의 답이 그대로 남습니다.',
  adjust_now: '지금 서 있는 답',
  adjust_source: '무엇으로',
  adjust_undo: '되돌리기',
  confirm_heading: '확정',
  confirm_intro: '확정은 화면에 있는 숫자를 모으는 것이 아니라, 쌓인 조정이 결국 무엇을 뜻하는 설정인지로 절차를 다시 돌립니다. 그래서 몇 분 걸립니다. 그 대신 내려받는 표가 같은 실행 하나를 설명하고, 함께 들어 있는 설정 문서를 명령줄에서 돌리면 같은 답이 나옵니다.',
  confirm_settings: (counts: number, bands: number) =>
    `온도 ${counts}개의 개수를 고정하고, 구간 ${bands}개에 결합을 겁니다.`,
  confirm_run: '확정하고 다시 돌리기',
  confirm_running: '확정한 설정으로 다시 도는 중…',
  confirm_stopped: '멈췄습니다. 일부 온도만 확정된 답은 확정된 답이 아니므로 아무것도 남기지 않았습니다.',
  confirm_done: '확정했습니다. 아래 파일은 이 확정된 답의 것이고, 절차의 원래 답은 5단계에서 그대로 내려받을 수 있습니다.',
  confirm_download_tables: '표와 설정 문서 (.zip)',

  offline_heading: '프로그램이 응답하지 않습니다',
  offline_body: (address: string) =>
    `이 창은 ${address} 주소를 보고 있는데, 그 주소에서 답하는 프로그램이 없습니다. 프로그램이 꺼져 있거나, 이 창이 이전에 실행했던 프로그램의 창입니다.`,
  offline_what: 'MultibandHall.exe 를 실행하십시오. 프로그램이 뜨면 이 창은 스스로 돌아옵니다. 돌아오지 않으면 새로 열리는 창을 쓰십시오.',
  offline_lost: '서버가 다시 뜨면 올려 두었던 파일은 남아 있지 않습니다. 파일부터 다시 올리게 됩니다.',
  offline_retry: '지금 다시 확인',
  offline_checking: '확인하는 중…',

  col_island: '이웃 양쪽이 공유하는 개수(섬)',
  island_cell: (label: string, times: string) => `${label}, 잔차 ${times}배`,
  island_intro: '"섬" 열은 양쪽 이웃 온도가 모두 같은 개수인데 이 온도만 carrier 가 더 많은 경우를 가리킵니다. 옆의 배수는 그 온도를 이웃의 개수로 붙들었을 때 잔차가 몇 배가 되는지입니다. 판정은 바꾸지 않았습니다 — 진짜 전이인지 피팅이 만든 것인지는 읽는 사람이 판단할 부분입니다. 붙들어 보려면 아래 "밴드 개수를 바꿔 다시 맞추기" 를 쓰십시오.',

  recount_heading: '밴드 개수를 바꿔 다시 맞추기',
  recount_intro: '절차가 고른 개수 대신 다른 개수로 다시 맞춥니다. 분석 전체를 다시 돌리지 않고 고른 온도만 다시 맞춥니다. 온도 구간을 지정하면 그 구간 전체를 같은 개수로 맞추므로 n(T)·μ(T) 를 하나의 carrier 집합으로 그릴 수 있습니다. 원래 판정은 그대로 남고, 개수를 바꾼 대가가 잔차 배수로 나옵니다. 배수가 1보다 작으면 고른 개수가 더 잘 맞는다는 뜻이고, 그래도 절차가 그것을 고르지 않은 이유는 아래 후보 표의 시험들에 있습니다.',
  recount_holes: 'hole 개수',
  recount_electrons: 'electron 개수',
  recount_from: '시작 온도',
  recount_to: '끝 온도',
  recount_chosen: (n: number) => `온도 ${n}개에 적용합니다.`,
  recount_run: '다시 맞추기',
  recount_running: '맞추는 중…',
  recount_original: '절차의 판정',
  // FR-109. 다시 맞춘 결과가 그림과 표에도 나란히 나옵니다.
  recount_shown: '아래 그림과 carrier 표에 이 결과가 절차의 답과 나란히 그려집니다.',
  recount_clear: '그림에서 지우기',
  refit_showing: (what: string, where: string) =>
    `다시 맞춘 결과(${what}, ${where})를 절차의 답과 함께 보고 있습니다. 절차의 답은 지워지지 않습니다.`,
  trend_procedure: '절차',
  trend_refit: '다시 맞춤',
  trend_coupled: '매끄럽게',
  trend_adjusted: '조정 후',
  col_source: '출처',
  recount_result: '다시 맞춘 결과',
  recount_col_price: '잔차 배수',

  spectrum_show: '이동도 스펙트럼 (MSA) 보기',
  spectrum_intro: '1단계에서 계산한 이동도 스펙트럼입니다. 밴드 개수의 상한과 이동도 범위가 여기서 나왔습니다. 세로축은 스펙트럼이 푸는 정규화된 가중치이지 carrier 밀도가 아닙니다 — 봉우리 하나가 전도의 몇 분의 몇을 지는지를 나타냅니다. 봉우리가 뚜렷이 갈라지는지, 아니면 어깨처럼 붙어 있는지를 보십시오. 붙어 있으면 그 둘을 따로 세우기 어렵다는 뜻입니다.',
  spectrum_hole: 'hole',
  spectrum_electron: 'electron',
  spectrum_peak_hole: 'hole 봉우리',
  spectrum_peak_electron: 'electron 봉우리',
  spectrum_x: '이동도 (cm²/Vs)',
  spectrum_y: '가중치 (정규화)',
  spectrum_title: (T: number) => `${T} K 이동도 스펙트럼`,
  spectrum_window: (kind: string, low: string, high: string) =>
    `${kind} 탐색 창: ${low} ~ ${high} cm²/Vs`,
  spectrum_none: '이 온도에는 스펙트럼이 없습니다.',

  smooth_heading: '온도에 따라 매끄럽게',
  smooth_intro: '구간 전체를 한 문제로 풀면서, 파라미터가 온도에 따라 매끄럽게 변하도록 제약을 걸 수 있습니다. 공짜가 아닙니다 — 매끄러움은 잔차로 사는 것이고, 온도마다 얼마를 냈는지 보여 드립니다. 대가가 크다면 그 구간에서 모형이 실제로 바뀐다는 증거이니, 더 세게 누를 이유가 아니라 구간을 나눌 이유로 읽으십시오.',
  smooth_label: '매끄럽게',
  smooth_none: '하지 않음',
  smooth_weak: '약하게',
  smooth_normal: '보통',
  smooth_strong: '강하게',
  smooth_needs: '온도가 3개 이상이어야 합니다. 곡률은 점 셋이 있어야 정해집니다.',
  smooth_col: '매끄럽게 맞춘 결과',
  smooth_run: '매끄럽게 맞추기',
  smooth_running: '구간을 함께 맞추는 중…',
  smooth_stopped: '멈췄습니다. 반만 묶인 구간은 매끄러운 계열이 아니므로 결합은 아무것도 남기지 않습니다. 다시 맞춘 결과는 그대로 있습니다.',
  smooth_ask: (n: number) => `다시 맞춘 온도 ${n}개에 결합을 걸 수 있습니다.`,
  smooth_elapsed: (seconds: string, budget: string) =>
    `${seconds}초 지났습니다 (예산 ${budget}초). 구간 전체가 한 번의 계산이라 온도 단위로는 셀 수 없습니다.`,
  smooth_long_band: (n: number) =>
    `온도 ${n}개는 긴 구간입니다. 결합은 구간이 길어질수록 급격히 비싸집니다 — 온도 8개가 몇 분이면 13개는 훨씬 더 걸립니다. 나눠서 거는 편이 빠르고, 보통 읽기도 더 낫습니다.`,
  recount_stopped: '멈췄습니다. 구간이 반만 고정되면 그것도 계열이 아니므로 아무것도 남기지 않았습니다.',
  recount_unheld: (list: string) => `고른 개수로 맞추지 못한 온도: ${list}. 예산 안에서 어떤 출발점도 끝나지 않았습니다. 이 온도들은 절차의 판정이 그대로 남아 있고, 아래 조정 목록에도 들어가지 않습니다.`,
  roughness_label: '구간의 거칠기',
  roughness_none: '온도 3개 이상이고 개수가 같은 구간에서만 잴 수 있습니다.',
  roughness_note: (value: string) =>
    `이 구간의 거칠기는 ${value} 입니다. 파라미터가 온도에 따라 얼마나 휘는지를, 제약이 실제로 줄이려는 양 그대로 잰 값입니다. 작을수록 하나의 계열로 보기 좋습니다.`,
  smooth_done: (strength: string, before: string, after: string) =>
    `${strength} 로 맞췄습니다. 거칠기 ${before} → ${after}. 온도마다 치른 잔차는 오른쪽 열에 있습니다.`,

  files_heading: '측정 파일 올리기',
  files_intro: '온도 하나당 파일 하나여도, 여러 온도가 한 파일에 들어 있어도 됩니다. 파일은 이 컴퓨터 밖으로 나가지 않습니다.',
  files_drop: '파일을 이 페이지 아무 곳에나 끌어다 놓거나, 여기를 눌러 고르십시오',
  files_formats: 'CSV·TXT·DAT (쉼표·세미콜론·탭·공백 구분, 소수점 쉼표, UTF-8·CP949·UTF-16). ρxx 와 ρxy 가 따로 된 파일도 됩니다. Excel 파일(.xlsx)은 CSV 로 저장해서 올려 주십시오.',
  files_pick_folder: '폴더째 고르기',
  files_skipped: (n: number) => `표 파일(CSV·TXT·DAT)이 아닌 파일 ${n}개는 건너뛰었습니다.`,
  files_temperatures: (ts: number[]) =>
    ts.length <= 4 ? ts.map((t) => `${t} K`).join(', ') : `${ts[0]}–${ts[ts.length - 1]} K, ${ts.length}개 온도`,
  files_conflict: (one: string, others: string[], temps: string[]) =>
    `${one} 와 ${others.length > 3 ? `${others.slice(0, 3).join(', ')} 외 ${others.length - 3}개` : others.join(', ')} 가 같은 온도(${temps.length > 4 ? `${temps[0]}–${temps[temps.length - 1]}` : temps.join(', ')})의 같은 측정을 담고 있습니다. 같은 데이터를 두 번 올린 것이면 한쪽만 남기십시오.`,
  files_remove_one: (name: string) => `${name} 빼기`,
  files_remove_others: (n: number) => `나머지 ${n}개 빼기`,
  files_conflict_block: '겹치는 파일을 정리해야 다음으로 넘어갈 수 있습니다.',
  files_uploading: '읽는 중…',
  files_listed: '올린 파일',
  files_remove: '빼기',
  files_next: '열 지정으로',

  mapping_heading: '각 파일의 열 지정',
  mapping_intro: '프로그램이 추측한 대응입니다. 확인하고, 틀렸으면 고치십시오. 모든 파일이 완전히 지정되기 전에는 분석을 시작하지 않습니다.',
  mapping_skipped: (n: number) => (n > 0 ? `머리글 위의 ${n}줄은 건너뛰었습니다.` : '건너뛴 줄 없음'),
  mapping_rows: (shown: number, total: number) => `처음 ${shown}행 / 전체 ${total}행`,
  mapping_B: '자기장 열',
  mapping_rhoxx: 'ρxx 열',
  mapping_rhoxy: 'ρxy 열',
  mapping_T_source: '온도',
  mapping_T_from_column: '열에서 읽기',
  mapping_T_value: '직접 입력 (K)',
  mapping_T_column: '온도 열',
  mapping_field_unit: '자기장 단위',
  mapping_resistivity_unit: '비저항 단위',
  mapping_choose: '— 고르기 —',
  mapping_missing: (what: string) => `아직 지정 안 됨: ${what}`,
  mapping_T_from_name: (T: number) => `파일 이름에서 ${T} K 를 읽었습니다.`,
  mapping_back: '파일로',
  mapping_next: '절차 확인으로',

  settings_heading: '분석 절차',
  settings_intro: '파일마다 온도별로 아래 순서로 분석합니다.',
  procedure_steps: [
    '이동도 스펙트럼(MSA)으로 hole·electron 각각의 밴드 개수 상한과 carrier 밀도·이동도의 범위를 정합니다.',
    '그 범위 안에서 multiband Drude 로 조합을 fit 해, 데이터를 맞추고 출발점을 바꿔도 같은 답이 나오는 가장 작은 조합을 고릅니다.',
    '밴드를 하나 더 늘린 조합이 잔차를 뚜렷이(2배 넘게) 줄이면 늘리고, 그렇지 않으면 거기서 확정합니다. carrier 를 늘리면 잔차는 늘 조금씩 줄어들기 때문에, 그 정도의 개선은 밴드를 늘릴 근거가 되지 않습니다.',
  ],
  procedure_claim: '결과의 밴드 개수는 이 데이터를 설명하는 데 필요한 전도 채널 수의 하한이고, 밀도·이동도는 그 채널의 유효값입니다. 실제 Fermi pocket 은 더 많을 수 있으며, 그것은 양자진동 같은 자기수송 밖의 근거가 필요합니다.',
  sym_heading: '데이터 대칭화',
  sym_intro: '켜면 측정값을 짝·홀 부분으로 바꿉니다. 묻지 않고 데이터를 바꾸지 않도록 꺼져 있습니다. 패리티 위반은 바꾸기 전에 잽니다.',
  sym_rhoxx: 'ρxx 를 B 에 대해 대칭화 (짝수 부분)',
  sym_rhoxy: 'ρxy 를 B 에 대해 반대칭화 (홀수 부분)',
  prelim_heading: '예비 fit 모형',
  prelim_intro: '스펙트럼의 잡음 수준은 예비 fit 의 잔차에서 정합니다. 따로 주지 않으면 hole 2개 + electron 2개, 출발 이동도 10⁴ 와 10³ cm²/Vs 인 일반 모형을 씁니다. 이 모형은 잡음 수준을 재는 데만 쓰이고 답이 아닙니다 — 최종 carrier 개수와 이동도는 스펙트럼이 준 상한 안에서 다시 찾으므로, 이 출발값이 이 시료에 맞지 않더라도 답이 그쪽으로 끌려가지 않습니다. 이 프로젝트의 12개 sweep 에서 정성 들여 고른 모형과 비교했을 때 carrier 상한이 모든 온도에서 같았고 잡음 수준은 3 % 이내였습니다.',
  prelim_document: '설정 문서(JSON)를 대신 쓰기',
  prelim_document_hint: 'carrier 선언과 workflow 설정(예: fixed_counts)을 담은 설정 문서를 붙여 넣으십시오. 열 이름은 프로그램이 채웁니다.',
  prelim_document_invalid: '설정 문서가 올바른 JSON 이 아닙니다.',
  settings_back: '열 지정으로',
  settings_start: '분석 시작',

  run_heading: '분석 중',
  run_stop: '멈추기',
  run_stopping: '멈추는 중… 지금 돌고 있는 fit 하나가 끝나야 멈춥니다 (최대 약 30초).',
  run_elapsed: (s: number) => `${Math.round(s)}초 경과`,

  results_heading: '결과',
  results_stopped: '분석을 멈췄습니다. 멈추기 전에 끝난 온도만 보여 줍니다.',
  results_dropped: (n: number) => `올린 파일에서 ${n}개 행이 분석 전에 빠졌습니다. 온도나 자기장을 읽을 수 없는 행입니다. 온도 하나가 통째로 빠질 수도 있으니 열 지정과 파일을 확인하십시오.`,
  results_failed: '분석이 실패했습니다.',
  results_new: '새 분석',
  results_download_page: '보고서 페이지 받기 (report.html)',
  results_download_tables: '표 받기 (tables.zip)',
  results_seconds: (s: number) => `${Math.round(s)}초 걸림`,
  results_prelim: (list: string) => `예비 fit 모형: ${list}`,
  count_notice_peaks_cli: '개수를 스펙트럼 봉우리 수로 고정한 결과입니다 (명령줄 --count peaks). 자기수송 밖의 근거가 있을 때만 인용하십시오.',
  count_notice_data: '개수 규칙: 데이터로 결정. carrier 개수는 이 sweep 을 설명하는 데 필요한 전도 채널 수의 하한이고, 값은 그 채널들의 유효 밀도와 유효 이동도입니다. 실제 pocket 은 더 많을 수 있습니다.',

  verdict_heading: '1. 온도별 판정',
  verdict_intro: '숫자보다 이것을 먼저 보십시오. 행을 누르면 아래가 그 온도로 바뀝니다.',
  curves_heading: '2. 측정과 모형',
  params_heading: '3. carrier',
  trends_heading: '4. 온도에 따른 파라미터',
  trends_intro: '세로축은 로그입니다. 온도마다 조합이 다르면 계열이 아닙니다 — 개수를 고정하려면 설정 문서의 fixed_counts 를 쓰십시오.',
  cands_heading: '5. 시도한 모든 조합',
  cands_none: '이 모드는 조합을 탐색하지 않습니다.',

  col_T: 'T (K)', col_combo: '조합', col_grade: '등급', col_r2xx: 'R² ρxx', col_r2xy: 'R² ρxy',
  col_cond: '조건수', col_failed: '통과 못 한 시험', col_escaped: '창 이탈', col_stop: '반복 종료',
  col_undetermined: '더 잘 맞는 미결정 조합',
  col_fit_ratio: '잔차/노이즈 ρxx / ρxy',
  beyond_mark: '(MSA 상한 넘음)',
  undetermined: (label: string, ratio: string) => `${label}: 잔차 ${ratio}배 작음, 재현 안 됨`,
  col_name: 'carrier', col_kind: '종류', col_density: '밀도 (cm⁻³)', col_mobility: '이동도 (cm²/Vs)',
  col_share: '전도 분담', col_weakest: '가장 약한 분담', col_holes: 'hole', col_electrons: 'electron', col_rmse: 'RMSE ρxx',
  col_spread: '해의 퍼짐', col_bound: '경계', col_expired: '예산 초과',
  col_starts: '완주 출발점', col_seconds: '초',
  col_quantity: '양', col_value: '값', col_low: '하한', col_high: '상한', col_relative: '상대 1σ',

  grade: { A: 'A: 파라미터가 결정됨', B: 'B: 추세는 쓸 수 있고 자릿수는 못 씀', C: 'C: 모양만', D: 'D: 결정 안 됨', '-': '답 없음' } as Record<string, string>,
  gate: { fits: '데이터를 못 맞춤', reproducible: '재현 안 됨', earns: '일하지 않는 carrier', free: '경계에 붙음' } as Record<string, string>,
  stop: { converged: '수렴', max_iterations: '반복 한도', fit_out_of_budget: 'fit 이 예산 초과', no_peaks: '봉우리 없음' } as Record<string, string>,
  no_answer: '답 없음: 봉우리가 없거나 fit 이 예산 안에 끝나지 않음',
  none: '없음', yes: '예', no: '아니오',
  hole: 'hole', electron: 'electron',
  rhoxx: 'ρxx (μΩ·cm)', rhoxy: 'ρxy (μΩ·cm)', field: 'B (T)', temperature: 'T (K)',
  density: '밀도 (cm⁻³)', mobility: '이동도 (cm²/Vs)',
  measured: '측정', model: '모형',
  no_curve: '그릴 곡선이 없습니다.',

  precise_heading: '정밀 점검 (재샘플링)',
  precise_intro: '고른 온도 하나에 대해 잔차를 재샘플링해 밀도와 이동도의 구간을 구합니다. 수 분 걸립니다.',
  precise_start: (T: number) => `${T} K 정밀 점검 시작`,
  precise_running: (done: number, total: number) => `재샘플 ${done} / ${total}`,
  precise_stopped: '정밀 점검을 멈췄습니다. 일부 재샘플로 만든 구간은 다른 구간이므로 아무것도 남기지 않았습니다.',
  precise_result: (n: number, block: number, seed: number) => `재샘플 ${n}회, 블록 길이 ${block}, seed ${seed}`,
  precise_lower_bound: '이 온도의 잔차에 구조가 있습니다. 아래 구간은 하한입니다.',

  notice_interval: '등급, 해의 퍼짐, 재샘플링 구간은 모형 안에서의 재현성입니다. 모형 오차는 들어 있지 않습니다.',
  notice_mobility: '추출된 이동도는 해당 전도 채널의 유효 이동도이며, 특정 Fermi pocket 의 미시적 이동도와 같지 않습니다.',
  notice_peaks: '스펙트럼의 봉우리는 전도 채널이지 밴드가 아닙니다. 봉우리 개수는 밴드 개수의 상한이지 추정값이 아닙니다.',
}

/** The shape every language must fill. `en.ts` is typed against this. */
export type Labels = typeof L

export const STAGES = {
  prepare: (p: Progress) => `데이터를 읽고 예비 fit 을 하는 중 (온도 ${p.total ?? '?'}개)`,
  spectrum: (_p: Progress, T: string) => `${T}: 이동도 스펙트럼 계산 중`,
  temperature: (_p: Progress, T: string) => `${T}: 분석 시작`,
  search: (p: Progress, T: string, combo: string) =>
    `${T}: 조합 ${combo} fit 중 (상한 ${p.max_holes ?? '?'}h+${p.max_electrons ?? '?'}e)`,
  release: (_p: Progress, T: string, combo: string) => `${T}: 고른 ${combo} 를 창 없이 다시 fit 하는 중`,
  peaks: (p: Progress, T: string, combo: string) =>
    `${T}: 봉우리 수 ${combo} 로 fit, 반복 ${p.iteration ?? ''}회차`,
  fixed: (_p: Progress, T: string, combo: string) => `${T}: 고정된 개수 ${combo} 로 fit 하는 중`,
  smooth: (_p: Progress, T: string) => `${T ? `${T}: ` : ''}구간을 함께 fit 하는 중`,
  resample: (p: Progress, T: string) => `${T}: 재샘플 ${p.done ?? 0} / ${p.total ?? '?'}`,
  done: () => '마무리하는 중',
}

export type Stages = typeof STAGES

export const STAGE_DEFAULT = '시작하는 중'

// FR-105. One message per code; parameters are filled in where the message
// names them. tests/test_app_api.py checks that no code is missing.
export const CODE_MESSAGES = {
  E_UPLOAD_EMPTY: '올린 파일이 없거나 비어 있습니다.',
  E_UPLOAD_UNREADABLE: '{file}: 구분자로 나뉜 텍스트 표로 읽을 수 없습니다.',
  E_UPLOAD_NO_TABLE: '{file}: 숫자 행이 이어지는 표를 찾지 못했습니다. 자기장과 비저항이 열로 나뉜 텍스트 표인지 확인해 주십시오.',
  E_UPLOAD_SPREADSHEET: '{file}: Excel 파일은 바로 읽지 못합니다. Excel 에서 "CSV(쉼표로 분리)" 로 저장한 뒤 올려 주십시오.',
  E_FILE_UNKNOWN: '서버가 이 파일을 더 이상 갖고 있지 않습니다. 파일을 다시 올려 주십시오.',
  E_MAPPING_INCOMPLETE: '{file}: 지정되지 않은 항목이 있습니다 ({missing}). ρxx 와 ρxy 를 다른 파일에서 가져온다면 같은 온도의 짝 파일도 함께 올려 주십시오.',
  E_MAPPING_UNKNOWN_COLUMN: '{file}: "{column}" 열이 파일에 없습니다.',
  E_MAPPING_BAD_UNIT: '{file}: 알 수 없는 단위 {unit}.',
  E_TEMPERATURE_DUPLICATE: '{T_K} K 가 두 파일에 있습니다: {files}. 합치거나 덮어쓰지 않습니다. 하나를 빼 주십시오.',
  E_COUNT_RULE_UNKNOWN: '알 수 없는 개수 규칙 {count}.',
  E_PRECISE_NO_ANSWER: '{T_K} K 에는 재샘플링할 fit 이 없습니다.',
  E_JOB_NOT_FOUND: '이 작업을 찾을 수 없습니다. 프로그램을 다시 켜면 작업은 사라집니다.',
  E_JOB_NOT_FINISHED: '분석이 끝난 뒤에만 할 수 있습니다.',
  E_PRECISE_UNKNOWN_TEMPERATURE: '{T_K} K 는 이 분석에 없습니다.',
  E_RECOUNT_INVALID: 'carrier 개수가 잘못되었습니다. hole 과 electron 을 합쳐 1개 이상 {most}개 이하여야 합니다.',
  E_SMOOTHING_TOO_FEW: '온도 {given}개로는 매끄럽게 맞출 수 없습니다. 곡률을 정하려면 구간에 온도가 {needed}개 이상 있어야 합니다.',
  E_SMOOTHING_UNKNOWN: '매끄럽게 하는 강도가 잘못되었습니다 ({smooth}).',
  E_SMOOTH_NO_BAND: '매끄럽게 맞추기는 이미 끝난 재적합에 대고 요청합니다. 먼저 구간을 고른 개수로 다시 맞춰 주십시오.',
  E_BAND_COUNTS_DIFFER: '구간의 sweep 들이 하나의 carrier 개수를 공유하지 않습니다 ({counts}). 묶을 것이 없으니, 먼저 구간 전체를 같은 개수로 다시 맞춰 주십시오.',
  E_BUDGET_EXPIRED: '결합 fit 이 예산 {seconds}초 안에 끝나지 않아 포기했습니다. 구간을 나누거나 더 짧은 구간으로 해 보십시오 — 구간이 길수록 급격히 비싸집니다.',
  E_CONFIRM_EMPTY: '확정할 조정이 없습니다. 먼저 하나 이상 다시 맞춰 주십시오.',
  E_REQUEST_INVALID: '요청의 형식이 잘못되었습니다 ({fields}).',
  E_INTERNAL: '예상하지 못한 문제가 생겼습니다: {detail}',
  E_NOT_FOUND: '찾는 것이 없습니다.',
  E_NETWORK: '프로그램에 닿지 못했습니다. 프로그램이 꺼져 있거나, 이 창이 이전에 실행했던 프로그램의 창입니다. MultibandHall.exe 를 실행하면 이 창이 스스로 돌아옵니다.',

  E_CONFIG_UNREADABLE: '설정 문서를 읽을 수 없습니다.',
  E_CONFIG_SCHEMA_VERSION: '설정 문서의 schema_version 이 없거나 지원하지 않는 값입니다.',
  E_CONFIG_UNKNOWN_FIELD: '설정 문서에 모르는 항목이 있습니다 ({field}). 오타가 기본값을 조용히 살려 두지 않도록 거부합니다.',
  E_CONFIG_MISSING_FIELD: '설정 문서에 반드시 있어야 할 항목이 없습니다 ({field}).',
  E_CONFIG_BAD_VALUE: '설정 값이 허용 범위를 벗어났습니다 ({field}).',
  E_CONFIG_NO_CARRIERS: '설정 문서에 carrier 를 최소 하나는 선언해야 합니다.',
  E_CONFIG_DUPLICATE_CARRIER: 'carrier 이름이 중복되었습니다.',
  E_CONFIG_BAD_CARRIER_KIND: 'carrier 의 kind 는 electron 또는 hole 이어야 합니다.',
  E_CONFIG_BOUNDS_INVALID: 'bounds 가 잘못되었습니다. min 은 0보다 크고 max 이하여야 합니다.',
  E_CONFIG_INIT_OUT_OF_BOUNDS: '초기값이 bounds 밖에 있습니다.',
  E_CONFIG_UNKNOWN_CARRIER: '선언되지 않은 carrier 이름을 지칭했습니다.',
  E_CONFIG_EMPTY_FIELD_WINDOW: '자기장 창이 어떤 온도에서 레코드를 하나도 남기지 않습니다.',
  E_CONFIG_COUPLING_WITHOUT_GLOBAL: '결합 penalty 나 단조 prior 는 temperature_strategy 가 global_smooth 일 때만 작동합니다.',
  E_CONFIG_BREAK_OUTSIDE_RANGE: 'smoothing 절단선이 측정 온도 범위 밖에 있습니다.',
  E_DATA_UNREADABLE: '합친 데이터를 읽을 수 없습니다.',
  E_DATA_MISSING_COLUMN: '데이터에 필요한 열이 없습니다.',
  E_DATA_EMPTY: '쓸 수 있는 레코드가 하나도 남지 않았습니다. 열 지정과 단위를 확인하십시오.',
  E_DATA_UNDERDETERMINED: '어떤 온도의 데이터 점이 자유 파라미터보다 적습니다.',
  E_FIT_NO_START: '모든 시작점이 실패했습니다.',
  E_FIT_SINGULAR: '전도도 텐서를 역변환할 수 없습니다 (σxx² + σxy² = 0).',
}

export type Codes = keyof typeof CODE_MESSAGES

export const UNKNOWN_CODE = (code: string) => `알 수 없는 오류 (${code})`
