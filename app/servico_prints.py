"""
Screenshot service: one persistent headless browser in a dedicated worker thread,
priority queue (user clicks jump ahead of background prefetch), and a cache keyed
by lead id + website, so a recycled lead id never shows another company's print.
"""

import os
import glob
import time
import queue
import hashlib
import threading
import html as html_lib
import itertools
from concurrent.futures import Future
from datetime import datetime

import banco_dados
import gerador_propostas

VIEWPORT = {"width": 1280, "height": 800}
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
PRIORITY_USER = 0
PRIORITY_PREFETCH = 5

_counter = itertools.count()
_queue = queue.PriorityQueue()
_thread = None
_thread_lock = threading.Lock()
_inflight = {}
_inflight_lock = threading.Lock()


def _shots_dir(static_folder):
    path = os.path.join(static_folder, "screenshots")
    os.makedirs(path, exist_ok=True)
    return path


def _cache_key(lead):
    raw = f"{(lead.get('website') or '').strip().lower()}|{(lead.get('name') or '').strip().lower()}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()[:10]


def _file_for(static_folder, lead):
    filename = f"lead_{lead['id']}_{_cache_key(lead)}.jpg"
    return os.path.join(_shots_dir(static_folder), filename), filename


def clear_cache(static_folder):
    """Remove every stored print (called when the lead base is cleared)."""
    for f in glob.glob(os.path.join(_shots_dir(static_folder), "lead_*")):
        try:
            os.remove(f)
        except OSError:
            pass


def _launch(pw):
    args = {"headless": True, "args": ["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]}
    for channel in ("chrome", "msedge", None):
        try:
            if channel:
                return pw.chromium.launch(channel=channel, **args)
            return pw.chromium.launch(**args)
        except Exception:
            continue
    raise RuntimeError("Nenhum navegador disponível para capturar prints.")


def _worker_loop():
    from playwright.sync_api import sync_playwright
    pw = None
    browser = None
    while True:
        try:
            if pw is None:
                pw = sync_playwright().start()
            if browser is None or not browser.is_connected():
                browser = _launch(pw)
            _, _, func, fut = _queue.get()
            try:
                fut.set_result(func(browser))
            except Exception as e:
                fut.set_exception(e)
        except Exception as err:
            time.sleep(1)


def _ensure_worker():
    global _thread
    with _thread_lock:
        if _thread is None or not _thread.is_alive():
            _thread = threading.Thread(target=_worker_loop, name="ScreenshotWorker", daemon=True)
            _thread.start()


def _submit(func, priority):
    _ensure_worker()
    fut = Future()
    _queue.put((priority, next(_counter), func, fut))
    return fut


def _card_html(kind, name, url):
    palette = {
        "nosite": ("#C2410C", "Sem site cadastrado",
                   "Nenhum site oficial vinculado no perfil do Google Maps.",
                   "Quem pesquisa esta empresa no celular não encontra onde clicar para falar no WhatsApp. Oportunidade direta para a Landing Page de R$ 1.000,00."),
        "whatsapp": ("#15803D", "Apenas link de WhatsApp",
                     "O perfil aponta somente para uma conversa direta, sem página de apresentação.",
                     "A empresa depende de um link solto, sem catálogo, serviços ou autoridade. Bom alvo para a oferta de R$ 1.000,00."),
        "offline": ("#B45309", "Site fora do ar ou inacessível",
                    "O servidor não respondeu a tempo (DNS, SSL ou indisponibilidade).",
                    "Clientes que chegam pelo Google caem numa página com erro. Argumento forte para criar uma página nova e estável."),
    }
    color, title, sub, argument = palette.get(kind, palette["offline"])
    name = html_lib.escape(name or "Empresa")
    url = html_lib.escape(url or "-")
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>
    body{{margin:0;background:#FAF9F6;font-family:'Segoe UI',system-ui,sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;color:#1C1917}}
    .card{{background:#fff;border:1px solid #E8E5DF;border-top:4px solid {color};border-radius:16px;padding:44px 52px;max-width:680px;box-shadow:0 20px 50px rgba(28,25,23,.08)}}
    .tag{{display:inline-block;font-size:11px;letter-spacing:.08em;text-transform:uppercase;font-weight:700;color:{color};margin-bottom:14px}}
    h2{{margin:0 0 6px;font-size:26px;letter-spacing:-.01em}}
    .url{{font-family:Consolas,monospace;font-size:13px;background:#F5F3EF;border-radius:8px;padding:9px 14px;margin:14px 0 18px;word-break:break-all;color:#57534E}}
    p{{font-size:14px;color:#78716C;line-height:1.6;margin:0 0 16px}}
    .arg{{border-left:3px solid {color};padding:4px 0 4px 16px;font-size:13.5px;color:#44403C;line-height:1.6}}
    </style></head><body><div class="card">
    <div class="tag">{title}</div><h2>{name}</h2><div class="url">{url}</div>
    <p>{sub}</p><div class="arg">{argument}</div></div></body></html>"""


def _capture_job(lead, filepath, website, kind, force):
    def job(browser):
        if os.path.exists(filepath) and not force and os.path.getsize(filepath) > 1000:
            return
        context = browser.new_context(viewport=VIEWPORT, user_agent=USER_AGENT, ignore_https_errors=True)
        try:
            page = context.new_page()
            shot = {"path": filepath, "type": "jpeg", "quality": 72, "full_page": False}
            if kind == "site":
                # Abort media, fonts, and heavy tracking scripts to make capture 3x faster
                def _filter_route(route):
                    r_type = route.request.resource_type
                    if r_type in ("media", "font"):
                        return route.abort()
                    u = route.request.url.lower()
                    if any(t in u for t in ("google-analytics.com", "googletagmanager.com", "connect.facebook.net", "hotjar", "clarity.ms")):
                        return route.abort()
                    return route.continue_()

                page.route("**/*", _filter_route)
                try:
                    page.goto(website, timeout=7000, wait_until="domcontentloaded")
                    try:
                        page.wait_for_load_state("load", timeout=1500)
                    except Exception:
                        pass
                    page.wait_for_timeout(350)
                    page.screenshot(**shot)
                    return
                except Exception:
                    kind_final = "offline"
            else:
                kind_final = kind
            page.set_content(_card_html(kind_final, lead.get("name"), website))
            page.screenshot(**shot)
        finally:
            try:
                context.close()
            except Exception:
                pass
    return job


def _plan(lead):
    raw = (lead.get("website") or "").strip()
    if not raw:
        return "", "nosite"
    website = gerador_propostas.resolve_google_ad_url(raw)
    if website != raw:
        banco_dados.update_lead_website(lead["id"], website)
        lead["website"] = website
    if not website.startswith(("http://", "https://")):
        website = f"http://{website}"
    if "wa.me" in website.lower() or "whatsapp.com" in website.lower():
        return website, "whatsapp"
    return website, "site"


def get_screenshot(lead, static_folder, force=False):
    """Blocking call used by the modal. Returns a dict ready for jsonify."""
    filepath, filename = _file_for(static_folder, lead)
    url = f"/static/screenshots/{filename}"
    cached = os.path.exists(filepath) and os.path.getsize(filepath) > 1000
    if not (cached and not force):
        website, kind = _plan(lead)
        # The URL may have been rewritten by _plan, so recompute the target file.
        filepath, filename = _file_for(static_folder, lead)
        url = f"/static/screenshots/{filename}"
        fut = _submit(_capture_job(lead, filepath, website, kind, force), PRIORITY_USER)
        fut.result(timeout=40)
    
    cached_at_str = "agora"
    if os.path.exists(filepath):
        try:
            cached_at_str = datetime.fromtimestamp(os.path.getmtime(filepath)).strftime("%d/%m/%Y %H:%M")
        except Exception:
            cached_at_str = "agora"

    return {
        "success": True,
        "lead_id": lead["id"],
        "lead_name": lead.get("name"),
        "website": (lead.get("website") or "Sem website cadastrado"),
        "screenshot_url": url,
        "cached": cached and not force,
        "cached_at": cached_at_str,
    }


def prefetch(leads, static_folder):
    """Queue background captures so the modal opens instantly. Returns how many were queued."""
    queued = 0
    for lead in leads:
        filepath, _ = _file_for(static_folder, lead)
        if os.path.exists(filepath) and os.path.getsize(filepath) > 1000:
            continue
        with _inflight_lock:
            if filepath in _inflight:
                continue
            _inflight[filepath] = True

        def run(lead=lead, filepath=filepath):
            try:
                website, kind = _plan(lead)
                real_path, _ = _file_for(static_folder, lead)
                _submit(_capture_job(lead, real_path, website, kind, False), PRIORITY_PREFETCH).result(timeout=60)
            except Exception:
                pass
            finally:
                with _inflight_lock:
                    _inflight.pop(filepath, None)

        threading.Thread(target=run, daemon=True).start()
        queued += 1
    return queued
