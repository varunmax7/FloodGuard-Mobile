"""SPA serving for the Flutter web build.

Serves the Flutter build/web/ directory as a client-side-routed SPA:
- Files that physically exist in build/web/ (main.dart.js, assets/, canvaskit/,
  icons/, favicon.png, manifest.json, etc.) are streamed with their real MIME
  type and long cache headers on hashed asset paths.
- Any other path (that isn't an /api or /admin URL) returns index.html so
  go_router can handle client-side routing when someone deep-links to /radar
  or /report.
"""
import mimetypes
from pathlib import Path

from django.http import FileResponse, Http404
from django.views.decorators.cache import cache_control
from django.views.decorators.http import require_GET

# Priority order:
#   1. FLUTTER_WEB_ROOT env var (explicit override)
#   2. backend/spa/  (production — bundled into the Docker image)
#   3. ../mobile/build/web/  (local dev — served directly from the repo)
import os as _os
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
_env_root = _os.environ.get("FLUTTER_WEB_ROOT", "").strip()
if _env_root:
    FLUTTER_WEB_ROOT = Path(_env_root).resolve()
elif (_BACKEND_ROOT / "spa" / "index.html").is_file():
    FLUTTER_WEB_ROOT = (_BACKEND_ROOT / "spa").resolve()
else:
    FLUTTER_WEB_ROOT = (_BACKEND_ROOT.parent / "mobile" / "build" / "web").resolve()


def _serve_file(path: Path):
    if not path.is_file():
        raise Http404
    ctype, _ = mimetypes.guess_type(str(path))
    ctype = ctype or "application/octet-stream"
    return FileResponse(path.open("rb"), content_type=ctype)


@require_GET
@cache_control(max_age=31536000, public=True, immutable=True)
def spa_static(request, path: str):
    """Serve a hashed/immutable asset under assets/, canvaskit/, icons/."""
    target = (FLUTTER_WEB_ROOT / path).resolve()
    # Prevent path traversal outside the web root.
    if not str(target).startswith(str(FLUTTER_WEB_ROOT)):
        raise Http404
    return _serve_file(target)


@require_GET
def spa_root_file(request, filename: str):
    """Serve a top-level file that isn't hashed — no long cache."""
    target = (FLUTTER_WEB_ROOT / filename).resolve()
    if not str(target).startswith(str(FLUTTER_WEB_ROOT)):
        raise Http404
    resp = _serve_file(target)
    resp["Cache-Control"] = "no-cache"
    return resp


@require_GET
def spa_index(request):
    """SPA fallback — return index.html for any client-side route."""
    resp = _serve_file(FLUTTER_WEB_ROOT / "index.html")
    resp["Cache-Control"] = "no-cache"
    return resp
