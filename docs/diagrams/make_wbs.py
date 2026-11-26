# baby-care-vision-platform WBS 일정표 (HTML → PNG)
# 사용: python3 make_wbs.py      → wbs.html
#       python3 make_wbs.py en   → wbs.en.html
# PNG: node render_html.js wbs wbs.en
import sys
from html import escape as E

EN = len(sys.argv) > 1 and sys.argv[1] == 'en'
def T(ko, en):
    return en if EN else ko

DAYS = [('11/25', T('수', 'Wed')), ('11/26', T('목', 'Thu')), ('11/27', T('금', 'Fri'))]
SLOTS = [T('오전', 'AM'), T('오후', 'PM'), T('저녁', 'Eve')]
N = len(DAYS) * len(SLOTS)   # 칸 번호: 0 = 11/25 오전 … 8 = 11/27 저녁

PHASE = {
    1: ('#e8f0fb', '#9db4d8'),
    2: ('#eaf3e3', '#9cc283'),
    3: ('#f6ece0', '#dbb68a'),
    4: ('#efe9f7', '#b9a3dd'),
    5: ('#e3f2f4', '#84c3cc'),
}
DONE, PROG, PLAN, GOAL = 'done', 'prog', 'plan', 'goal'

# (단계, 수행내용, 상세수행내용, 담당, 칸 목록, 상태, 비고)
rows = [
    (1, T('기획', 'Planning'), T('요청서 v2 ~ v4 · 화면 · API 계약', 'Request doc v2 ~ v4 · screen · API contract'), 'PM', [0, 1], DONE, ''),
    (1, T('기획', 'Planning'), T('역할 분담 · 공통 규칙 10개', 'Roles · 10 common rules'), 'PM', [1], DONE, ''),
    (1, T('기획', 'Planning'), T('저장소 · 브랜치 보호 · CONTRIBUTING', 'Repo · branch protection · CONTRIBUTING'), 'PM', [1], DONE, ''),
    (2, T('백엔드', 'Backend'), T('Django 프로젝트 · settings', 'Django project · settings'), T('백엔드 2', 'Backend 2'), [1], DONE, ''),
    (2, T('백엔드', 'Backend'), 'AnalysisPageView', T('백엔드 1', 'Backend 1'), [2], DONE, ''),
    (2, T('백엔드', 'Backend'), T('Analysis 모델 · URL · AI_SERVICE_URL', 'Analysis model · URLs · AI_SERVICE_URL'), T('백엔드 2', 'Backend 2'), [3], DONE, ''),
    (2, T('백엔드', 'Backend'), 'AnalysisSerializer · AnalysisAPIView', T('백엔드 1', 'Backend 1'), [3], DONE, ''),
    (2, 'AI', T('uv 환경 · 의존성', 'uv environment · deps'), 'AI 2', [1], DONE, ''),
    (2, 'AI', T('모델 로드 · 규격 검증 · lifespan', 'Model loading · validation · lifespan'), 'AI 1', [1, 2, 3], DONE, ''),
    (2, 'AI', T('포즈 추적 → 특징 → RF 판정', 'Pose tracking → features → RF decision'), 'AI 1', [3], DONE, ''),
    (2, 'AI', 'GET /health · POST /predict', 'AI 2', [4], DONE, ''),
    (2, T('프론트', 'Front'), 'index.html', T('프론트 1', 'Front 1'), [4], DONE, ''),
    (2, T('프론트', 'Front'), 'analysis.js', T('프론트 2', 'Front 2'), [4], DONE, ''),
    (3, T('통합 · 리뷰', 'Integration'), T('PR #1 리뷰 · 머지', 'PR #1 review · merge'), 'PM', [2], DONE, ''),
    (3, T('통합 · 리뷰', 'Integration'), T('PR #2 ~ #5 리뷰 · 머지', 'PR #2 ~ #5 review · merge'), 'PM', [4], DONE, ''),
    (3, T('통합 · 리뷰', 'Integration'), T('전체 흐름 확인 (화면 → AI → DB)', 'End-to-end check (page → AI → DB)'), T('전원', 'All'), [4], DONE, ''),
    (4, T('최적화', 'Optimisation'), T('AI main.py 중복 정리 (PR #6)', 'AI main.py clean-up (PR #6)'), 'AI 2', [5], DONE, ''),
    (4, T('최적화', 'Optimisation'), T('구조표 = 실제 파일 점검', 'Structure table = real files'), 'PM', [5, 6], PLAN, ''),
    (5, T('문서', 'Docs'), T('README 한/영 · 아키텍처 · 파이프라인', 'README ko/en · architecture · pipeline'), 'PM', [5], DONE, ''),
    (5, T('문서', 'Docs'), T('WBS 일정 · README 보완', 'WBS schedule · README updates'), 'PM', [5, 6], PROG, ''),
    (5, T('발표', 'Demo'), T('발표 준비 · 시연 리허설', 'Presentation prep · demo rehearsal'), T('전원', 'All'), [6, 7], PLAN, ''),
    (5, T('발표', 'Demo'), T('최종 완료 · 발표', 'Final · presentation'), T('전원', 'All'), [7], GOAL, ''),
]
PH_NAME = {1: T('1. 착수', '1. Kick-off'), 2: T('2. 개발', '2. Build'), 3: T('3. 통합', '3. Integrate'),
           4: T('4. 최적화', '4. Optimise'), 5: T('5. 문서 · 발표', '5. Docs · demo')}
STATUS = {DONE: T('완료', 'Done'), PROG: T('진행', 'In progress'), PLAN: T('예정', 'Planned'), GOAL: T('목표', 'Goal')}
TODAY = [3, 4, 5]   # 11/26 칸 (작성일)

def cells(slots, phase, st):
    out = []
    for i in range(N):
        cls = 'g'
        style = ''
        if i in slots:
            if st == GOAL:
                style = 'background:#e03a3a'
            elif st == PLAN or (st == PROG and i != slots[0]):
                style = 'background:#c9ced6'
            else:
                style = f'background:{PHASE[phase][1]}'
        sep = ' d' if i % 3 == 2 else ''
        out.append(f'<td class="c{sep}" style="{style}"></td>')
    return ''.join(out)

body = []
# 단계 · 수행내용 rowspan 계산
for idx, (ph, task, detail, owner, slots, st, note) in enumerate(rows):
    tr = ['<tr>']
    if idx == 0 or rows[idx - 1][0] != ph:
        span = sum(1 for r in rows if r[0] == ph)
        tr.append(f'<td class="ph" rowspan="{span}" style="background:{PHASE[ph][0]}">{E(PH_NAME[ph])}</td>')
    if idx == 0 or (rows[idx - 1][0], rows[idx - 1][1]) != (ph, task):
        span = 0
        for r in rows[idx:]:
            if (r[0], r[1]) == (ph, task):
                span += 1
            else:
                break
        tr.append(f'<td class="task" rowspan="{span}">{E(task)}</td>')
    tr.append(f'<td class="det">{E(detail)}</td><td class="own">{E(owner)}</td>')
    tr.append(cells(slots, ph, st))
    tr.append(f'<td class="st">{E(STATUS[st])}</td></tr>')
    body.append(''.join(tr))

day_head = ''.join(f'<th colspan="3" class="day d">{d} ({w})</th>' for d, w in DAYS)
slot_head = ''.join(f'<th class="slot{" d" if i % 3 == 2 else ""}">{E(SLOTS[i % 3])}</th>' for i in range(N))

html = f'''<!doctype html><html><head><meta charset="utf-8"><style>
body{{margin:0;background:#fff;font-family:"Noto Sans CJK KR","WenQuanYi Zen Hei",sans-serif;color:#1d2433}}
#wbs{{display:inline-block;padding:22px 26px 18px}}
table{{border-collapse:collapse;font-size:13px}}
.meta td,.meta th{{border:1px solid #b8c0cc;padding:5px 12px;height:20px}}
.meta th{{background:#eceef2;font-weight:bold;white-space:nowrap}}
.meta .title{{font-size:16px;font-weight:bold;text-align:center;width:300px;border:2px solid #2c3444}}
.main{{margin-top:16px}}
.main th,.main td{{border:1px solid #c3c9d3;padding:5px 10px;height:22px}}
.main th{{background:#eceef2;font-weight:bold}}
.ph{{font-weight:bold;text-align:center;width:110px}}
.task{{text-align:center;width:90px}}
.det{{width:300px;white-space:nowrap}}
.own{{text-align:center;width:70px;white-space:nowrap}}
.c{{width:34px;padding:0!important}}
.c.d{{border-right:2px solid #8a94a6}}
th.d{{border-right:2px solid #8a94a6}}
.st{{width:60px;text-align:center}}
.slot{{font-size:11.5px;font-weight:normal!important;padding:3px 0!important}}
.note{{font-size:12px;color:#5a6475;margin-top:8px}}
</style></head><body><div id="wbs">
<table class="meta"><tr>
<td class="title" rowspan="3">{E(T('baby-care-vision-platform WBS', 'baby-care-vision-platform WBS'))}</td>
<th>{E(T('프로젝트명', 'Project'))}</th><td>{E(T('영상 위험 감지 웹 서비스 · 6명', 'Video danger detection web service · 6 members'))}</td>
<th>{E(T('문서버전', 'Version'))}</th><td>v1.0</td></tr>
<tr><th>{E(T('작성자', 'Author'))}</th><td>PM</td><th>{E(T('최초작성일', 'Created'))}</th><td>2026-11-26</td></tr>
<tr><th>{E(T('기간', 'Period'))}</th><td>{E(T('2026-11-25 ~ 11-27 · 발표 11-27', '2026-11-25 ~ 11-27 · demo 11-27'))}</td><th>{E(T('최종수정일', 'Updated'))}</th><td>2026-11-26</td></tr>
</table>
<table class="main">
<tr><th rowspan="2">{E(T('진행단계', 'Phase'))}</th><th rowspan="2">{E(T('수행내용', 'Work'))}</th><th rowspan="2">{E(T('상세수행내용', 'Details'))}</th><th rowspan="2">{E(T('담당', 'Owner'))}</th>{day_head}<th rowspan="2">{E(T('비고', 'Status'))}</th></tr>
<tr>{slot_head}</tr>
{''.join(body)}
</table>
<div class="note">{E(T('기간 = 3일 (오전 · 오후 · 저녁) · 칸 색 = 진행단계 · 회색 막대 = 예정 · 빨간 칸 = 최종 완료 목표 · 완료 일정은 GitHub 커밋 · PR 머지 시각 기준',
                       '3 days (AM · PM · evening) · colour = phase · gray bar = planned · red = final goal · done items follow GitHub commit and PR merge times'))}</div>
</div></body></html>'''
open('wbs.en.html' if EN else 'wbs.html', 'w', encoding='utf-8').write(html)
