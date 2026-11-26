# baby-care-vision-platform README 아키텍처 그림 (SVG)
# 사용: python3 make_architecture.py      → architecture.svg
#       python3 make_architecture.py en   → architecture.en.svg
# PNG: node render.js architecture architecture.en
import sys
from html import escape as E

EN = len(sys.argv) > 1 and sys.argv[1] == 'en'
def T(ko, en):
    return en if EN else ko

F = 'font-family="Noto Sans CJK KR, WenQuanYi Zen Hei, sans-serif"'
o = []
def t(x, y, s, size=18, fill='#1d2433', w='normal', anchor='middle'):
    o.append(f'<text x="{x}" y="{y}" {F} font-size="{size}" fill="{fill}" font-weight="{w}" text-anchor="{anchor}" xml:space="preserve">{E(s)}</text>')
def r(x, y, w, h, fill, stroke, rx=12, dash='', sw=2):
    d = f' stroke-dasharray="{dash}"' if dash else ''
    o.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{d}/>')
def path(d, c, dash='', sw=2.5, marker=''):
    ds = f' stroke-dasharray="{dash}"' if dash else ''
    m = f' marker-end="url(#{marker})"' if marker else ''
    o.append(f'<path d="{d}" fill="none" stroke="{c}" stroke-width="{sw}"{ds}{m}/>')

PUR, TEAL, NAVY, INK, SUB = '#6a3fc8', '#11847f', '#1f2a5a', '#1d2433', '#5a6475'
CARD_LINE, DOT = '#c9d0db', '#9aa3b2'

NW, NH, G, X0 = 222, 118, 136, 44
W = X0 * 2 + NW * 8 + G * 7
xs = [X0 + i * (NW + G) for i in range(8)]
cx = [x + NW / 2 for x in xs]

# 제목
t(X0, 58, 'Architecture · baby-care-vision-platform', 34, INK, 'bold', 'start')
t(X0, 94, T('영상을 올리면 Django 가 저장하고 FastAPI 가 YOLO11 Pose → RandomForest 로 판정해 "위험 미감지 / 위험 감지" 만 돌려줍니다',
            'Django stores the uploaded video, FastAPI judges it with YOLO11 Pose → RandomForest, and the page shows only "No danger / Danger"'),
  18, SUB, 'normal', 'start')

# 구역선
ZY = 132
def zone(i, j, label, c):
    x1, x2 = xs[i], xs[j] + NW
    path(f'M{x1},{ZY} L{x2},{ZY}', c, '', 4)
    t(x1, ZY + 26, label, 17, c, 'bold', 'start')
zone(0, 4, T('서비스 서버 · Django + DRF · localhost:8000 — 화면 · API · 저장', 'Service server · Django + DRF · localhost:8000 — page · API · storage'), PUR)
zone(5, 6, T('AI 서버 · FastAPI · localhost:8001 — 추론 · 판정', 'AI server · FastAPI · localhost:8001 — inference'), TEAL)
zone(7, 7, T('브라우저 · 결과 표시', 'Browser · result'), PUR)

colors = [PUR] * 5 + [TEAL] * 2 + [PUR]

# 위 카드: 파일 · 담당
top = [
    ('templates/index.html', T('김준형 · 프론트 1', '김준형 · Front 1')),
    ('static/js/analysis.js', T('장세훈 · 프론트 2', '장세훈 · Front 2')),
    ('config → analysis/urls.py', T('박하솔 · 백엔드 2', '박하솔 · Backend 2')),
    ('views.py · serializers.py', T('이성형 · 백엔드 1', '이성형 · Backend 1')),
    ('models.py · migrations/', T('박하솔 · 백엔드 2', '박하솔 · Backend 2')),
    ('ai_service/main.py', T('이상직 · AI 2', '이상직 · AI 2')),
    ('main.py  analyze_video()', T('박하나 · AI 1', '박하나 · AI 1')),
    ('analysis.js  showResult()', T('장세훈 · 프론트 2', '장세훈 · Front 2')),
]
CT, CH = 178, 62
NY = CT + CH + 70
for i, (a, b) in enumerate(top):
    r(xs[i], CT, NW, CH, '#fff', CARD_LINE, 8, '', 1.5)
    t(xs[i] + 14, CT + 26, a, 14.5, INK, 'bold', 'start')
    t(xs[i] + 14, CT + 48, b, 13.5, SUB, 'normal', 'start')
    path(f'M{cx[i]},{CT + CH} L{cx[i]},{NY}', DOT, '5 5', 1.5)

# 노드
nodes = [
    ('index.html', T('영상 선택 화면', 'Video picker page')),
    ('analysis.js', T('FormData 전송', 'Sends FormData')),
    ('urls', T('URL 2단 라우팅', 'Two-level routing')),
    ('AnalysisAPIView', T('Serializer 검증', 'Serializer validation')),
    ('Analysis', 'SQLite · media/'),
    ('FastAPI /predict', T('임시 파일 저장', 'Temp file')),
    ('YOLO Pose → RF', T('→ SAFE / DANGER 판정', '→ SAFE / DANGER')),
    (T('결과 표시', 'Result'), T('위험 미감지 · 위험 감지', 'No danger · Danger')),
]
for i, (a, b) in enumerate(nodes):
    c = colors[i]
    r(xs[i], NY, NW, NH, '#fff', c, 14, '', 3)
    o.append(f'<circle cx="{xs[i] + 4}" cy="{NY + 2}" r="17" fill="{c}"/>')
    t(xs[i] + 4, NY + 8, str(i + 1), 17, '#fff', 'bold')
    t(cx[i], NY + 56, a, 21, INK, 'bold')
    t(cx[i], NY + 86, b, 14.5, SUB)

# 앞으로 가는 화살표 + 오가는 데이터
fw = [
    ('click', '#analyze-button'),
    ('POST', 'FormData video'),
    ('/api/v1/analyses/', 'AnalysisAPIView'),
    ('serializer.save()', 'video → media/'),
    ('POST /predict', 'multipart file'),
    (T('임시 파일 경로', 'temp file path'), 'analyze_video()'),
]
AY = NY + NH / 2
for i, (a, b) in enumerate(fw):
    x1, x2 = xs[i] + NW + 4, xs[i + 1] - 6
    path(f'M{x1},{AY} L{x2},{AY}', NAVY, '', 5, 'n')
    xm = (x1 + x2) / 2
    t(xm, AY - 30, a, 12.5, NAVY, 'bold')
    t(xm, AY - 14, b, 12, SUB)

# 아래 카드: 세부
bot = [
    ('#video-input · #analyze-button', 'GET / → AnalysisPageView'),
    ('X-CSRFToken ' + T('헤더', 'header'), T('응답 전까지 버튼 잠금', 'button locked until reply')),
    ("include('analysis.urls')", "'' · 'api/v1/analyses/'"),
    (T('영상 없음 → 400', 'no video → 400'), T('AI 호출 timeout 60초', 'AI call timeout 60 s')),
    ('video · result · created_at', T('result 는 판정 후 채움', 'result filled after AI')),
    ('GET /health · POST /predict', T('분석 불가 → 422', 'cannot analyse → 422')),
    (T('4클래스 확률 → 위험 동작', '4-class prob. → danger action'), T('0.35 이상 2구간 연속 → DANGER', '≥ 0.35 in 2 windows → DANGER')),
    (T('SAFE → 위험 미감지 (초록)', 'SAFE → 위험 미감지 (green)'), T('DANGER → 위험 감지 (빨강)', 'DANGER → 위험 감지 (red)')),
]
BY = NY + NH + 70
for i, (a, b) in enumerate(bot):
    path(f'M{cx[i]},{NY + NH} L{cx[i]},{BY}', DOT, '5 5', 1.5)
    r(xs[i], BY, NW, CH, '#fff', CARD_LINE, 8, '', 1.5)
    t(xs[i] + 14, BY + 26, a, 13.5, INK, 'bold', 'start')
    t(xs[i] + 14, BY + 48, b, 13, SUB, 'normal', 'start')

# 되돌아오는 점선 2개
R1 = BY + CH + 46
path(f'M{cx[6]},{BY + CH} L{cx[6]},{R1} L{cx[3] + 30},{R1} L{cx[3] + 30},{BY + CH + 8}', TEAL, '9 7', 3, 't')
lab1 = T('{"result": "SAFE" | "DANGER"} → analysis.result 저장', '{"result": "SAFE" | "DANGER"} → save analysis.result')
xm1 = (cx[6] + cx[3]) / 2
r(xm1 - 260, R1 - 17, 520, 34, '#fff', '#fff', 6)
t(xm1, R1 + 6, lab1, 15, TEAL, 'bold')
R2 = R1 + 52
path(f'M{cx[3] - 30},{BY + CH} L{cx[3] - 30},{R2} L{cx[7]},{R2} L{cx[7]},{BY + CH + 8}', PUR, '9 7', 3, 'p')
lab2 = '201 Created · {"result": "SAFE" | "DANGER"}'
xm2 = (cx[4] + cx[7]) / 2 + 60
r(xm2 - 230, R2 - 17, 460, 34, '#fff', '#fff', 6)
t(xm2, R2 + 6, lab2, 15, PUR, 'bold')

# GitHub 상자
GY = R2 + 44
GW = 1000
gx = (W - GW) / 2
r(gx, GY, GW, 78, '#faf7ff', PUR, 10, '8 6', 2)
t(gx + 28, GY + 32, 'GitHub · main ← Pull Request ← backend / ai-service / frontend', 17, INK, 'bold', 'start')
t(gx + 28, GY + 58, T('main 직접 push 금지 · 모델 파일 · 영상 · db.sqlite3 · media/ · .venv/ 는 올리지 않음 · 규칙 CONTRIBUTING.md',
                      'No direct push to main · model files · videos · db.sqlite3 · media/ · .venv/ stay out of git · CONTRIBUTING.md'),
  14, SUB, 'normal', 'start')

# 범례
LY = GY + 78 + 50
t(X0, LY, T('굵은 화살표 = 요청과 데이터가 가는 길 (위 글자 = 오가는 데이터) · 회색 점선 = 단계별 파일 · 담당 · 세부 · 청록 점선 = AI 판정 결과가 돌아오는 길 · 보라 점선 = 화면으로 가는 응답',
            'Bold arrow = request and data path (text above = payload) · gray dotted = file · owner · details per step · teal dashed = AI result coming back · purple dashed = response to the page'),
  14.5, SUB, 'normal', 'start')
H = LY + 30

svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">
<defs>
<marker id="n" markerUnits="userSpaceOnUse" markerWidth="22" markerHeight="22" refX="18" refY="11" orient="auto"><path d="M0,0 L22,11 L0,22 z" fill="{NAVY}"/></marker>
<marker id="t" markerUnits="userSpaceOnUse" markerWidth="16" markerHeight="16" refX="13" refY="8" orient="auto"><path d="M0,0 L16,8 L0,16 z" fill="{TEAL}"/></marker>
<marker id="p" markerUnits="userSpaceOnUse" markerWidth="16" markerHeight="16" refX="13" refY="8" orient="auto"><path d="M0,0 L16,8 L0,16 z" fill="{PUR}"/></marker>
</defs>
<rect width="100%" height="100%" fill="#ffffff"/>{''.join(o)}</svg>'''
open('architecture.en.svg' if EN else 'architecture.svg', 'w', encoding='utf-8').write(svg)
