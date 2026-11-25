# Contributing

1. **Branches**: `main` = finished work only. Work only on part branches: `backend`, `ai-service`, `frontend`.
2. **No direct push to main.** Open a Pull Request from your part branch to `main`; the PM reviews and merges.
3. **Shared branch**: two members share one part branch (different files). `git pull` before you start and again before you push.
4. **Commits**: one step = one commit. One English line with a prefix: `feat:` / `fix:` / `refactor:` / `chore:` / `docs:` (e.g. `feat: add AnalysisAPIView post`)
5. **Pull Requests**: same title format as commits. Body: **What I did** / **How to check**. Files not in the agreed folder structure are not merged.
6. **Merge order**: `ai-service` (/predict) → `backend` (connect) → `frontend`.
7. **Never commit**: `.venv/`, `ai_service/models/`, `media/`, `db.sqlite3`, `*.mp4`, `*.pt`, `*.joblib`, `__pycache__/`, `.env`
8. **Result values**: the API returns `SAFE` / `DANGER`; the screen shows "위험 미감지" / "위험 감지".
9. **Naming**: Python `snake_case` (classes `PascalCase`), JavaScript `camelCase`, HTML id / CSS class `kebab-case`, API keys and URLs lowercase.
