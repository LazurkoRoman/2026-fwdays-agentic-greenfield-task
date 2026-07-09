#!/usr/bin/env python3
"""
app.py — веб-сервер Flask для порівняння двох STEP-файлів.

Запуск:
    python app.py
    # або
    flask --app app run --debug

Відкрийте http://127.0.0.1:5000 у браузері.
"""

import os
import sys
import math
import html as html_lib
import tempfile
import shutil
import uuid
from collections import OrderedDict
from pathlib import Path

from flask import Flask, Response, redirect, request, send_from_directory, url_for
from werkzeug.utils import secure_filename

sys.path.insert(0, str(Path(__file__).parent / "src"))

from compare import compare_nodes
from i18n import available_languages, normalize_lang, tr
from report import render_report
from step_tree import parse_step

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 200 * 1024 * 1024  # 200 MB ліміт завантаження

# ---------- Session store ----------
# sid -> absolute path до temp-директорії з STL-файлами
_MAX_SESSIONS = 10
_sessions: OrderedDict = OrderedDict()


def _session_dir(session_value):
  """Return the session STL directory for legacy/new in-memory session formats."""
  if isinstance(session_value, dict):
    return session_value.get("dir")
  return session_value


def _new_session() -> tuple:
  """Створює нову temp-директорію для сесії, повертає (sid, dir_path)."""
  sid = uuid.uuid4().hex
  tmpdir = tempfile.mkdtemp(prefix="stptree_")
  _sessions[sid] = {"dir": tmpdir}
  # Виселяємо найстаріші сесії понад ліміт
  while len(_sessions) > _MAX_SESSIONS:
    _, old_session = _sessions.popitem(last=False)
    old_dir = _session_dir(old_session)
    shutil.rmtree(old_dir, ignore_errors=True)
  return sid, tmpdir


def _render_session_report(sid: str, lang: str) -> Response:
  """Rebuild a report for an existing session so language switching keeps tree data."""
  session = _sessions.get(sid)
  stl_dir = _session_dir(session)
  if not stl_dir or not os.path.isdir(stl_dir):
    return Response(_render_error_page(lang, tr(lang, "internal_error_prefix")), status=404)

  if not isinstance(session, dict):
    return Response(_render_error_page(lang, tr(lang, "internal_error_prefix")), status=410)

  path_a = session.get("path_a")
  path_b = session.get("path_b")
  title_a = session.get("title_a")
  title_b = session.get("title_b")
  vol_tol = session.get("volume_tol")
  com_tol = session.get("com_tol")

  if not path_a or not path_b or title_a is None or title_b is None or vol_tol is None or com_tol is None:
    return Response(_render_error_page(lang, tr(lang, "internal_error_prefix")), status=410)

  tree_a = parse_step(path_a, stl_dir=stl_dir)
  tree_b = parse_step(path_b, stl_dir=stl_dir)
  diff = compare_nodes(tree_a, tree_b, volume_tol_pct=vol_tol, com_tol_mm=com_tol)
  stl_base_url = f"/stl/{sid}/"
  html_report = render_report(
    diff,
    title_a,
    title_b,
    tree_a=tree_a,
    tree_b=tree_b,
    stl_base_url=stl_base_url,
    lang=lang,
    lang_switch_url_template=f"/report/{sid}?lang={{code}}",
    back_url=f"/?lang={lang}",
  )
  return Response(html_report, mimetype="text/html; charset=utf-8")


_ALLOWED = {".stp", ".step"}


def _allowed(filename: str) -> bool:
  """Return True when an uploaded filename has an allowed STEP extension."""
  return Path(filename).suffix.lower() in _ALLOWED


def _language_links(lang: str) -> str:
  """Render language switch links for the upload page header."""
  return " ".join(
    f'<a href="/?lang={code}" class="lang-link{" active" if code == lang else ""}">{tr(code, "language_label")}</a>'
    for code in available_languages()
  )


def _render_upload_page(lang: str) -> str:
  """Return localized upload-page HTML for the requested language."""
  page = _UPLOAD_PAGE
  page = page.replace('lang="uk"', f'lang="{lang}"')
  page = page.replace("<title>STEP Tree Comparator</title>", f"<title>{tr(lang, 'app_title')}</title>")
  page = page.replace(
    "<style>",
    "<style>\n  .langbar { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 18px; }\n  .lang-label { font-size: 12px; text-transform: uppercase; letter-spacing: .08em; color: #7f8aa5; }\n  .lang-links { display: flex; gap: 8px; flex-wrap: wrap; }\n  .lang-link { color: #aeb9ff; text-decoration: none; border: 1px solid #30364a; padding: 4px 8px; border-radius: 999px; font-size: 12px; }\n  .lang-link.active { color: #fff; border-color: #5b6af0; background: rgba(91, 106, 240, .18); }",
  )
  page = page.replace(
    '<div class="card">',
    f'<div class="card"><div class="langbar"><div class="lang-label">{tr(lang, "lang_switch_label")}</div><div class="lang-links">{_language_links(lang)}</div></div>',
  )
  page = page.replace("<h1>⚙ STEP Tree Comparator</h1>", f"<h1>⚙ {tr(lang, 'app_heading')}</h1>")
  page = page.replace(
    '<p class="subtitle">Завантажте два .stp/.step файли, щоб порівняти їх дерева елементів</p>',
    f'<p class="subtitle">{tr(lang, "app_subtitle")}</p>',
  )
  page = page.replace("<label>Файл A (базовий)</label>", f'<label>{tr(lang, "file_a_label")}</label>')
  page = page.replace("<label>Файл B (для порівняння)</label>", f'<label>{tr(lang, "file_b_label")}</label>')
  page = page.replace(
    "Перетягніть або натисніть, щоб вибрати",
    tr(lang, "file_hint"),
  )
  page = page.replace(
    "<button type=\"button\" class=\"advanced-toggle\" onclick=\"toggleAdv()\">▸ Налаштування допусків</button>",
    f'<button type="button" class="advanced-toggle" onclick="toggleAdv()">▸ {tr(lang, "tolerance_toggle")}</button>',
  )
  page = page.replace("<label>Допуск обʼєму, %</label>", f'<label>{tr(lang, "volume_tol_label")}</label>')
  page = page.replace("Зміна меньша за цей % вважається шумом", tr(lang, "volume_tol_hint"))
  page = page.replace("<label>Допуск ЦВ, мм</label>", f'<label>{tr(lang, "com_tol_label")}</label>')
  page = page.replace("Зміщення ЦВ меньше цього = без змін", tr(lang, "com_tol_hint"))
  page = page.replace("Порівняти →", tr(lang, "compare_button"))
  page = page.replace("Обробка STEP-файлів, зачекайте…", tr(lang, "loading_text"))
  page = page.replace(
    'action="/compare" enctype="multipart/form-data">',
    f'action="/compare" enctype="multipart/form-data"><input type="hidden" name="lang" value="{lang}">',
  )
  page = page.replace(
    "btn.textContent = (open ? '▾' : '▸') + ' Налаштування допусків';",
    f"btn.textContent = (open ? '▾' : '▸') + ' {tr(lang, 'tolerance_toggle')}';",
  )
  return page


def _render_error_page(lang: str, msg: str) -> str:
  """Build a localized standalone error page."""
  safe_msg = html_lib.escape(msg, quote=True)
  return f"""<!DOCTYPE html><html lang=\"{lang}\"><head><meta charset=\"UTF-8\">
<title>{tr(lang, 'error_title')}</title>
<style>body{{font-family:sans-serif;background:#0f1115;color:#e8e8e8;
  display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0}}
.box{{background:#3b1a1a;color:#f48fb1;border-radius:10px;padding:28px 36px;max-width:480px}}
a{{color:#90caf9;text-decoration:none}} .back{{display:inline-block;margin-top:12px}}</style></head>
<body><div class="box"><h2>{tr(lang, 'error_title')}</h2><p>{safe_msg}</p>
<a class="back" href="/?lang={lang}">← {tr(lang, 'error_back')}</a></div></body></html>"""


# ---------- Сторінка завантаження ----------

_UPLOAD_PAGE = """<!DOCTYPE html>
<html lang="uk">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>STEP Tree Comparator</title>
<style>
  *, *::before, *::after { box-sizing: border-box; }
  body { font-family: -apple-system, Segoe UI, Roboto, sans-serif;
         background: #0f1115; color: #e8e8e8;
         min-height: 100vh; display: flex; align-items: center; justify-content: center;
         margin: 0; padding: 24px; }
  .card { background: #171a21; border-radius: 14px; padding: 40px 44px;
          width: 100%; max-width: 560px; box-shadow: 0 8px 40px #0008; }
  h1 { margin: 0 0 6px; font-size: 22px; }
  .subtitle { color: #888; font-size: 13px; margin-bottom: 30px; }
  .fields { display: grid; gap: 18px; }
  label { font-size: 12px; font-weight: 700; text-transform: uppercase;
          letter-spacing: .07em; color: #aaa; display: block; margin-bottom: 6px; }
  .drop-zone { border: 2px dashed #2e3347; border-radius: 8px; padding: 22px 16px;
               text-align: center; cursor: pointer; transition: border-color .2s, background .2s;
               position: relative; }
  .drop-zone:hover, .drop-zone.over { border-color: #5b6af0; background: #1c2035; }
  .drop-zone input[type=file] { position: absolute; inset: 0; opacity: 0; cursor: pointer; width: 100%; }
  .drop-zone .hint { font-size: 13px; color: #666; pointer-events: none; }
  .drop-zone .filename { font-size: 13px; color: #81c784; font-weight: 600; pointer-events: none; }
  .drop-icon { font-size: 28px; margin-bottom: 6px; pointer-events: none; }
  .advanced-toggle { background: none; border: none; color: #5b6af0; font-size: 12px;
                     cursor: pointer; padding: 0; margin-top: 4px; }
  .advanced { display: none; grid-template-columns: 1fr 1fr; gap: 12px; margin-top: 12px; }
  .advanced.open { display: grid; }
  .input-group { display: flex; flex-direction: column; gap: 4px; }
  input[type=number] { background: #1e2330; border: 1px solid #2e3347; border-radius: 6px;
                        color: #e8e8e8; font-size: 13px; padding: 7px 10px; outline: none;
                        transition: border-color .2s; }
  input[type=number]:focus { border-color: #5b6af0; }
  .hint-text { font-size: 11px; color: #555; }
  .btn { width: 100%; padding: 13px; border: none; border-radius: 8px; font-size: 15px;
         font-weight: 700; cursor: pointer; margin-top: 6px;
         background: linear-gradient(135deg, #5b6af0, #7c3aed); color: #fff;
         transition: opacity .2s, transform .1s; }
  .btn:hover { opacity: .92; }
  .btn:active { transform: scale(.98); }
  .btn:disabled { opacity: .45; cursor: not-allowed; transform: none; }
  .loading { display: none; text-align: center; padding: 14px 0 4px; font-size: 13px; color: #888; }
  .spinner { display: inline-block; width: 16px; height: 16px; border: 2px solid #333;
             border-top-color: #5b6af0; border-radius: 50%; animation: spin .7s linear infinite;
             vertical-align: middle; margin-right: 6px; }
  @keyframes spin { to { transform: rotate(360deg); } }
  .error { background: #3b1a1a; color: #f48fb1; border-radius: 8px; padding: 10px 14px;
           font-size: 13px; display: none; margin-top: 10px; }
</style>
</head>
<body>
<div class="card">
  <h1>⚙ STEP Tree Comparator</h1>
  <p class="subtitle">Завантажте два .stp/.step файли, щоб порівняти їх дерева елементів</p>
  <form id="frm" method="post" action="/compare" enctype="multipart/form-data">
    <div class="fields">

      <div>
        <label>Файл A (базовий)</label>
        <div class="drop-zone" id="dz-a">
          <input type="file" name="file_a" accept=".stp,.step" required id="inp-a">
          <div class="drop-icon">📂</div>
          <div class="hint" id="lbl-a">Перетягніть або натисніть, щоб вибрати</div>
        </div>
      </div>

      <div>
        <label>Файл B (для порівняння)</label>
        <div class="drop-zone" id="dz-b">
          <input type="file" name="file_b" accept=".stp,.step" required id="inp-b">
          <div class="drop-icon">📂</div>
          <div class="hint" id="lbl-b">Перетягніть або натисніть, щоб вибрати</div>
        </div>
      </div>

      <div>
        <button type="button" class="advanced-toggle" onclick="toggleAdv()">▸ Налаштування допусків</button>
        <div class="advanced" id="adv">
          <div class="input-group">
            <label>Допуск обʼєму, %</label>
            <input type="number" name="volume_tol" value="0.5" min="0" step="0.1">
            <span class="hint-text">Зміна меньша за цей % вважається шумом</span>
          </div>
          <div class="input-group">
            <label>Допуск ЦВ, мм</label>
            <input type="number" name="com_tol" value="0.1" min="0" step="0.01">
            <span class="hint-text">Зміщення ЦВ меньше цього = без змін</span>
          </div>
        </div>
      </div>

    </div>
    <button type="submit" class="btn" id="btn">Порівняти →</button>
    <div class="loading" id="loading">
      <span class="spinner"></span>Обробка STEP-файлів, зачекайте…
    </div>
    <div class="error" id="err"></div>
  </form>
</div>
<script>
function toggleAdv() {
  var el = document.getElementById('adv');
  var btn = event.target;
  var open = el.classList.toggle('open');
  btn.textContent = (open ? '▾' : '▸') + ' Налаштування допусків';
}

function bindDrop(dzId, inpId, lblId) {
  var inp = document.getElementById(inpId);
  var lbl = document.getElementById(lblId);
  var dz  = document.getElementById(dzId);
  inp.addEventListener('change', function() {
    if (inp.files[0]) {
      lbl.textContent = inp.files[0].name;
      lbl.className = 'filename';
    }
  });
  dz.addEventListener('dragover', function(e) { e.preventDefault(); dz.classList.add('over'); });
  dz.addEventListener('dragleave', function() { dz.classList.remove('over'); });
  dz.addEventListener('drop', function(e) {
    e.preventDefault(); dz.classList.remove('over');
    var file = e.dataTransfer.files[0];
    if (!file) return;
    var dt = new DataTransfer(); dt.items.add(file);
    inp.files = dt.files;
    lbl.textContent = file.name; lbl.className = 'filename';
  });
}

bindDrop('dz-a', 'inp-a', 'lbl-a');
bindDrop('dz-b', 'inp-b', 'lbl-b');

document.getElementById('frm').addEventListener('submit', function() {
  document.getElementById('btn').disabled = true;
  document.getElementById('loading').style.display = 'block';
});
</script>
</body>
</html>"""


# ---------- Routes ----------

@app.route("/")
def index():
  """Serve the localized upload page."""
  lang = normalize_lang(request.args.get("lang"))
  return _render_upload_page(lang)


@app.route("/stl/<sid>/<filename>")
def serve_stl(sid, filename):
  """Serve STL/PNG assets from the in-memory session cache directory."""
  stl_dir = _session_dir(_sessions.get(sid))
  if not stl_dir or not os.path.isdir(stl_dir):
    return "", 404
  safe = secure_filename(filename)
  if not safe or safe != filename or not (safe.endswith(".stl") or safe.endswith(".png")):
    return "", 400
  full = os.path.join(stl_dir, safe)
  if not os.path.isfile(full):
    return "", 404
  mimetype = "image/png" if safe.endswith(".png") else "application/octet-stream"
  return send_from_directory(stl_dir, safe, mimetype=mimetype)


@app.route("/compare", methods=["POST"])
def compare():
  """Compare two uploaded STEP files and return a localized HTML report."""
  lang = normalize_lang(request.form.get("lang") or request.args.get("lang"))
  fa = request.files.get("file_a")
  fb = request.files.get("file_b")

  if not fa or not fa.filename or not fb or not fb.filename:
    return _render_error_page(lang, tr(lang, "no_files_error")), 400

  if not _allowed(fa.filename):
    return _render_error_page(lang, tr(lang, "unsupported_format_a", filename=fa.filename)), 400
  if not _allowed(fb.filename):
    return _render_error_page(lang, tr(lang, "unsupported_format_b", filename=fb.filename)), 400

  try:
    vol_tol = float(request.form.get("volume_tol", 0.5))
    com_tol = float(request.form.get("com_tol", 0.1))
  except ValueError:
    return _render_error_page(lang, tr(lang, "invalid_tolerance_error")), 400

  if not math.isfinite(vol_tol) or not math.isfinite(com_tol) or vol_tol < 0 or com_tol < 0:
    return _render_error_page(lang, tr(lang, "invalid_tolerance_error")), 400

  try:
    sid, stl_dir = _new_session()
    uploads = os.path.join(stl_dir, "uploads")
    os.makedirs(uploads)

    safe_name_a = secure_filename(fa.filename) or "file_a.step"
    safe_name_b = secure_filename(fb.filename) or "file_b.step"
    path_a = os.path.join(uploads, f"a_{uuid.uuid4().hex}_{safe_name_a}")
    path_b = os.path.join(uploads, f"b_{uuid.uuid4().hex}_{safe_name_b}")

    fa.save(path_a)
    fb.save(path_b)

    _sessions[sid].update({
      "path_a": path_a,
      "path_b": path_b,
      "title_a": fa.filename,
      "title_b": fb.filename,
      "volume_tol": vol_tol,
      "com_tol": com_tol,
    })
    return redirect(url_for("report_for_session", sid=sid, lang=lang), code=303)
  except RuntimeError:
    app.logger.exception("Failed to read or parse uploaded STEP files")
    return _render_error_page(lang, tr(lang, "read_error_prefix")), 422
  except Exception:  # noqa: BLE001
    app.logger.exception("Unhandled exception in /compare")
    return _render_error_page(lang, tr(lang, "internal_error_prefix")), 500

@app.route("/report/<sid>")
def report_for_session(sid):
  """Render existing compare result for another language without re-upload."""
  lang = normalize_lang(request.args.get("lang"))
  try:
    return _render_session_report(sid, lang)
  except RuntimeError:
    app.logger.exception("Failed to rebuild report from stored session")
    return Response(_render_error_page(lang, tr(lang, "read_error_prefix")), status=422)
  except Exception:  # noqa: BLE001
    app.logger.exception("Unhandled exception in /report/<sid>")
    return Response(_render_error_page(lang, tr(lang, "internal_error_prefix")), status=500)


if __name__ == "__main__":
  host = os.environ.get("APP_HOST", "0.0.0.0")
  port = int(os.environ.get("APP_PORT", "5000"))
  app.run(debug=False, host=host, port=port)
