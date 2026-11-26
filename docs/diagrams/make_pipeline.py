# baby-care-vision-platform README AI 파이프라인 그림 (SVG) — AI 서버가 영상 1개를 판정하는 과정
# 사용: python3 make_pipeline.py      → pipeline.svg
#       python3 make_pipeline.py en   → pipeline.en.svg
# PNG: node render.js pipeline pipeline.en
import sys
from html import escape as E

EN = len(sys.argv) > 1 and sys.argv[1] == 'en'
def T(ko, en):
    return en if EN else ko

F = 'font-family="Noto Sans CJK KR, WenQuanYi Zen Hei, sans-serif"'
o = []
def t(x, y, s, size=17, fill='#1d2433', w='normal', anchor='start'):
    o.append(f'<text x="{x}" y="{y}" {F} font-size="{size}" fill="{fill}" font-weight="{w}" text-anchor="{anchor}" xml:space="preserve">{E(s)}</text>')
def rect(x, y, w, h, fill, stroke, rx=10, dash='', sw=2):
    d = f' stroke-dasharray="{dash}"' if dash else ''
    o.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{d}/>')
def path(d, c='#2c3444', dash='', sw=2.2, arrow=True):
    ds = f' stroke-dasharray="{dash}"' if dash else ''
    m = ' marker-end="url(#a)"' if arrow and not dash else (' marker-end="url(#g)"' if arrow else '')
    o.append(f'<path d="{d}" fill="none" stroke="{c}" stroke-width="{sw}"{ds}{m}/>')
def tw(s, size):  # 대략 글자 폭
    return sum(size * (0.98 if ord(ch) > 0x2E80 else 0.56) for ch in s)
def label(x, y, s, size=14):
    w = tw(s, size) + 16
    rect(x - w / 2, y - size + 1, w, size + 9, '#fff', '#fff', 4, '', 0)
    t(x, y + 3, s, size, '#5a6475', 'normal', 'middle')

# 종류별 색: (테두리, 바탕, 태그 바탕)
K = {
    'cfg': ('#3b7ddd', '#f2f7fe', '#dce9fb'),   # 설정값
    'vid': ('#1fb5c9', '#effbfd', '#d3f2f6'),   # 영상
    'py':  ('#2c3444', '#ffffff', '#eceef2'),   # Python 처리
    'dat': ('#2fbf5a', '#f0fbf3', '#d6f3de'),   # 실행 중 만들어지는 데이터
    'mdl': ('#8b5cf6', '#f6f2ff', '#e8defd'),   # 학습 모델 파일
    'res': ('#f0a000', '#fffaec', '#fdefc8'),   # 결과 · 응답
}
W = 2000
COLX = {'L': 70, 'C': 720, 'R': 1370}
BW = 560
LH = 25

boxes = {}
def box_h(lines):
    return 40 + 30 + len(lines) * LH + 18

def draw_box(b):
    x, y, h = b['x'], b['y'], b['h']
    c, bg, tag = K[b['kind']]
    rect(x, y, BW, h, bg, c, 10, '', 2.5)
    o.append(f'<rect x="{x}" y="{y + 1}" width="7" height="{h - 2}" fill="{c}"/>')
    t(x + 26, y + 36, b['title'], 21, '#1d2433', 'bold')
    tg = T('역할 · ', 'Role · ') + b['role']
    rect(x + 20, y + 48, tw(tg, 16) + 20, 26, tag, tag, 4, '', 0)
    t(x + 30, y + 67, tg, 16, '#1d2433', 'bold')
    for k, s in enumerate(b['lines']):
        t(x + 26, y + 98 + k * LH, s, 16, '#3a4252')
    if b.get('mark'):
        s = '● result'
        w = tw(s, 15) + 26
        rect(x + BW - w - 14, y - 14, w, 28, '#fff', '#d32f2f', 14, '', 2)
        t(x + BW - w / 2 - 14, y + 6, s, 15, '#d32f2f', 'bold', 'middle')

y = 0
sections = []
def section(title, sub, rows):
    """rows: [[box, ...], ...] — box = dict(id, col, kind, title, role, lines, mark)"""
    global y
    top = y
    y += 92
    for row in rows:
        hmax = 0
        for b in row:
            b['x'] = COLX[b['col']]
            b['y'] = y
            b['h'] = box_h(b['lines'])
            boxes[b['id']] = b
            hmax = max(hmax, b['h'])
        y += hmax + 74
    y -= 30
    sections.append((top, y, title, sub))
    y += 34

def B(id, col, kind, title, role, lines, mark=False):
    return dict(id=id, col=col, kind=kind, title=title, role=role, lines=lines, mark=mark)

y = 140
section(T('① 학습 완료 모델 파일 — ai_service/models/', '① Trained model files — ai_service/models/'),
        T('학습은 끝난 상태 · 용량 때문에 Git 에 없고 팀 공유 드라이브에서 받아 넣는다 (서비스는 재학습하지 않음)',
          'Training is done · not in Git because of size, copied from the team shared drive (the service never retrains)'), [[
    B('pt', 'L', 'mdl', 'yolo11n-pose.pt', T('사람 관절 추출 모델', 'Pose model'),
      [T('YOLO11 Pose · 사람마다 관절 17개 (COCO)', 'YOLO11 Pose · 17 COCO keypoints per person'),
       T('load_pose_model() 이 YOLO(...) 로 로드', 'loaded by load_pose_model() with YOLO(...)')]),
    B('rf', 'C', 'mdl', 'rf_action_baseline.joblib', T('동작 분류 RandomForest', 'Action RandomForest'),
      [T('입력 = 특징 1,140개', 'input = 1,140 features'),
       'classes_ = OTHER · drop · look_away · shake',
       T('predict_proba → 4개 클래스 확률', 'predict_proba → 4 class probabilities')], True),
    B('js', 'R', 'mdl', 'rf_training_info.json', T('규격 · 구간 · 판정 기준값', 'Spec · windows · thresholds'),
      ['classes · feature_count 1,140 · sequence_steps 30',
       'window_seconds · window_stride_seconds · min_valid_frames',
       'danger_threshold 0.35 · repeat_windows 2']),
]])

section(T('② 서버 시작 — ai_service/main.py lifespan (켤 때 1번)', '② Start-up — ai_service/main.py lifespan (once)'),
        T('요청이 오기 전에 모델 파일 3개를 한 번만 로드하고 규격(특징 수 · 클래스)이 학습 때와 같은지 확인',
          'Load the 3 model files once before any request and check feature count · classes match training'), [[
    B('const', 'L', 'cfg', T('main.py 상수', 'main.py constants'), T('추론 설정값', 'Inference settings'),
      ['IMAGE_SIZE 640 · PERSON_CONFIDENCE 0.25', 'TRACKER bytetrack.yaml',
       'DANGER_CLASSES = shake · drop · look_away',
       T('장치: GPU 있으면 0, 없으면 cpu', 'device: GPU → 0, else cpu')]),
    B('life', 'C', 'py', 'lifespan(app) → load_models()', T('모델 로드 + 규격 확인', 'Load models + validate'),
      ['joblib.load · load_json(rf_training_info) · YOLO(pt)',
       T('validate_model(): n_features_in_ = feature_count', 'validate_model(): n_features_in_ = feature_count'),
       T('classes_ = training_info["classes"] (순서까지)', 'classes_ = training_info["classes"] (same order)'),
       T('하나라도 다르면 서버가 켜지지 않음', 'any mismatch → server does not start')]),
  ], [
    B('state', 'C', 'dat', 'app.state', T('요청마다 재사용할 객체', 'Reused on every request'),
      ['models = {rf_model · training_info · pose_model}',
       T('pose_lock (동시 요청 추적 충돌 방지)', 'pose_lock (no tracker clash between requests)')]),
    B('health', 'R', 'res', 'GET /health', T('서버 상태 확인', 'Health check'),
      ['{"status": "ok"}', T('lifespan 이 끝나야 응답 → 모델 준비 완료 신호', 'answers only after lifespan → models ready')]),
]])

section(T('③ 영상 입력 — POST /predict', '③ Video in — POST /predict'),
        T('Django 가 저장한 영상을 multipart file 로 보내면 임시 파일로 받아 판정 함수에 넘긴다 · FastAPI 는 DB 를 쓰지 않음',
          'Django sends the stored video as a multipart file; it is kept as a temp file and passed to the decision function · no DB here'), [[
    B('dj', 'L', 'vid', T('Django → 영상 전송', 'Django → sends video'), T('영상을 보내는 쪽', 'Caller'),
      ['media/videos/*.mp4  (Analysis.video)',
       'requests.post(AI_SERVICE_URL + "/predict",',
       '  files={"file": ...}, timeout=60)']),
    B('pred', 'C', 'py', 'predict(file: UploadFile)', T('추론 API 입구', 'Inference entry'),
      [T('NamedTemporaryFile(suffix=.mp4) 에 복사', 'copy to NamedTemporaryFile(suffix=.mp4)'),
       'analyze_video(temp, app.state.models, pose_lock)',
       T('ValueError → HTTPException 422', 'ValueError → HTTPException 422'),
       T('요청이 끝나면 임시 파일 자동 삭제', 'temp file deleted after the request')]),
    B('e422', 'R', 'res', '422 Unprocessable Entity', T('분석 불가 사유', 'Why it cannot analyse'),
      ['Cannot open video · No readable video frames', 'No main performer detected',
       'Insufficient valid pose frames', 'Incomplete video analysis']),
]])

section(T('④ 포즈 → 특징 — analyze_video()', '④ Pose → features — analyze_video()'),
        T('프레임마다 사람을 추적하고 주 인물 1명의 관절을 38개 숫자로 바꾼 뒤, 시간 구간마다 30스텝 = 1,140 특징을 만든다',
          'Track people per frame, turn the main person\'s joints into 38 numbers, then build 30 steps = 1,140 features per time window'), [[
    B('track', 'C', 'py', 'track_video()', T('프레임마다 사람 추적', 'Track people per frame'),
      [T('with pose_lock: cv2.VideoCapture · fps (없으면 30)', 'with pose_lock: cv2.VideoCapture · fps (default 30)'),
       'pose_model.track(persist=True, bytetrack, imgsz 640, conf 0.25)',
       T('끝나면 tracker.reset() (다음 요청과 섞이지 않게)', 'tracker.reset() at the end (next request starts clean)')]),
  ], [
    B('frames', 'C', 'dat', 'frames', T('프레임별 사람 목록', 'People per frame'),
      ['timestamp_sec', 'persons: track_id · box · keypoints (17, 2)']),
  ], [
    B('main', 'C', 'py', 'select_main_track()', T('주 인물 1명 선택', 'Pick the main person'),
      [T('track 별 박스 면적 합 → 가장 큰 track_id', 'sum of box area per track → largest track_id'),
       T('사람이 없으면 422', 'no person → 422')]),
  ], [
    B('ff', 'L', 'py', 'build_frame_feature()', T('정규화 · 관절 각도', 'Normalise · joint angles'),
      [T('골반 중심을 빼고 어깨 너비로 나눠 정규화', 'minus pelvis centre, ÷ shoulder width'),
       T('calculate_angle() × 4: 팔꿈치 2 · 무릎 2', 'calculate_angle() × 4: 2 elbows · 2 knees'),
       T('NaN · 어깨 너비 0 → 그 프레임 제외', 'NaN · zero shoulder width → frame skipped')]),
    B('feat', 'C', 'dat', 'features (N, 38) · timestamps', T('주 인물의 프레임별 특징', 'Main person per-frame features'),
      ['extract_frame_features()', T('관절 17 × 2 + 각도 4 = 38', '17 joints × 2 + 4 angles = 38'),
       T('유효 프레임 < min_valid_frames → 422', 'valid frames < min_valid_frames → 422')]),
  ], [
    B('ti', 'L', 'mdl', 'rf_training_info.json', T('구간 기준', 'Window settings'),
      ['window_seconds · window_stride_seconds', 'sequence_steps 30 · min_valid_frames']),
    B('win', 'C', 'py', 'build_window_features()', T('시간 구간 → 고정 길이', 'Windows → fixed length'),
      [T('window_seconds 길이 · stride 간격으로 구간 이동', 'slide windows by window_seconds · stride'),
       T('resample_sequence(): 구간마다 30스텝으로 보간', 'resample_sequence(): interpolate to 30 steps'),
       T('30 × 38 = 1,140 (프레임 부족 구간 = None)', '30 × 38 = 1,140 (too few frames → None)')]),
]])

section(T('⑤ 판정 → 응답 — decide_result()', '⑤ Decide → reply — decide_result()'),
        T('구간마다 4클래스 확률을 내고, 위험 동작이 같은 동작으로 2구간 연속 0.35 이상이면 DANGER',
          '4-class probabilities per window; DANGER if the same danger action is ≥ 0.35 in 2 windows in a row'), [[
    B('rfp', 'C', 'mdl', T('RandomForest.predict_proba()', 'RandomForest.predict_proba()'), T('구간별 4클래스 확률', '4-class prob. per window'),
      ['rf_model.predict_proba(1 × 1,140)', 'probabilities: OTHER · drop · look_away · shake',
       T('decide_result() 안에서 구간마다 호출', 'called per window inside decide_result()')], True),
  ], [
    B('th', 'L', 'cfg', T('판정 기준값', 'Decision thresholds'), T('코드가 아니라 파일에서 읽음', 'read from files, not code'),
      ['danger_threshold 0.35 · repeat_windows 2', '(rf_training_info.json)',
       'DANGER_CLASSES = drop · look_away · shake']),
    B('dec', 'C', 'py', T('decide_result() 판정', 'decide_result() decision'), T('영상 1개 → SAFE / DANGER', 'One video → SAFE / DANGER'),
      [T('구간마다 위험 동작 3개 중 가장 높은 확률', 'per window: highest of the 3 danger actions'),
       T('≥ 0.35 · 같은 동작 2구간 연속 → 바로 DANGER', '≥ 0.35 · same action 2 windows in a row → DANGER'),
       T('끝까지 없으면 SAFE (빈 구간이 있었으면 422)', 'none until the end → SAFE (gap window → 422)')], True),
  ], [
    B('ok', 'C', 'res', '200 {"result": "SAFE" | "DANGER"}', T('Django 로 돌려주는 결과', 'Result back to Django'),
      [T('FastAPI 는 저장하지 않고 JSON 만 응답', 'FastAPI stores nothing, returns JSON only'),
       T('Django 가 Analysis.result 저장 → 201', 'Django saves Analysis.result → 201')], True),
    B('scr', 'R', 'res', T('화면 표시 (analysis.js)', 'Page (analysis.js)'), T('사용자에게 보이는 글자', 'What the user sees'),
      [T('SAFE → 위험 미감지 (초록)', 'SAFE → 위험 미감지 / no danger (green)'),
       T('DANGER → 위험 감지 (빨강)', 'DANGER → 위험 감지 / danger (red)')]),
]])

# 구역 패널
for top, bot, title, sub in sections:
    rect(40, top, W - 80, bot - top, '#f7f8fa', '#e3e6eb', 18, '', 1.5)
    t(70, top + 40, title, 23, '#1d2433', 'bold')
    t(70, top + 70, sub, 16, '#5a6475')
panels = o[:]; o.clear()

def bx(i): return boxes[i]
def cxm(b): return b['x'] + BW / 2
def down(a, b, lab=None, dx=0):
    A, Bx = bx(a), bx(b)
    x = cxm(A) + dx
    y1, y2 = A['y'] + A['h'], Bx['y'] - 4
    path(f'M{x},{y1} L{x},{y2}')
    if lab: label(x, (y1 + y2) / 2 + 4, lab)
def side(a, b, lab=None):
    A, Bx = bx(a), bx(b)
    ym = max(A['y'], Bx['y']) + 46 if A['y'] != Bx['y'] else A['y'] + 46
    ym = Bx['y'] + Bx['h'] / 2
    if A['x'] < Bx['x']:
        x1, x2 = A['x'] + BW, Bx['x'] - 4
    else:
        x1, x2 = A['x'], Bx['x'] + BW + 4
    path(f'M{x1},{ym} L{x2},{ym}')
    if lab: label((x1 + x2) / 2, ym - 12, lab, 13)
def elbow(a, b, tx_off, lab=None, dash=False, ym=None):
    A, Bx = bx(a), bx(b)
    sx, sy = cxm(A), A['y'] + A['h']
    tx, ty = cxm(Bx) + tx_off, Bx['y'] - 4
    ym = ym if ym is not None else ty - 34
    c = '#9aa3b2' if dash else '#2c3444'
    path(f'M{sx},{sy} L{sx},{ym} L{tx},{ym} L{tx},{ty}', c, '7 6' if dash else '')
    if lab: label(sx, (sy + ym) / 2 - 6, lab, 13)

down('rf', 'life', T('모델 파일 로드', 'load model files'))
GAP = (sections[0][1] + sections[1][0]) / 2
elbow('pt', 'life', -170, 'yolo11n-pose.pt', ym=GAP)
elbow('js', 'life', 170, 'rf_training_info.json', ym=GAP)
side('const', 'life', T('설정값', 'settings'))
down('life', 'state', 'app.state')
side('state', 'health', T('준비 완료', 'ready'))
down('state', 'pred', T('요청마다 재사용', 'reused per request'))
side('dj', 'pred', 'multipart file')
side('pred', 'e422', T('실패 시', 'on error'))
down('pred', 'track', T('임시 파일 경로', 'temp file path'))
down('track', 'frames', T('프레임별 결과', 'per-frame result'))
down('frames', 'main', 'persons')
down('main', 'feat', T('주 인물 track_id', 'main track_id'))
side('ff', 'feat', T('프레임당 38', '38 per frame'))
down('feat', 'win', 'features · timestamps')
side('ti', 'win', T('구간 · 30스텝', '30 steps'))
down('win', 'rfp', T('구간마다 1,140', '1,140 per window'))
down('rfp', 'dec', T('구간별 확률', 'probabilities'))
side('th', 'dec', T('0.35 · 2구간', 'thresholds'))
down('dec', 'ok', '"SAFE" | "DANGER"')
side('ok', 'scr', '201')
# 회색 점선: ② app.state.rf_model → ⑤ predict_windows
S, R_ = bx('state'), bx('rfp')
ys = S['y'] + S['h'] / 2
yr = R_['y'] + R_['h'] / 2
path(f'M{S["x"]},{ys} L{56},{ys} L{56},{yr} L{R_["x"] - 4},{yr}', '#9aa3b2', '7 6')
label(400, yr - 12, 'models["rf_model"]', 13)
arrows = o[:]; o.clear()

for b in boxes.values():
    draw_box(b)
boxes_svg = o[:]; o.clear()

# 범례
ly = y + 20
s = '● result'
w = tw(s, 15) + 26
rect(70, ly - 20, w, 28, '#fff', '#d32f2f', 14, '', 2); t(70 + w / 2, ly, s, 15, '#d32f2f', 'bold', 'middle')
t(70 + w + 18, ly, T('classes_ 순서 → predict_proba → decide_result → JSON result → Django Analysis.result → 화면 (정답이 아니라 모델 예측값)',
                     'classes_ order → predict_proba → decide_result → JSON result → Django Analysis.result → page (a model prediction, not ground truth)'), 16, '#3a4252')
ly += 50
lx = 70
for k, lab in [('cfg', T('설정값', 'Settings')), ('vid', T('영상', 'Video')), ('py', T('Python 처리', 'Python step')),
               ('dat', T('실행 중 만들어지는 데이터', 'Runtime data')), ('mdl', T('학습 모델 파일', 'Model file')), ('res', T('결과 · 응답', 'Result · reply'))]:
    c, bg, _ = K[k]
    rect(lx, ly - 20, 46, 28, bg, c, 6, '', 2.5)
    t(lx + 58, ly, lab, 16, '#3a4252')
    lx += 58 + tw(lab, 16) + 60
ly += 44
t(70, ly, T('회색 점선 = 다른 구역에서 넘어오는 객체 · AI 서버가 하는 일만 그림 (Django 저장 · 화면은 양 끝에 표시)',
            'Gray dashed = object from another section · only the AI server\'s work is drawn (Django storage and the page appear only at both ends)'), 14.5, '#5a6475')
H = ly + 40

head = [
    f'<text x="{W / 2}" y="62" {F} font-size="34" fill="#1d2433" font-weight="bold" text-anchor="middle">{E(T("baby-care-vision-platform · AI 판정 파이프라인", "baby-care-vision-platform · AI decision pipeline"))}</text>',
    f'<text x="{W / 2}" y="100" {F} font-size="18" fill="#5a6475" text-anchor="middle">{E(T("models/ → 서버 시작 시 로드 → POST /predict → YOLO Pose → 주 인물 → 38 특징 → 30스텝 = 1,140 → RandomForest 4클래스 → 0.35 · 2구간 → SAFE / DANGER", "models/ → loaded at start-up → POST /predict → YOLO Pose → main person → 38 features → 30 steps = 1,140 → RandomForest 4 classes → 0.35 · 2 windows → SAFE / DANGER"))}</text>',
]
svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">
<defs><marker id="a" markerUnits="userSpaceOnUse" markerWidth="14" markerHeight="14" refX="12" refY="7" orient="auto"><path d="M0,0 L14,7 L0,14 z" fill="#2c3444"/></marker>
<marker id="g" markerUnits="userSpaceOnUse" markerWidth="14" markerHeight="14" refX="12" refY="7" orient="auto"><path d="M0,0 L14,7 L0,14 z" fill="#9aa3b2"/></marker></defs>
<rect width="100%" height="100%" fill="#fff"/>{''.join(head + panels + arrows + boxes_svg + o)}</svg>'''
open('pipeline.en.svg' if EN else 'pipeline.svg', 'w', encoding='utf-8').write(svg)
