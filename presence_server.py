"""
Ari's Discord Rich Presence Tool - 0.4.7
────────────────────────────────────────────────────────────
Features:
  • System-tray (Windows) – minimises there on close
  • Launch-on-startup registry toggle
  • HTTP server for Tampermonkey
  • Configurable activity type: Playing / Watching / Listening / Custom
  • Anime cover-art via AniList + Jikan fallback
  • YouTube thumbnail as large image (non-incognito)
  • playing_icon / paused_icon as small image
  • Platform name shown instead of Discord app name
  • Stable start-timestamp per title
  • Grid layout in Sites tab (~415 px cards)
  • Toast notifications instead of popup dialogs
  • Global RPC on/off master switch
  • Dev Mode (hidden: Add Custom Site)
  • Per-site Display Name field
  • app.ico used for window + tray icon
────────────────────────────────────────────────────────────
Dependencies:  pip install pypresence pystray pillow requests
Build:         build_exe.bat
"""

# ── stdlib ─────────────────────────────────────────────────────────────────────
import json, os, sys, threading, time, webbrowser, winreg
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.request import urlopen, Request as URLRequest

# ── tkinter ────────────────────────────────────────────────────────────────────
import tkinter as tk
from tkinter import ttk

# ── optional deps ──────────────────────────────────────────────────────────────
try:
    from pypresence import Presence
    try:
        from pypresence import ActivityType
        _AT_PLAYING   = ActivityType.PLAYING
        _AT_WATCHING  = ActivityType.WATCHING
        _AT_LISTENING = ActivityType.LISTENING
        _AT_CUSTOM    = getattr(ActivityType, "CUSTOM", 4)
    except (ImportError, AttributeError):
        _AT_PLAYING, _AT_WATCHING, _AT_LISTENING, _AT_CUSTOM = 0, 3, 2, 4
    PYPRESENCE_OK = True
except ImportError:
    PYPRESENCE_OK = False
    _AT_PLAYING, _AT_WATCHING, _AT_LISTENING, _AT_CUSTOM = 0, 3, 2, 4

_ACTIVITY_TYPES = {
    "Playing":   _AT_PLAYING,
    "Watching":  _AT_WATCHING,
    "Listening": _AT_LISTENING,
    "Custom":    _AT_CUSTOM,
}

try:
    import pystray
    from PIL import Image as PilImage, ImageDraw
    TRAY_OK = True
except ImportError:
    TRAY_OK = False

try:
    import requests as _req
    def _http_get(url, timeout=5):
        r = _req.get(url, timeout=timeout, headers={"User-Agent": "DiscordRP/0.4.7"})
        r.raise_for_status()
        return r.content
    def _http_post_json(url, payload, timeout=5):
        r = _req.post(url, json=payload, timeout=timeout,
                      headers={"Content-Type": "application/json", "Accept": "application/json"})
        r.raise_for_status()
        return r.json()
except ImportError:
    def _http_get(url, timeout=5):
        req = URLRequest(url, headers={"User-Agent": "DiscordRP/0.4.7"})
        with urlopen(req, timeout=timeout) as resp:
            return resp.read()
    def _http_post_json(url, payload, timeout=5):
        import json as _j
        data = _j.dumps(payload).encode()
        req  = URLRequest(url, data=data,
                          headers={"Content-Type": "application/json",
                                   "Accept":       "application/json"})
        with urlopen(req, timeout=timeout) as resp:
            return _j.loads(resp.read())

# ──────────────────────────────────────────────────────────────────────────────
APP_NAME    = "DiscordRichPresenceTool"
APP_VERSION = "0.4.7"
STARTUP_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
DEFAULT_APP_ID = "1491540466418843730"

if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
ICON_FILE   = os.path.join(BASE_DIR, "app.ico")

CATEGORY_LABELS = {"video": "Video-Streaming", "stream": "Live Streaming",
                   "music": "Music", "polish": "Polish Websites", "other": "Other"}

def _def_site(name, img, cat, enabled=True, hidden=False):
    return {"name": name, "display_name": name, "enabled": enabled, "hidden": hidden,
            "privacy": False, "discord_app_id": DEFAULT_APP_ID, "large_image": img,
            "large_text": name, "category": cat}

DEFAULT_SITES = {
    "youtube":      _def_site("YouTube",         "youtube_logo",       "video"),
    "twitch":       _def_site("Twitch",           "twitch_logo",       "video"),
    "rumble":       _def_site("Rumble",           "rumble_logo",       "video"),
    "netflix":      _def_site("Netflix",          "netflix_logo",      "video"),
    "cda":          _def_site("CDA.pl",           "cda_logo",          "polish"),
    "ogladajanime": _def_site("OgladajAnime.pl",  "anime_logo",        "polish"),
    "shinden":      _def_site("Shinden.pl",       "anime_logo",        "polish"),
}

DEFAULT_CONFIG = {
    "server_port":     7591,
    "launch_on_start": False,
    "start_minimised": False,
    "activity_type":   "Watching",
    "rpc_enabled":     True,
    "dev_mode":        False,
    "sites":           DEFAULT_SITES,
}

# ── Catppuccin Mocha palette ────────────────────────────────────────────────────
BG       = "#1e1e2e"
BG2      = "#181825"
BG3      = "#11111b"
SURFACE0 = "#313244"
SURFACE1 = "#45475a"
SURFACE2 = "#585b70"
TEXT     = "#cdd6f4"
SUBTEXT1 = "#bac2de"
SUBTEXT0 = "#a6adc8"
OVERLAY1 = "#7f849c"
OVERLAY0 = "#6c7086"
ACCENT   = "#89b4fa"
MAUVE    = "#cba6f7"
GREEN    = "#a6e3a1"
RED      = "#f38ba8"
RED2     = "#3b1a25"
YELLOW   = "#f9e2af"
PEACH    = "#fab387"
TEAL     = "#94e2d5"

# ── Global state ───────────────────────────────────────────────────────────────
config:           dict  = {}
current_presence: dict  = {}
rpc_client               = None
rpc_connected:    bool  = False
rpc_enabled:      bool  = True
app_running:      bool  = True

_presence_start_ts: float | None = None
_last_title:        str          = ""
_cover_cache:       dict         = {}

log_lines:      list  = []
_log_widget           = None
_status_labels: dict  = {}
_site_vars:     dict  = {}
_card_frames:   dict  = {}
_app_ref              = None

# ──────────────────────────────────────────────────────────────────────────────
# Logging
# ──────────────────────────────────────────────────────────────────────────────
def log(msg: str):
    ts   = time.strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    log_lines.append(line)
    if len(log_lines) > 400:
        log_lines.pop(0)
    if _log_widget:
        try:
            _log_widget.configure(state="normal")
            _log_widget.insert("end", line + "\n")
            _log_widget.see("end")
            _log_widget.configure(state="disabled")
        except Exception:
            pass

# ──────────────────────────────────────────────────────────────────────────────
# Config
# ──────────────────────────────────────────────────────────────────────────────
def load_config() -> dict:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
            merged = DEFAULT_CONFIG.copy()
            merged.update({k: v for k, v in saved.items() if k != "sites"})
            merged["sites"] = {k: v.copy() for k, v in DEFAULT_SITES.items()}
            for key, val in saved.get("sites", {}).items():
                if key in merged["sites"]:
                    merged["sites"][key].update(val)
                else:
                    merged["sites"][key] = val
            return merged
        except Exception:
            pass
    return {k: (v.copy() if isinstance(v, dict) else v) for k, v in DEFAULT_CONFIG.items()}

def save_config():
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

# ──────────────────────────────────────────────────────────────────────────────
# Windows startup registry
# ──────────────────────────────────────────────────────────────────────────────
def _exe_path() -> str:
    return sys.executable if getattr(sys, "frozen", False) else os.path.abspath(__file__)

def get_startup_state() -> bool:
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, STARTUP_KEY, 0, winreg.KEY_READ)
        winreg.QueryValueEx(key, APP_NAME)
        winreg.CloseKey(key)
        return True
    except Exception:
        return False

def set_startup(enabled: bool):
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, STARTUP_KEY, 0, winreg.KEY_SET_VALUE)
        if enabled:
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, f'"{_exe_path()}"')
            log("[Startup] Added to Windows startup")
        else:
            try:
                winreg.DeleteValue(key, APP_NAME)
                log("[Startup] Removed from Windows startup")
            except FileNotFoundError:
                pass
        winreg.CloseKey(key)
        config["launch_on_start"] = enabled
        save_config()
    except Exception as e:
        log(f"[Startup] Registry error: {e}")

# ──────────────────────────────────────────────────────────────────────────────
# Anime cover-art
# ──────────────────────────────────────────────────────────────────────────────
def _normalise_anime_title(title: str) -> str:
    """Strip episode/season suffixes so AniList/Jikan get a clean search term."""
    import re
    title = re.sub(r'\s*[-–:]\s*(?:odcinek|episode|odc\.?|ep\.?|sezon|season)\s*\d+.*$', '', title, flags=re.I)
    title = re.sub(r'\s*[Ss]\d+[Ee]\d+.*$', '', title)
    title = re.sub(r'\s*\(\d{4}\)\s*$', '', title)
    return title.strip()


def fetch_anime_cover(title: str) -> str:
    """Fetch anime cover from AniList GraphQL API."""
    if not title:
        return ""

    if title in _cover_cache and _cover_cache[title]:
        return _cover_cache[title]

    _neg_key = f"__neg__{title}"
    if _neg_key in _cover_cache:
        if time.time() - _cover_cache[_neg_key] < 120:
            return ""
        del _cover_cache[_neg_key]

    search_title = _normalise_anime_title(title)
    if not search_title:
        return ""

    candidates = [search_title]
    if title != search_title:
        candidates.append(title)

    q = """
    query ($search: String) {
      Media(search: $search, type: ANIME, sort: SEARCH_MATCH) {
        coverImage {
          extraLarge
          large
        }
        title {
          romaji
          english
        }
      }
    }
    """

    for search in candidates:
        try:
            r   = _http_post_json(
                "https://graphql.anilist.co",
                {"query": q, "variables": {"search": search}},
                timeout=6,
            )
            img = r["data"]["Media"]["coverImage"]
            url = img.get("extraLarge") or img.get("large") or ""
            if url:
                _cover_cache[title] = url
                log(f"[Cover] AniList '{search}': {url[:70]}")
                return url
        except Exception as e:
            log(f"[Cover] AniList error for '{search}': {e}")

    _cover_cache[_neg_key] = time.time()
    log(f"[Cover] AniList: no result for '{search_title}'")
    return ""

def youtube_thumbnail(video_id: str) -> str:
    if not video_id:
        return ""
    return f"https://img.youtube.com/vi/{video_id}/mqdefault.jpg"

# ──────────────────────────────────────────────────────────────────────────────
# Time helpers
# ──────────────────────────────────────────────────────────────────────────────
def fmt_time(s) -> str:
    if s is None or s < 0: return "0:00"
    m, s = divmod(int(s), 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"

def time_str(data: dict) -> str:
    cur, tot = data.get("current_time"), data.get("total_time")
    if cur is not None and tot is not None:
        return f"{fmt_time(cur)} / {fmt_time(tot)}"
    return ""

# ──────────────────────────────────────────────────────────────────────────────
# RPC payload builder
# ──────────────────────────────────────────────────────────────────────────────
def build_payload(data: dict) -> dict | None:
    global _presence_start_ts, _last_title

    if not rpc_enabled:
        return None

    site     = data.get("site", "")
    site_cfg = config["sites"].get(site, {})

    if not site_cfg.get("enabled", True):
        return None

    privacy  = site_cfg.get("privacy", False)
    category = site_cfg.get("category", "other")
    ts       = time_str(data)
    is_anime = category == "anime" or site in ("shinden", "ogladajanime")
    paused   = data.get("paused", False)

    title_key = data.get("title") or data.get("streamer") or ""
    if title_key != _last_title:
        _last_title        = title_key
        _presence_start_ts = time.time()

    act_name = config.get("activity_type", "Watching")
    act_type = _ACTIVITY_TYPES.get(act_name, _AT_WATCHING)

    hide_time = site_cfg.get("incognito_time", False)
    if hide_time and privacy:
        ts = ""

    display_name = (site_cfg.get("display_name") or site_cfg.get("name") or site).strip()

    default_img = site_cfg.get("large_image", "")
    large_image = default_img

    if not privacy:
        if site == "youtube" and data.get("video_id"):
            thumb = youtube_thumbnail(data["video_id"])
            if thumb:
                large_image = thumb
        elif is_anime and title_key:
            page_cover = data.get("cover_url", "").strip()
            cover      = page_cover or fetch_anime_cover(title_key)
            if cover:
                large_image = cover

    small_image = "paused_icon" if paused else "playing_icon"
    small_text  = "Paused" if paused else "Playing"

    payload: dict = {
        "large_image":   large_image,
        "large_text":    display_name,
        "small_image":   small_image,
        "small_text":    small_text,
        "activity_type": act_type,
        "start":         int(_presence_start_ts) if _presence_start_ts else None,
    }

    if site in ("youtube", "cda", "rumble"):
        if privacy:
            payload["details"] = "Watching a Video"
            payload["state"]   = (ts if ts else None)
        else:
            payload["details"] = (data.get("title") or "Unknown video")[:128]
            payload["state"]   = (ts if ts else None)

    elif site == "netflix":
        if privacy:
            payload["details"] = "Watching Netflix"
            payload["state"]   = (ts if ts else None)
        else:
            payload["details"] = (data.get("title") or "Unknown title")[:128]
            ep = data.get("episode", "")
            payload["state"]   = ((f"Ep. {ep} · " if ep else "") + (ts or ""))[:128]

    elif site == "twitch":
        if privacy:
            payload["details"] = "Twitch"
            payload["state"]   = "Live"
        else:
            streamer = data.get("streamer") or ""
            game = data.get("game", "")
            title = data.get("title") or streamer or "Unknown Stream"
            
            payload["details"] = title[:128]
            
            # Format state as "Streamer · Game" or just "Streamer" or "Live"
            state_parts = [p for p in (streamer, game) if p]
            payload["state"] = (" · ".join(state_parts) if state_parts else "Live")[:128]

    elif is_anime:
        if privacy:
            payload["details"] = "Watching Anime"
            payload["state"]   = (ts if ts else None)
        else:
            import re as _re
            raw_title = data.get("title") or "Unknown anime"
            clean_title = _re.sub(
                r'\s*[-–|]\s*(?:ogl[\u0105]daj\s*anime|ogladajanime|shinden\.?pl|shinden|animesub|anime\.?).*$',
                "", raw_title, flags=_re.I | _re.UNICODE).strip() or raw_title
            clean_title = clean_title.rstrip(" -–|").strip() or raw_title
            payload["details"] = clean_title[:80]
            ep = data.get("episode", "")
            payload["state"]   = ((f"Ep. {ep} · " if ep else "") + (ts or ""))[:128]

    else:
        if privacy:
            payload["details"] = f"Browsing {display_name}"
            payload["state"]   = ts or ""
        else:
            payload["details"] = (data.get("title") or display_name)[:128]
            payload["state"]   = (ts or "")[:128]

    return {k: v for k, v in payload.items() if v not in (None, "")}

# ──────────────────────────────────────────────────────────────────────────────
# Discord RPC client
# ──────────────────────────────────────────────────────────────────────────────
def connect_rpc(app_id: str) -> bool:
    global rpc_client, rpc_connected
    if not PYPRESENCE_OK:
        return False
    if rpc_client:
        try: rpc_client.close()
        except Exception: pass
        rpc_client = None
    last_err = None
    for pipe in range(10):
        try:
            c = Presence(app_id, pipe=pipe)
            c.connect()
            rpc_client = c
            rpc_connected = True
            log(f"[RPC] Connected pipe={pipe} id={app_id[:8]}…")
            _refresh_rpc_label()
            return True
        except Exception as e:
            last_err = e
    rpc_connected = False
    log(f"[RPC] All pipes failed: {last_err}")
    _refresh_rpc_label()
    return False

def update_rpc(payload: dict):
    global rpc_connected
    if not rpc_client or not rpc_connected:
        return
    try:
        rpc_client.update(**payload)
    except Exception as e:
        log(f"[RPC] Update error: {e}")
        rpc_connected = False
        _refresh_rpc_label()

def clear_rpc():
    if rpc_client and rpc_connected:
        try:
            rpc_client.clear()
            log("[RPC] Status Cleared")
        except Exception:
            pass

# ──────────────────────────────────────────────────────────────────────────────
# HTTP server
# ──────────────────────────────────────────────────────────────────────────────
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def _cors(self, code=200):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_OPTIONS(self): self._cors()

    def do_POST(self):
        global current_presence
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        try:
            data     = json.loads(body)
            site     = data.get("site", "")
            site_cfg = config["sites"].get(site, {})

            if not rpc_enabled or not site_cfg.get("enabled", True):
                self._cors()
                self.wfile.write(b'{"ok":true,"skipped":true}')
                return

            current_presence = data
            _gui_update_status(data)

            app_id = site_cfg.get("discord_app_id", "").strip()
            if app_id:
                if not rpc_connected:
                    connect_rpc(app_id)
                threading.Thread(target=_rpc_bg, args=(data,), daemon=True).start()
            else:
                log(f"[Server] {site}: no App ID")

            log(f"[Server] {site} » {(data.get('title') or '')[:55]}")
            self._cors()
            self.wfile.write(b'{"ok":true}')
        except Exception as e:
            log(f"[Server] POST error: {e}")
            self._cors(400)
            self.wfile.write(b'{"ok":false}')

    def do_GET(self):
        if self.path == "/status":
            self._cors()
            self.wfile.write(json.dumps({
                "running": True, "rpc_connected": rpc_connected,
                "rpc_enabled": rpc_enabled, "current": current_presence,
                "sites": {k: {"enabled": v.get("enabled", True),
                              "privacy": v.get("privacy", False)}
                          for k, v in config["sites"].items()},
            }).encode())
        else:
            self._cors(404); self.wfile.write(b'{"ok":false}')

def _rpc_bg(data):
    p = build_payload(data)
    if p: update_rpc(p)

def run_server():
    port = config.get("server_port", 7591)
    try:
        srv = HTTPServer(("127.0.0.1", port), Handler)
        log(f"[Server] Listening on localhost:{port}")
        while app_running:
            srv.handle_request()
    except OSError as e:
        log(f"[Server] Cannot start on port {port}: {e}")

# ──────────────────────────────────────────────────────────────────────────────
# GUI helpers
# ──────────────────────────────────────────────────────────────────────────────
def _gui_update_status(data: dict):
    def _do():
        raw_site = data.get("site", "?")
        site  = (raw_site.upper().replace("_", ".") + ".COM") if raw_site and "." not in raw_site else raw_site.upper()
        title = (data.get("title") or "")[:65]
        ts    = time_str(data) or "—"
        if "site"  in _status_labels: _status_labels["site"].config(text=site)
        if "title" in _status_labels: _status_labels["title"].config(text=title or "—")
        if "time"  in _status_labels: _status_labels["time"].config(text=ts)
        _refresh_rpc_label()
        if "cover" in _status_labels and _app_ref:
            _app_ref.after(0, lambda: _update_cover_label(data))
    if _log_widget: _log_widget.after(0, _do)

_discord_asset_cache: dict[tuple, str] = {}

def _resolve_discord_asset_url(app_id: str, icon_key: str) -> str:
    cache_key = (app_id, icon_key)
    if cache_key in _discord_asset_cache:
        return _discord_asset_cache[cache_key]

    try:
        raw = _http_get(
            f"https://discord.com/api/v10/oauth2/applications/{app_id}/assets",
            timeout=5,
        )
        assets = json.loads(raw)
        for asset in assets:
            if asset.get("name") == icon_key:
                cdn = f"https://cdn.discordapp.com/app-assets/{app_id}/{asset['id']}.png"
                _discord_asset_cache[cache_key] = cdn
                log(f"[Asset] Resolved '{icon_key}' → {cdn[:60]}")
                return cdn
        _discord_asset_cache[cache_key] = ""
        log(f"[Asset] Key '{icon_key}' not found in App {app_id[:8]}… assets")
    except Exception as e:
        _discord_asset_cache[cache_key] = ""
        log(f"[Asset] Failed to fetch assets for {app_id[:8]}…: {e}")

    return ""

def _update_cover_label(data: dict):
    if "cover" not in _status_labels or _app_ref is None:
        return
    lbl = _status_labels["cover"]

    site     = data.get("site", "")
    site_cfg = config["sites"].get(site, {})
    privacy  = site_cfg.get("privacy", False)
    category = site_cfg.get("category", "other")
    is_anime = category == "anime" or site in ("shinden", "ogladajanime")

    def _load_and_display(img_url: str, fallback_text: str = ""):
        if not img_url:
            _app_ref.after(0, lambda t=fallback_text: lbl.config(image="", text=t))
            return
        if not TRAY_OK:
            _app_ref.after(0, lambda u=img_url: lbl.config(image="", text=u[:60]))
            return
        try:
            from io import BytesIO
            from PIL import ImageTk
            raw     = _http_get(img_url, timeout=6)
            pil_img = PilImage.open(BytesIO(raw)).convert("RGBA")
            pil_img.thumbnail((80, 80), PilImage.LANCZOS)
            photo   = ImageTk.PhotoImage(pil_img)
            def _apply(p=photo):
                if _app_ref:
                    _app_ref._cover_photo = p
                    lbl.config(image=p, text="")
            _app_ref.after(0, _apply)
        except Exception:
            _app_ref.after(0, lambda t=fallback_text: lbl.config(image="", text=t))

    def _resolve_and_show():
        icon_key = site_cfg.get("large_image", "")
        app_id   = site_cfg.get("discord_app_id", "").strip()

        if privacy:
            if app_id and icon_key:
                cdn_url = _resolve_discord_asset_url(app_id, icon_key)
                _load_and_display(cdn_url, fallback_text=icon_key)
            else:
                _app_ref.after(0, lambda: lbl.config(image="", text=icon_key or "—"))
            return

        img_url = ""

        if site == "youtube" and data.get("video_id"):
            img_url = youtube_thumbnail(data["video_id"])

        elif is_anime:
            img_url = data.get("cover_url", "").strip()
            if not img_url:
                title = data.get("title", "")
                if title:
                    img_url = fetch_anime_cover(title)

        if not img_url and app_id and icon_key:
            img_url = _resolve_discord_asset_url(app_id, icon_key)

        _load_and_display(img_url, fallback_text=icon_key or "—")

    threading.Thread(target=_resolve_and_show, daemon=True).start()

def _refresh_rpc_label():
    if "rpc" not in _status_labels:
        return
    if not rpc_enabled:
        _status_labels["rpc"].config(text="Status is currently paused and not visible", foreground=YELLOW)
    elif rpc_connected:
        _status_labels["rpc"].config(text="Connected", foreground=GREEN)
    else:
        _status_labels["rpc"].config(text="Disconnected", foreground=OVERLAY1)

def _update_card_dim(site_key: str):
    if site_key not in _card_frames:
        return
    outer, body, en_var = _card_frames[site_key]
    enabled = en_var.get()
    bg  = SURFACE0 if enabled else BG2
    fg  = TEXT     if enabled else OVERLAY0

    def _rec(w):
        try:
            cls = w.winfo_class()
            if cls == "Frame": w.configure(bg=bg)
            elif cls == "Label":
                if w.cget("fg") not in (ACCENT, MAUVE, GREEN, RED, YELLOW, PEACH, TEAL):
                    w.configure(fg=fg, bg=bg)
        except Exception: pass
        for c in w.winfo_children(): _rec(c)

    _rec(outer); _rec(body)

# ──────────────────────────────────────────────────────────────────────────────
# Toast notification
# ──────────────────────────────────────────────────────────────────────────────
def show_toast(root: tk.Tk, message: str = "Saved.", duration_ms: int = 2200):
    toast = tk.Toplevel(root)
    toast.overrideredirect(True)
    toast.attributes("-topmost", True)
    toast.configure(bg=SURFACE1)

    lbl = tk.Label(toast, text=f"  {message}  ",
                   fg=TEXT, bg=SURFACE1,
                   font=("Segoe UI", 10), padx=12, pady=7)
    lbl.pack()

    def _place():
        root.update_idletasks()
        rw = root.winfo_width()
        rx = root.winfo_rootx()
        ry = root.winfo_rooty()
        rh = root.winfo_height()
        tw = toast.winfo_reqwidth()
        th = toast.winfo_reqheight()
        x  = rx + (rw - tw) // 2
        y  = ry + rh - th - 24
        toast.geometry(f"+{x}+{y}")

    root.after(10, _place)

    fade_steps  = 20
    fade_delay  = 60
    hold_ms     = duration_ms - fade_steps * fade_delay

    def _fade(step=0):
        alpha = 1.0 - step / fade_steps
        try:
            toast.attributes("-alpha", alpha)
        except Exception:
            pass
        if step < fade_steps:
            toast.after(fade_delay, lambda: _fade(step + 1))
        else:
            toast.destroy()

    toast.after(max(hold_ms, 500), _fade)

# ──────────────────────────────────────────────────────────────────────────────
# System tray
# ──────────────────────────────────────────────────────────────────────────────
def _make_tray_image():
    if TRAY_OK and os.path.exists(ICON_FILE):
        try:
            return PilImage.open(ICON_FILE).resize((64, 64))
        except Exception:
            pass
    if not TRAY_OK:
        return None
    img  = PilImage.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse((2, 2, 62, 62), fill="#89b4fa")
    return img

def _run_tray():
    if not TRAY_OK:
        return
    img = _make_tray_image()
    if img is None:
        return

    sv = {"startup": get_startup_state()}

    def _show(icon, item):
        if _app_ref: _app_ref.after(0, _app_ref.deiconify)

    def _tog_startup(icon, item):
        sv["startup"] = not sv["startup"]
        set_startup(sv["startup"])

    def _quit(icon, item):
        clear_rpc()
        icon.stop()
        if _app_ref: _app_ref.after(0, _app_ref.quit)

    menu = pystray.Menu(
        pystray.MenuItem("Open", _show, default=True),
        pystray.MenuItem("Launch on Start", _tog_startup,
                         checked=lambda item: sv["startup"]),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Close App", _quit),
    )
    icon = pystray.Icon(APP_NAME, img, f"Discord RPC Tool - {APP_VERSION}", menu)
    icon.run()

# ──────────────────────────────────────────────────────────────────────────────
# Custom Tabbed Container
# ──────────────────────────────────────────────────────────────────────────────
class FlatNotebook(ttk.Frame):
    def __init__(self, parent, bg_color, accent_color, surface0_color, surface1_color, text_color, subtext0_color, bg2_color):
        super().__init__(parent)
        
        self.bg_color = bg_color
        self.accent_color = accent_color
        self.surface0_color = surface0_color
        self.surface1_color = surface1_color
        self.text_color = text_color
        self.subtext0_color = subtext0_color
        self.bg2_color = bg2_color

        self.tab_header = tk.Frame(self, bg=self.bg2_color)
        self.tab_header.pack(fill="x", side="top")

        self.content_container = ttk.Frame(self)
        self.content_container.pack(fill="both", expand=True)

        self.tabs = {}
        self.active_tab = None

    def add(self, child_frame, text="Tab"):
        tab_id = str(child_frame)
        
        btn = tk.Button(
            self.tab_header,
            text=text,
            font=("Segoe UI", 10, "bold"),
            bg=self.surface0_color,
            fg=self.subtext0_color,
            activebackground=self.surface1_color,
            activeforeground=self.text_color,
            bd=0,
            padx=20,
            pady=8,
            relief="flat",
            cursor="hand2",
            command=lambda: self.select(tab_id)
        )
        btn.pack(side="left", padx=(0, 2))

        self.tabs[tab_id] = {
            "button": btn,
            "frame": child_frame
        }

        if self.active_tab is None:
            self.select(tab_id)

    def select(self, tab_id):
        for t_id, data in self.tabs.items():
            if t_id == tab_id:
                data["button"].config(
                    bg=self.accent_color,
                    fg=self.bg2_color,
                    activebackground=self.accent_color,
                    activeforeground=self.bg2_color
                )
                data["frame"].pack(in_=self.content_container, fill="both", expand=True)
            else:
                data["button"].config(
                    bg=self.surface0_color,
                    fg=self.subtext0_color,
                    activebackground=self.surface1_color,
                    activeforeground=self.text_color
                )
                data["frame"].pack_forget()

        self.active_tab = tab_id

# ──────────────────────────────────────────────────────────────────────────────
# Main Application GUI
# ──────────────────────────────────────────────────────────────────────────────
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        global _app_ref, rpc_enabled
        _app_ref   = self
        rpc_enabled = config.get("rpc_enabled", True)

        self.title(f"Discord RPC Tool")
        self.geometry("872x680")
        self.minsize(680, 520)
        self.configure(bg=BG)

        if os.path.exists(ICON_FILE):
            try: self.iconbitmap(ICON_FILE)
            except Exception: pass

        self._apply_style()
        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._rpc_poll()

        if config.get("start_minimised", False):
            self.after(100, self.withdraw)

    def _apply_style(self):
        s = ttk.Style(self)
        s.theme_use("clam")
        
        s.configure(".", background=BG, foreground=TEXT,
                    font=("Segoe UI", 10), borderwidth=0, relief="flat")
        s.configure("TFrame", background=BG)
        s.configure("TLabel", background=BG, foreground=TEXT)
        s.configure("TCheckbutton", background=BG, foreground=SUBTEXT1,
                    indicatorcolor=SURFACE0, selectcolor=ACCENT, focuscolor=BG)
        s.map("TCheckbutton", background=[("active", BG)], foreground=[("active", TEXT)])
        
        s.configure("Card.TCheckbutton", background=SURFACE0, foreground=SUBTEXT1,
                    indicatorcolor=SURFACE1, selectcolor=ACCENT, focuscolor=SURFACE0)
        s.map("Card.TCheckbutton", background=[("active", SURFACE0)], foreground=[("active", TEXT)])

        s.configure("TEntry", fieldbackground=SURFACE0, foreground=TEXT,
                    insertcolor=TEXT, relief="flat",
                    bordercolor=SURFACE1, lightcolor=SURFACE0, darkcolor=SURFACE0)
        s.configure("TButton", background=SURFACE1, foreground=TEXT,
                    relief="flat", padding=(12, 5))
        s.map("TButton", background=[("active", SURFACE2)], foreground=[("active", TEXT)])
        
        s.configure("Accent.TButton", background=ACCENT, foreground=BG2,
                    relief="flat", padding=(12, 5), font=("Segoe UI", 10, "bold"))
        s.map("Accent.TButton", background=[("active", MAUVE)], foreground=[("active", BG2)])
        
        s.configure("TScrollbar", background=SURFACE0, troughcolor=BG2,
                    relief="flat", borderwidth=0, arrowcolor=OVERLAY1)
        s.map("TScrollbar", background=[("active", SURFACE1)])
        
        s.configure("Treeview", background=SURFACE0, foreground=TEXT,
                    fieldbackground=SURFACE0, rowheight=26, borderwidth=0)
        s.configure("Treeview.Heading", background=SURFACE1, foreground=SUBTEXT0,
                    relief="flat", font=("Segoe UI", 9, "bold"))
        s.map("Treeview", background=[("selected", ACCENT)], foreground=[("selected", BG2)])
        
        s.configure("TCombobox", fieldbackground=SURFACE0, background=SURFACE0,
                    foreground=TEXT, selectbackground=ACCENT, selectforeground=BG2,
                    arrowcolor=OVERLAY1)
        s.map("TCombobox", fieldbackground=[("readonly", SURFACE0)],
              background=[("active", SURFACE1)])

    # ── Top-level layout ────────────────────────────────────────────────────────
    def _build_ui(self):
        hdr = tk.Frame(self, bg=BG2)
        hdr.pack(fill="x")
        ih = tk.Frame(hdr, bg=BG2)
        ih.pack(fill="x", padx=18, pady=10)
        tk.Label(ih, text="Discord RPC",
                 font=("Segoe UI", 14, "bold"), fg=ACCENT, bg=BG2).pack(side="left")

        tk.Frame(self, height=1, bg=SURFACE1).pack(fill="x")

        # Custom Flat Notebook replacing default ttk.Notebook
        self.notebook = FlatNotebook(
            parent=self, 
            bg_color=BG, 
            accent_color=ACCENT, 
            surface0_color=SURFACE0, 
            surface1_color=SURFACE1, 
            text_color=TEXT, 
            subtext0_color=SUBTEXT0, 
            bg2_color=BG2
        )
        self.notebook.pack(fill="both", expand=True)

        self._build_tab_status(self.notebook)
        self._build_tab_sites(self.notebook)
        self._build_tab_settings(self.notebook)
        self._build_tab_log(self.notebook)
        self._build_tab_about(self.notebook)

    # ── Tab: Status ─────────────────────────────────────────────────────────────
    def _build_tab_status(self, nb):
        frame = ttk.Frame(nb)
        nb.add(frame, text="Status")

        card = tk.Frame(frame, bg=SURFACE0)
        card.pack(fill="x", padx=16, pady=(16, 8))

        tk.Label(card, text="Current Status",
                 font=("Segoe UI", 10, "bold"), fg=ACCENT, bg=SURFACE0).pack(
                     anchor="w", padx=14, pady=(10, 6))
        tk.Frame(card, height=1, bg=SURFACE1).pack(fill="x", padx=14)

        grid = tk.Frame(card, bg=SURFACE0)
        grid.pack(fill="x", padx=14, pady=8)
        grid.columnconfigure(1, weight=1)

        for i, (lbl, key) in enumerate([("Site:", "site"), ("Title:", "title"), ("Time:", "time")]):
            tk.Label(grid, text=lbl, fg=OVERLAY0, bg=SURFACE0,
                     font=("Segoe UI", 9)).grid(row=i, column=0, sticky="w",
                                                 pady=4, padx=(0, 16))
            v = tk.Label(grid, text="—", fg=TEXT, bg=SURFACE0, font=("Segoe UI", 10))
            v.grid(row=i, column=1, sticky="w", pady=4)
            _status_labels[key] = v

        tk.Label(grid, text="Cover:", fg=OVERLAY0, bg=SURFACE0,
                 font=("Segoe UI", 9)).grid(row=3, column=0, sticky="nw",
                                             pady=(6, 4), padx=(0, 16))
        cover_lbl = tk.Label(grid, bg=SURFACE0, text="—", fg=OVERLAY0,
                             font=("Segoe UI", 9))
        cover_lbl.grid(row=3, column=1, sticky="w", pady=(6, 4))
        _status_labels["cover"] = cover_lbl
        self._cover_photo = None

        tk.Frame(card, height=1, bg=SURFACE1).pack(fill="x", padx=14)
        rpc_row = tk.Frame(card, bg=SURFACE0)
        rpc_row.pack(fill="x", padx=14, pady=8)
        tk.Label(rpc_row, text="Status:", fg=OVERLAY0, bg=SURFACE0,
                 font=("Segoe UI", 9)).pack(side="left", padx=(0, 10))
        rpc_lbl = tk.Label(rpc_row, text="Disconnected", fg=OVERLAY1,
                           bg=SURFACE0, font=("Segoe UI", 10))
        rpc_lbl.pack(side="left")
        _status_labels["rpc"] = rpc_lbl

        btn_row = tk.Frame(frame, bg=BG)
        btn_row.pack(fill="x", padx=16, pady=8)

        self._rpc_master_var = tk.BooleanVar(value=rpc_enabled)
        self._master_btn = tk.Button(
            btn_row,
            text="Disabled" if not rpc_enabled else "Enabled",
            bg="#3b1a25" if not rpc_enabled else "#1e3a2a",
            fg=RED   if not rpc_enabled else GREEN,
            activebackground=SURFACE2, activeforeground=TEXT,
            relief="flat", bd=0, padx=12, pady=4,
            font=("Segoe UI", 9), cursor="hand2",
            command=self._toggle_master)
        self._master_btn.pack(side="left", padx=(0, 8))

        self._mk_danger_btn(btn_row, "Clear Status",
                            self._clear_activity).pack(side="left")

        guide = tk.Frame(frame, bg=SURFACE0)
        guide.pack(fill="x", padx=16, pady=8)
        tk.Label(guide, text="How to setup your own discord application",
                 font=("Segoe UI", 10, "bold"), fg=ACCENT, bg=SURFACE0).pack(
                     anchor="w", padx=14, pady=(10, 4))
        for s in [
            "1.  Create an application at discord.com/developers/applications",
            "2.  Copy Application ID → paste it in the Sites tab",
            "3.  Upload icon art in Rich Presence → Art Assets",
            "4.  Install the .user.js file in the Tampermonkey extension",
            "5.  Open any supported site – activity will appear here",
        ]:
            tk.Label(guide, text=s, fg=SUBTEXT0, bg=SURFACE0,
                     font=("Segoe UI", 9)).pack(anchor="w", padx=14, pady=1)
        ttk.Button(guide, text="🌐 Open discord.com/developers",
                   command=lambda: webbrowser.open(
                       "https://discord.com/developers/applications")
                   ).pack(anchor="w", padx=14, pady=(8, 0))
        tk.Frame(guide, height=8, bg=SURFACE0).pack()

    def _toggle_master(self):
        global rpc_enabled
        rpc_enabled = not rpc_enabled
        config["rpc_enabled"] = rpc_enabled
        save_config()
        if not rpc_enabled:
            clear_rpc()
            self._master_btn.config(text="Disabled",
                                    bg="#3b1a25", fg=RED)
        else:
            self._master_btn.config(text="Enabled",
                                    bg="#1e3a2a", fg=GREEN)
        _refresh_rpc_label()
        log(f"[RPC] Status: {'ON' if rpc_enabled else 'OFF'}")

    def _clear_activity(self):
        global current_presence
        clear_rpc()
        current_presence = {}
        for k in ("site", "title", "time"):
            if k in _status_labels: _status_labels[k].config(text="—")
        log("[GUI] Activity manually cleared")

    # ── Tab: Sites ──────────────────────────────────────────────────────────────
    CARD_W   = 415
    CARD_H   = 178
    GRID_PAD = 8

    def _build_tab_sites(self, nb):
        outer = ttk.Frame(nb)
        nb.add(outer, text="Sites")

        tb  = tk.Frame(outer, bg=BG2)
        tb.pack(fill="x")
        tbi = tk.Frame(tb, bg=BG2)
        tbi.pack(fill="x", padx=16, pady=8)

        ttk.Button(tbi, text="Save All Sites", style="Accent.TButton",
                   command=self._save_all_sites).pack(side="left", padx=(0, 8))
        ttk.Button(tbi, text="Set App ID for All…",
                   command=self._bulk_app_id).pack(side="left", padx=(0, 8))

        self._show_hidden_var = tk.BooleanVar(value=False)
        self._show_hidden_btn = tk.Button(
            tbi,
            text="Show Hidden",
            bg=SURFACE1, fg=SUBTEXT0,
            activebackground=SURFACE2, activeforeground=TEXT,
            relief="flat", bd=0, padx=10, pady=4,
            font=("Segoe UI", 9), cursor="hand2",
            command=self._toggle_show_hidden,
        )
        self._show_hidden_btn.pack(side="right")

        tk.Frame(outer, height=1, bg=SURFACE1).pack(fill="x")

        self._sites_canvas = tk.Canvas(outer, bg=BG, bd=0, highlightthickness=0)
        vsb = ttk.Scrollbar(outer, orient="vertical", command=self._sites_canvas.yview)
        self._sites_canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self._sites_canvas.pack(side="left", fill="both", expand=True)

        self._sites_inner = tk.Frame(self._sites_canvas, bg=BG)
        self._sites_wid   = self._sites_canvas.create_window(
            (0, 0), window=self._sites_inner, anchor="nw")

        self._sites_inner.bind("<Configure>", self._on_sites_inner_configure)
        self._sites_canvas.bind("<Configure>", self._on_sites_canvas_configure)
        self._sites_canvas.bind("<Enter>", lambda e: self._sites_canvas.bind_all(
            "<MouseWheel>", lambda ev: self._sites_canvas.yview_scroll(
                -1 * (ev.delta // 120), "units")))
        self._sites_canvas.bind("<Leave>",
            lambda e: self._sites_canvas.unbind_all("<MouseWheel>"))

        self._sites_all_cards: list[tuple] = []
        self._sites_card_list: list[tk.Frame] = []
        self._sites_cat_headers: list[tk.Frame] = []

        dev = config.get("dev_mode", False)

        by_cat: dict[str, list] = {}
        for key, data in config["sites"].items():
            by_cat.setdefault(data.get("category", "other"), []).append((key, data))

        cat_order = ["video", "stream", "music", "anime", "other"]
        remaining_cats = [c for c in by_cat if c not in cat_order]

        for cat in cat_order + remaining_cats:
            entries = by_cat.get(cat, [])
            for site_key, site_data in entries:
                if site_data.get("hidden", False) and not dev:
                    card = self._make_site_card(self._sites_inner, site_key, site_data)
                    self._sites_all_cards.append((site_key, site_data, cat, card, True))
                else:
                    card = self._make_site_card(self._sites_inner, site_key, site_data)
                    self._sites_all_cards.append((site_key, site_data, cat, card, False))

        self._refresh_sites_grid()

    def _toggle_show_hidden(self):
        showing = self._show_hidden_var.get()
        self._show_hidden_var.set(not showing)
        if not showing:
            self._show_hidden_btn.config(
                text="Show All", bg="#3a2a1e", fg=PEACH)
        else:
            self._show_hidden_btn.config(
                text="Show Hidden", bg=SURFACE1, fg=SUBTEXT0)
        self._refresh_sites_grid()

    def _refresh_sites_grid(self):
        show_hidden_mode = self._show_hidden_var.get()

        for h in self._sites_cat_headers:
            h.destroy()
        self._sites_cat_headers = []

        if show_hidden_mode:
            visible = [
                (k, d, cat, card)
                for k, d, cat, card, _is_h in self._sites_all_cards
                if config["sites"].get(k, {}).get("hidden", False)
            ]
        else:
            visible = [
                (k, d, cat, card)
                for k, d, cat, card, _is_h in self._sites_all_cards
                if not config["sites"].get(k, {}).get("hidden", False)
            ]

        seen_cats: list[str] = []
        cat_groups: dict[str, list] = {}
        for k, d, cat, card in visible:
            if cat not in cat_groups:
                seen_cats.append(cat)
                cat_groups[cat] = []
            cat_groups[cat].append((k, d, card))

        for widget in self._sites_inner.winfo_children():
            widget.pack_forget()
            widget.place_forget()

        self._sites_card_list = []

        if not visible:
            lbl = tk.Label(self._sites_inner,
                           text="No hidden sites." if show_hidden_mode else "No sites.",
                           fg=OVERLAY0, bg=BG, font=("Segoe UI", 10))
            lbl.pack(pady=40)
            self._sites_cat_headers.append(lbl)
            self._sites_inner.configure(height=100)
            self._sites_canvas.configure(scrollregion=(0, 0, 0, 100))
            return

        PAD  = self.GRID_PAD
        CW   = self.CARD_W
        CH   = self.CARD_H

        canvas_w = self._sites_canvas.winfo_width() or 860
        cols = max(1, canvas_w // (CW + PAD))

        used_w  = cols * (CW + PAD) - PAD
        offset  = max(0, (canvas_w - used_w) // 2)

        total_h = PAD

        for cat in seen_cats:
            entries = cat_groups[cat]
            label_text = CATEGORY_LABELS.get(cat, cat.title()).upper()

            hdr_frame = tk.Frame(self._sites_inner, bg=BG, height=28)
            hdr_frame.place(x=0, y=total_h, relwidth=1.0)
            hdr_frame.pack_propagate(False)

            tk.Label(hdr_frame, text=f"  {label_text}",
                     font=("Segoe UI", 8, "bold"), fg=MAUVE, bg=BG).pack(
                         side="left", pady=4)
            tk.Frame(hdr_frame, height=1, bg=SURFACE1).pack(
                side="left", fill="x", expand=True, padx=(8, PAD), pady=12)

            self._sites_cat_headers.append(hdr_frame)
            total_h += 30

            n_rows = (len(entries) + cols - 1) // cols
            for idx, (k, d, card) in enumerate(entries):
                col = idx % cols
                row = idx // cols
                x   = offset + col * (CW + PAD)
                y   = total_h + row * (CH + PAD)
                card.place(x=x, y=y, width=CW, height=CH)
                self._sites_card_list.append(card)

            total_h += n_rows * (CH + PAD) + PAD

        self._sites_inner.configure(width=canvas_w, height=total_h)
        self._sites_canvas.configure(scrollregion=(0, 0, canvas_w, total_h))
        self._sites_canvas.yview_moveto(0)

    def _on_sites_inner_configure(self, event=None):
        self._sites_canvas.configure(scrollregion=self._sites_canvas.bbox("all"))

    def _on_sites_canvas_configure(self, event=None):
        w = event.width if event else self._sites_canvas.winfo_width()
        self._sites_canvas.itemconfig(self._sites_wid, width=w)
        self._relayout_grid(w)

    def _relayout_grid(self, canvas_w: int):
        if not hasattr(self, "_sites_all_cards") or not self._sites_all_cards:
            return
        self._refresh_sites_grid()

    def _make_site_card(self, parent, site_key: str, site_data: dict) -> tk.Frame:
        card = tk.Frame(parent, bg=SURFACE0)

        hdr = tk.Frame(card, bg=SURFACE0)
        hdr.pack(fill="x", padx=10, pady=(10, 0))
        tk.Label(hdr, text=site_data.get("name", site_key),
                 font=("Segoe UI", 10, "bold"), fg=TEXT, bg=SURFACE0).pack(side="left")

        def _clear_this(key=site_key):
            global current_presence
            if current_presence.get("site") == key:
                clear_rpc(); current_presence = {}
                for k in ("site","title","time"):
                    if k in _status_labels: _status_labels[k].config(text="—")
                log(f"[GUI] Cleared: {key}")
            else:
                log(f"[GUI] {key} not active")

        self._mk_danger_btn(hdr, "✕", _clear_this).pack(side="right")

        def _remove_site(key=site_key):
            if key in DEFAULT_SITES:
                show_toast(self, f"Cannot remove built-in site '{key}'")
                return
            if key in config["sites"]:
                del config["sites"][key]
            if key in _site_vars:
                del _site_vars[key]
            if key in _card_frames:
                del _card_frames[key]
            self._sites_all_cards = [
                e for e in self._sites_all_cards if e[0] != key
            ]
            save_config()
            log(f"[Config] Removed site: {key}")
            self.after(50, self._refresh_sites_grid)

        remove_btn = tk.Button(
            hdr, text="Remove",
            bg=SURFACE1, fg=OVERLAY0,
            activebackground=RED, activeforeground=BG2,
            relief="flat", bd=0, padx=8, pady=2,
            font=("Segoe UI", 8), cursor="hand2",
            command=_remove_site,
        )
        if site_key not in DEFAULT_SITES:
            remove_btn.pack(side="right", padx=(0, 4))

        hid_var = tk.BooleanVar(value=site_data.get("hidden", False))

        def _toggle_hidden(key=site_key, v=hid_var, btn_ref=[None]):
            new_val = not v.get()
            v.set(new_val)
            config["sites"][key]["hidden"] = new_val
            save_config()
            btn = btn_ref[0]
            if btn:
                if new_val:
                    btn.config(text="● Hidden", bg="#2a2a1e", fg=YELLOW)
                else:
                    btn.config(text="Hide", bg=SURFACE1, fg=SUBTEXT0)
            if hasattr(self, "_refresh_sites_grid"):
                self.after(50, self._refresh_sites_grid)

        hide_btn = tk.Button(
            hdr,
            text="● Hidden" if site_data.get("hidden", False) else "Hide",
            bg="#2a2a1e" if site_data.get("hidden", False) else SURFACE1,
            fg=YELLOW if site_data.get("hidden", False) else SUBTEXT0,
            activebackground=SURFACE2, activeforeground=TEXT,
            relief="flat", bd=0, padx=8, pady=2,
            font=("Segoe UI", 8), cursor="hand2",
            command=_toggle_hidden,
        )
        hide_btn.pack(side="right", padx=(0, 6))
        _toggle_hidden.__defaults__ = (site_key, hid_var, [hide_btn])

        tog = tk.Frame(card, bg=SURFACE0)
        tog.pack(fill="x", padx=10, pady=(4, 2))

        en_var = tk.BooleanVar(value=site_data.get("enabled", True))
        pr_var = tk.BooleanVar(value=site_data.get("privacy", False))
        _site_vars[site_key] = {"enabled": en_var, "privacy": pr_var}

        def _tog_en(key=site_key, v=en_var):
            config["sites"][key]["enabled"] = v.get()
            _update_card_dim(key)

        def _tog_pr(key=site_key, v=pr_var):
            config["sites"][key]["privacy"] = v.get()

        ttk.Checkbutton(tog, text="Enabled", variable=en_var, command=_tog_en,
                        style="Card.TCheckbutton").pack(side="left", padx=(0, 10))
        ttk.Checkbutton(tog, text="Incognito Mode", variable=pr_var, command=_tog_pr,
                        style="Card.TCheckbutton").pack(side="left", padx=(0, 10))

        it_var = tk.BooleanVar(value=site_data.get("incognito_time", False))
        def _tog_it(key=site_key, v=it_var):
            config["sites"][key]["incognito_time"] = v.get()
        ttk.Checkbutton(tog, text="Hide Time (Requires Incognito)", variable=it_var,
                        command=_tog_it,
                        style="Card.TCheckbutton").pack(side="left")
        _site_vars[site_key]["it_var"] = it_var

        body = tk.Frame(card, bg=SURFACE0)
        body.pack(fill="x", padx=10, pady=(4, 6))
        body.columnconfigure(1, weight=1)

        id_var  = tk.StringVar(value=site_data.get("discord_app_id", ""))
        dn_var  = tk.StringVar(value=site_data.get("display_name", site_data.get("name", "")))
        img_var = tk.StringVar(value=site_data.get("large_image", ""))
        txt_var = tk.StringVar(value=site_data.get("large_text", ""))

        for ri, (lbl, var) in enumerate([
            ("Application ID:", id_var),
            ("Display name:",   dn_var),
            ("Icon key:",       img_var),
            ("Icon tooltip:",   txt_var),
        ]):
            tk.Label(body, text=lbl, fg=OVERLAY0, bg=SURFACE0,
                     font=("Segoe UI", 9)).grid(row=ri, column=0, sticky="w",
                                                padx=(0, 8), pady=1)
            ttk.Entry(body, textvariable=var).grid(row=ri, column=1,
                                                   sticky="ew", pady=1)

        _site_vars[site_key]["id_var"]  = id_var
        _site_vars[site_key]["dn_var"]  = dn_var
        _site_vars[site_key]["img_var"] = img_var
        _site_vars[site_key]["txt_var"] = txt_var

        tk.Frame(card, height=1, bg=SURFACE1).pack(fill="x", side="bottom")
        _card_frames[site_key] = (card, body, en_var)
        _update_card_dim(site_key)
        return card

    # ── Bulk actions ────────────────────────────────────────────────────────────
    def _save_all_sites(self):
        for key, vd in _site_vars.items():
            cfg = config["sites"].get(key)
            if not cfg: continue
            cfg["enabled"]        = vd["enabled"].get()
            cfg["privacy"]        = vd["privacy"].get()
            cfg["hidden"]         = config["sites"].get(key, {}).get("hidden", False)
            cfg["incognito_time"] = vd.get("it_var", tk.BooleanVar()).get() if "it_var" in vd else config["sites"].get(key, {}).get("incognito_time", False)
            cfg["discord_app_id"] = vd.get("id_var",  tk.StringVar()).get().strip()
            cfg["display_name"]   = vd.get("dn_var",  tk.StringVar()).get().strip()
            cfg["large_image"]    = vd.get("img_var", tk.StringVar()).get().strip()
            cfg["large_text"]     = vd.get("txt_var", tk.StringVar()).get().strip()
        save_config()
        log("[Config] All sites saved")
        show_toast(self, "Saved.")

    def _bulk_app_id(self):
        win = tk.Toplevel(self)
        win.title("Set Application ID for All Sites")
        win.geometry("460x190")
        win.configure(bg=BG)
        win.grab_set()
        win.resizable(False, False)

        tk.Label(win, text="Set Application ID for All Sites",
                 font=("Segoe UI", 12, "bold"), fg=ACCENT, bg=BG).pack(
                     anchor="w", padx=18, pady=(16, 4))
        tk.Label(win,
                 text="Overwrites the Application ID for every site.\n"
                      "Useful when using one Discord application for all presence.",
                 fg=SUBTEXT0, bg=BG, font=("Segoe UI", 9), justify="left").pack(
                     anchor="w", padx=18)

        row = tk.Frame(win, bg=BG)
        row.pack(fill="x", padx=18, pady=12)
        row.columnconfigure(1, weight=1)

        tk.Label(row, text="Application ID:", fg=OVERLAY0, bg=BG,
                 font=("Segoe UI", 9)).grid(row=0, column=0, sticky="w", padx=(0, 10))
        id_var = tk.StringVar(value=DEFAULT_APP_ID)
        ttk.Entry(row, textvariable=id_var).grid(row=0, column=1, sticky="ew")

        def _apply():
            new_id = id_var.get().strip()
            if not new_id:
                return
            for key in config["sites"]:
                config["sites"][key]["discord_app_id"] = new_id
                if key in _site_vars and "id_var" in _site_vars[key]:
                    _site_vars[key]["id_var"].set(new_id)
            save_config()
            log(f"[Config] Bulk App ID: {new_id[:8]}…")
            win.destroy()
            show_toast(self, "App ID applied to all sites.")

        ttk.Button(row, text="Apply to All", style="Accent.TButton",
                   command=_apply).grid(row=1, column=1, sticky="e", pady=(10, 0))

    def _add_custom_site(self):
        win = tk.Toplevel(self)
        win.title("Add Custom Site")
        win.geometry("440x280")
        win.configure(bg=BG)
        win.grab_set()
        win.resizable(False, False)

        tk.Label(win, text="Add Custom Site",
                 font=("Segoe UI", 12, "bold"), fg=ACCENT, bg=BG).pack(
                     anchor="w", padx=18, pady=(16, 8))

        form = tk.Frame(win, bg=BG)
        form.pack(fill="x", padx=18)
        form.columnconfigure(1, weight=1)

        defs = [("Key (e.g. twitch):", "key"),
                ("Display name:",       "name"),
                ("Category:",           "category"),
                ("Application ID:",     "discord_app_id"),
                ("Icon key:",           "large_image")]
        fv = {}
        for i, (lbl, fkey) in enumerate(defs):
            tk.Label(form, text=lbl, fg=OVERLAY0, bg=BG,
                     font=("Segoe UI", 9)).grid(row=i, column=0, sticky="w",
                                                pady=5, padx=(0, 12))
            v = tk.StringVar()
            if fkey == "category":
                v.set("other")
                ttk.Combobox(form, textvariable=v, width=16,
                             values=list(CATEGORY_LABELS.keys()),
                             state="readonly").grid(row=i, column=1, sticky="ew", pady=5)
            else:
                ttk.Entry(form, textvariable=v).grid(row=i, column=1, sticky="ew", pady=5)
            fv[fkey] = v

        def _save():
            raw = fv["key"].get().strip().lower().replace(" ", "_")
            if not raw: return
            n = fv["name"].get().strip() or raw
            config["sites"][raw] = {
                "name": n, "display_name": n, "enabled": True,
                "privacy": False,
                "discord_app_id": fv["discord_app_id"].get().strip() or DEFAULT_APP_ID,
                "large_image":    fv["large_image"].get().strip(),
                "large_text":     n,
                "category":       fv["category"].get() or "other",
            }
            save_config()
            log(f"[Config] Added: {raw}")
            win.destroy()
            show_toast(self, f"Site '{raw}' added. Restart to see it.")

        ttk.Button(win, text="Add Site", style="Accent.TButton",
                   command=_save).pack(anchor="e", padx=18, pady=14)

    # ── Tab: Settings ───────────────────────────────────────────────────────────
    def _build_tab_settings(self, nb):
        frame = ttk.Frame(nb)
        nb.add(frame, text="Settings")

        sv_outer = tk.Frame(frame, bg=BG)
        sv_outer.pack(fill="both", expand=True)

        canvas2 = tk.Canvas(sv_outer, bg=BG, bd=0, highlightthickness=0)
        vsb2    = ttk.Scrollbar(sv_outer, orient="vertical", command=canvas2.yview)
        canvas2.configure(yscrollcommand=vsb2.set)
        vsb2.pack(side="right", fill="y")
        canvas2.pack(side="left", fill="both", expand=True)
        inner2 = tk.Frame(canvas2, bg=BG)
        wid2   = canvas2.create_window((0, 0), window=inner2, anchor="nw")
        canvas2.bind("<Configure>", lambda e: canvas2.itemconfig(wid2, width=e.width))
        inner2.bind("<Configure>", lambda e: canvas2.configure(
            scrollregion=canvas2.bbox("all")))
        canvas2.bind("<MouseWheel>",
            lambda e: canvas2.yview_scroll(-1*(e.delta//120), "units"))
        canvas2.bind("<Enter>",
            lambda e: canvas2.bind_all("<MouseWheel>",
                lambda ev: canvas2.yview_scroll(-1*(ev.delta//120), "units")))
        canvas2.bind("<Leave>",
            lambda e: canvas2.unbind_all("<MouseWheel>"))

        def _section(title):
            c = tk.Frame(inner2, bg=SURFACE0)
            c.pack(fill="x", padx=16, pady=(12, 4))
            tk.Label(c, text=title, font=("Segoe UI", 10, "bold"),
                     fg=ACCENT, bg=SURFACE0).pack(anchor="w", padx=14, pady=(10, 6))
            tk.Frame(c, height=1, bg=SURFACE1).pack(fill="x", padx=14)
            body = tk.Frame(c, bg=SURFACE0)
            body.pack(fill="x", padx=14, pady=8)
            return body

        g_app = _section("App Settings")

        row_launch = tk.Frame(g_app, bg=SURFACE0)
        row_launch.pack(anchor="w", pady=(0, 6))
        start_var = tk.BooleanVar(value=get_startup_state())
        def _tog_start(): set_startup(start_var.get())
        ttk.Checkbutton(row_launch, text="Startup with System",
                        variable=start_var, command=_tog_start,
                        style="Card.TCheckbutton").pack(side="left")

        row_min = tk.Frame(g_app, bg=SURFACE0)
        row_min.pack(anchor="w")
        min_var = tk.BooleanVar(value=config.get("start_minimised", False))
        def _tog_min():
            config["start_minimised"] = min_var.get()
            save_config()
        ttk.Checkbutton(row_min, text="Start Minimized",
                        variable=min_var, command=_tog_min,
                        style="Card.TCheckbutton").pack(side="left")
                        
        g4 = _section("Start status as (Enabled/Disabled)")
        rpc_en_var = tk.BooleanVar(value=config.get("rpc_enabled", True))
        def _tog_rpc_en():
            global rpc_enabled
            rpc_enabled = rpc_en_var.get()
            config["rpc_enabled"] = rpc_enabled
            if not rpc_enabled: clear_rpc()
            _refresh_rpc_label()
            save_config()
        ttk.Checkbutton(g4, text="Enable (If clicked, status will be enabled on every app restart)",
                        variable=rpc_en_var, command=_tog_rpc_en,
                        style="Card.TCheckbutton").pack(anchor="w")
                        
        g2 = _section("Discord Activity Type")
        g2.columnconfigure(1, weight=1)
        tk.Label(g2, text="Show as:", fg=OVERLAY0, bg=SURFACE0,
                 font=("Segoe UI", 9)).grid(row=0, column=0, sticky="w", padx=(0, 14), pady=4)
        act_var = tk.StringVar(value=config.get("activity_type", "Watching"))
        cb = ttk.Combobox(g2, textvariable=act_var,
                          values=list(_ACTIVITY_TYPES.keys()),
                          state="readonly", width=14)
        cb.grid(row=0, column=1, sticky="w")
        tk.Label(g2, text="Takes effect on the next activity update.",
                 fg=OVERLAY0, bg=SURFACE0, font=("Segoe UI", 9)).grid(
                     row=1, column=0, columnspan=2, sticky="w", pady=(2, 6))

        g = _section("HTTP Server")
        g.columnconfigure(1, weight=1)
        tk.Label(g, text="Port:", fg=OVERLAY0, bg=SURFACE0,
                 font=("Segoe UI", 9)).grid(row=0, column=0, sticky="w", padx=(0, 14), pady=4)
        port_var = tk.StringVar(value=str(config.get("server_port", 7591)))
        ttk.Entry(g, textvariable=port_var, width=10).grid(row=0, column=1, sticky="w")
        tk.Label(g, text="Changing the port requires a restart.",
                 fg=OVERLAY0, bg=SURFACE0, font=("Segoe UI", 9)).grid(
                     row=1, column=0, columnspan=2, sticky="w", pady=(2, 6))
        def _save_port():
            try:
                p = int(port_var.get())
                if not 1024 <= p <= 65535: raise ValueError
                config["server_port"] = p
                save_config()
                show_toast(self, "Port saved. Restart to apply.")
            except ValueError:
                show_toast(self, "Invalid port (1024–65535).")
        ttk.Button(g, text="Save Port", style="Accent.TButton",
                   command=_save_port).grid(row=2, column=1, sticky="e")
                   
        def _save_act():
            config["activity_type"] = act_var.get()
            save_config()
            show_toast(self, f"Activity type set to {act_var.get()}.")
        ttk.Button(g2, text="Apply", style="Accent.TButton",
                   command=_save_act).grid(row=2, column=1, sticky="e")

        g5 = _section("Testing Developer Settings (Do not touch if you don't know what it is.)")
        dev_var = tk.BooleanVar(value=config.get("dev_mode", False))
        def _tog_dev():
            config["dev_mode"] = dev_var.get()
            save_config()
        ttk.Checkbutton(g5, text="Show hidden testing settings",
                        variable=dev_var, command=_tog_dev,
                        style="Card.TCheckbutton").pack(anchor="w", pady=(0, 8))
        ttk.Button(g5, text="+ Add Custom Site",
                   command=self._add_custom_site).pack(anchor="w")

        ref = tk.Frame(inner2, bg=SURFACE0)
        ref.pack(fill="x", padx=16, pady=(12, 4))
        tk.Label(ref, text="Icon Key Reference",
                 font=("Segoe UI", 10, "bold"), fg=ACCENT, bg=SURFACE0).pack(
                     anchor="w", padx=14, pady=(10, 6))
        tk.Frame(ref, height=1, bg=SURFACE1).pack(fill="x", padx=14)
        tk.Label(ref,
                 text="Upload in Discord Developers → Rich Presence → Art Assets.\n"
                      "Also upload: playing_icon, paused_icon",
                 fg=SUBTEXT0, bg=SURFACE0, font=("Segoe UI", 9)).pack(
                     anchor="w", padx=14, pady=(6, 4))
        tw = tk.Frame(ref, bg=SURFACE0)
        tw.pack(fill="x", padx=14, pady=(0, 10))
        cols = ("Site", "Icon Key")
        tree = ttk.Treeview(tw, columns=cols, show="headings", height=12)
        for c, w in zip(cols, (200, 280)):
            tree.heading(c, text=c); tree.column(c, width=w)
        for v in config["sites"].values():
            tree.insert("", "end", values=(v["name"], v.get("large_image", "")))
        tsb = ttk.Scrollbar(tw, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=tsb.set)
        tsb.pack(side="right", fill="y")
        tree.pack(side="left", fill="x", expand=True)

    # ── Tab: About ──────────────────────────────────────────────────────────────
    def _build_tab_about(self, nb):
        frame = ttk.Frame(nb)
        nb.add(frame, text="About")

        card = tk.Frame(frame, bg=SURFACE0)
        card.pack(fill="x", padx=16, pady=(16, 8))

        tk.Label(card, text=f"Version {APP_VERSION}",
                 font=("Segoe UI", 18, "bold"), fg=ACCENT, bg=SURFACE0).pack(
                     anchor="w", padx=20, pady=(20, 2))
        tk.Frame(card, height=1, bg=SURFACE1).pack(fill="x", padx=20, pady=(0, 12))
        
        contact_text = "Contact on Discord"
        contact_url  = "https://discord.com/users/97282552947027968"

        contact_lbl = tk.Label(card, text=contact_text,
                               font=("Segoe UI", 10, "underline"),
                               fg=ACCENT, bg=SURFACE0, cursor="hand2")
        contact_lbl.pack(anchor="w", padx=20, pady=(0, 8))
        contact_lbl.bind("<Button-1>", lambda e, url=contact_url: webbrowser.open(url))
        
        repo_url = "https://github.com/Arikizu/DiscordRPC"
        link_lbl = tk.Label(card, text=repo_url,
                            font=("Segoe UI", 10, "underline"),
                            fg=ACCENT, bg=SURFACE0, cursor="hand2")
        link_lbl.pack(anchor="w", padx=20, pady=(0, 8))
        link_lbl.bind("<Button-1>", lambda e: webbrowser.open(repo_url))

        tk.Frame(card, height=1, bg=SURFACE1).pack(fill="x", padx=20, pady=(0, 8))
        for line in [
            "Requires:  Python 3.10+",
            "Dependencies:   pypresence   pystray   pillow   requests",
            "",
            "Supported Websites:",
            "YouTube   Rumble   Twitch   Netflix",
            "",
            "Supported Polish Websites:",
            "CDA.pl   Shinden.pl   OgladajAnime.pl",
        ]:
            tk.Label(card, text=line, fg=SUBTEXT0, bg=SURFACE0,
                     font=("Segoe UI", 9)).pack(anchor="w", padx=20, pady=1)
        tk.Frame(card, height=16, bg=SURFACE0).pack()

    # ── Tab: Log ────────────────────────────────────────────────────────────────
    def _build_tab_log(self, nb):
        global _log_widget
        frame = ttk.Frame(nb)
        nb.add(frame, text="Logs")

        bar = tk.Frame(frame, bg=BG2)
        bar.pack(fill="x")
        tk.Label(bar, text="  Event Log", fg=OVERLAY0, bg=BG2,
                 font=("Segoe UI", 9)).pack(side="left", padx=4, pady=6)
        ttk.Button(bar, text="Clear", command=self._clear_log).pack(
            side="right", padx=8, pady=4)
        tk.Frame(frame, height=1, bg=SURFACE1).pack(fill="x")

        txt = tk.Text(frame, state="disabled", bg=BG3, fg=TEXT,
                      font=("Consolas", 9), relief="flat", bd=0, wrap="word",
                      selectbackground=SURFACE1, insertbackground=ACCENT,
                      padx=8, pady=6)
        sb = ttk.Scrollbar(frame, command=txt.yview)
        txt.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        txt.pack(fill="both", expand=True)
        _log_widget = txt

    def _clear_log(self):
        log_lines.clear()
        if _log_widget:
            _log_widget.configure(state="normal")
            _log_widget.delete("1.0", "end")
            _log_widget.configure(state="disabled")

    # ── Helpers ─────────────────────────────────────────────────────────────────
    @staticmethod
    def _mk_danger_btn(parent, text, cmd):
        return tk.Button(parent, text=text,
                         bg="#3b1a25", fg=RED,
                         activebackground=RED, activeforeground=BG2,
                         relief="flat", bd=0, padx=10, pady=4,
                         font=("Segoe UI", 9), cursor="hand2",
                         command=cmd)

    def _rpc_poll(self):
        _refresh_rpc_label()
        self.after(1_000, self._rpc_poll)

    def _on_close(self):
        self.withdraw()
        if not TRAY_OK:
            global app_running
            app_running = False
            clear_rpc()
            self.destroy()

# ──────────────────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────────────────
def main():
    global config
    config = load_config()
    save_config()

    threading.Thread(target=run_server, daemon=True).start()
    if TRAY_OK:
        threading.Thread(target=_run_tray, daemon=True).start()

    app = App()
    log(f"[App] Discord Rich Presence {APP_VERSION} is Ready.")
    if not PYPRESENCE_OK:
        log("[App] MISSING pypresence — pip install pypresence")
    if not TRAY_OK:
        log("[App] MISSING pystray/Pillow — pip install pystray pillow")
    app.mainloop()

if __name__ == "__main__":
    try:
        main()
    except Exception as _crash:
        import traceback as _tb
        _crash_path = os.path.join(BASE_DIR, "crash.log")
        with open(_crash_path, "w", encoding="utf-8") as _f:
            _f.write(_tb.format_exc())
        try:
            import tkinter.messagebox as _mb
            _mb.showerror("Crash", f"App crashed:\n{_crash}\n\nSee crash.log for details.")
        except Exception:
            pass
        raise