"""
Friday AI Assistant — app.py  (Jarvis HUD — Standalone Display)
================================================================
Pure visual HUD. Reads friday_state.json for Friday's live state.
NO AI logic here — all intelligence runs in friday.py.

pip install:
  pip install pygame psutil requests

Launch (via friday.py subprocess — do NOT run directly in most cases):
  python app.py
"""

# ── Standard library ──────────────────────────────────────────────────────────
import sys
import os
import math
import time
import json
import threading
import datetime
import random

# ── Third-party ───────────────────────────────────────────────────────────────
import pygame
import pygame.gfxdraw

# ── Optional: psutil ──────────────────────────────────────────────────────────
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

# ── Optional: requests ────────────────────────────────────────────────────────
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

# ── State file (IPC from friday.py) ──────────────────────────────────────────
ROOT       = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(ROOT, "friday_state.json")


# ══════════════════════════════════════════════════════════════════════════════
#  TIMETABLE  (mirrored from friday.py for local schedule panel rendering)
# ══════════════════════════════════════════════════════════════════════════════
TIMETABLE = {
    "Monday": [
        ("08:00", "09:00", "MRMM",                     ""),
        ("09:00", "10:00", "IPPR",                     ""),
        ("10:00", "12:00", "Service Ops Lab",          "B 405"),
        ("13:00", "14:00", "ITPM",                     "J 102"),
        ("14:00", "16:00", "IPPR Lab",                 "B 405"),
    ],
    "Tuesday": [
        ("08:00", "09:00", "Industrial Psychology",    ""),
        ("09:00", "10:00", "ITPM",                     ""),
        ("10:00", "11:00", "Service Ops",              ""),
        ("11:00", "12:00", "IPPR",                     ""),
        ("13:00", "14:00", "MRMM",                     "J 102"),
        ("14:00", "16:00", "Industrial Psychology Lab","B 408"),
    ],
    "Wednesday": [
        ("08:00", "10:00", "ITPM Lab",                 "B 406"),
        ("10:00", "11:00", "IPPR",                     "J 102"),
        ("11:00", "12:00", "ITPM",                     ""),
        ("13:00", "14:00", "Industrial Psychology",    "J 102"),
        ("14:00", "15:00", "Service Ops",              ""),
        ("15:00", "16:00", "Service Ops",              ""),
    ],
    "Thursday": [
        ("08:00", "09:00", "Industrial Psychology",    ""),
        ("10:00", "12:00", "Project Evaluation",       "B 716"),
    ],
    "Friday": [],
}

WEATHER_CODES = {
    0: "Clear Sky",
    1: "Mainly Clear", 2: "Partly Cloudy", 3: "Overcast",
    45: "Foggy", 48: "Icy Fog",
    51: "Light Drizzle", 53: "Drizzle", 55: "Heavy Drizzle",
    61: "Light Rain",   63: "Rain",      65: "Heavy Rain",
    71: "Light Snow",   73: "Snow",      75: "Heavy Snow",
    77: "Snow Grains",
    80: "Light Showers", 81: "Showers",  82: "Heavy Showers",
    95: "Thunderstorm",  96: "Thunderstorm+Hail", 99: "Thunderstorm+Hail",
}

def _wcode_desc(code: int) -> str:
    if code in WEATHER_CODES:
        return WEATHER_CODES[code]
    for k in sorted(WEATHER_CODES.keys(), reverse=True):
        if code >= k:
            return WEATHER_CODES[k]
    return "Unknown"


# ══════════════════════════════════════════════════════════════════════════════
#  PALETTE & CONSTANTS
# ══════════════════════════════════════════════════════════════════════════════
BG         = (2,   8,  16)
CYAN       = (0, 212, 255)
CYAN2      = (0, 160, 200)
CYAN_DIM   = (0,  80, 110)
BLUE       = (0, 100, 220)
GREEN      = (0, 255, 136)
GREEN_DIM  = (0, 140,  80)
WHITE      = (210, 225, 240)
WHITE70    = (150, 165, 180)
YELLOW     = (255, 200,  60)
PURPLE     = (160,  80, 255)
RED_DIM    = (200,  60,  60)
PANEL_DARK = (3,  12,  22)

FPS      = 60
BOOT_DUR = 3.0


# ══════════════════════════════════════════════════════════════════════════════
#  SHARED HUD STATE  (thread-safe)
# ══════════════════════════════════════════════════════════════════════════════
_lock  = threading.Lock()
_state = {
    "mode":          "boot",
    "response_text": "",
    "response_fade": 0.0,
    "response_age":  0.0,
    "weather":  {"temp": "--", "desc": "Loading...", "city": "..."},
    "sys":      {"cpu": 0.0,  "ram": 0.0, "uptime": "00:00:00"},
    "running":  True,
    # Status indicators
    "mic_ok":   True,
    "ai_ok":    True,
    "tts_ok":   True,
    # internal
    "_last_text":  "",
    "_last_mode":  "",
}

def _set_mode(m: str):
    with _lock:
        _state["mode"] = m

def _set_response(text: str):
    with _lock:
        if text != _state["_last_text"]:
            _state["response_text"] = text
            _state["response_fade"] = 0.0
            _state["response_age"]  = 0.0
            _state["_last_text"]    = text


# ══════════════════════════════════════════════════════════════════════════════
#  BACKGROUND THREADS
# ══════════════════════════════════════════════════════════════════════════════

def _state_reader_loop():
    """
    Read friday_state.json every 0.5s and update local HUD state.
    This is the IPC bridge from friday.py → app.py.
    """
    while True:
        with _lock:
            if not _state["running"]:
                return
        try:
            if os.path.exists(STATE_FILE):
                with open(STATE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                mode = data.get("mode", "idle")
                text = data.get("text", "")

                with _lock:
                    _state["mode"] = mode
                    if mode == "offline":
                        _state["running"] = False

                if text:
                    _set_response(text)
        except (json.JSONDecodeError, OSError):
            pass
        except Exception:
            pass
        time.sleep(0.4)


def _weather_loop():
    while True:
        with _lock:
            if not _state["running"]:
                return
        try:
            if HAS_REQUESTS:
                geo  = requests.get("http://ip-api.com/json/", timeout=6).json()
                lat  = geo["lat"]
                lon  = geo["lon"]
                city = geo.get("city", "Unknown")
                wr   = requests.get(
                    f"https://api.open-meteo.com/v1/forecast"
                    f"?latitude={lat}&longitude={lon}&current_weather=true",
                    timeout=6,
                ).json()
                cw = wr["current_weather"]
                with _lock:
                    _state["weather"] = {
                        "temp": f"{cw['temperature']:.0f}\u00b0C",
                        "desc": _wcode_desc(int(cw["weathercode"])),
                        "city": city,
                    }
        except Exception:
            pass
        # Poll every 10 minutes
        deadline = time.time() + 600
        while time.time() < deadline:
            with _lock:
                if not _state["running"]:
                    return
            time.sleep(2)


def _sysstat_loop():
    boot_t = psutil.boot_time() if HAS_PSUTIL else time.time()
    while True:
        with _lock:
            if not _state["running"]:
                return
        try:
            if HAS_PSUTIL:
                cpu    = psutil.cpu_percent(interval=1)
                ram    = psutil.virtual_memory().percent
                up     = int(time.time() - boot_t)
                h, r   = divmod(up, 3600)
                m, s   = divmod(r, 60)
                uptime = f"{h:02d}:{m:02d}:{s:02d}"
            else:
                cpu, ram, uptime = 0.0, 0.0, "N/A"
            with _lock:
                _state["sys"] = {"cpu": cpu, "ram": ram, "uptime": uptime}
        except Exception:
            pass
        time.sleep(2)


# ══════════════════════════════════════════════════════════════════════════════
#  DRAWING UTILITIES
# ══════════════════════════════════════════════════════════════════════════════
def _font(name: str, size: int) -> pygame.font.Font:
    try:
        p = pygame.font.match_font(name)
        if p:
            return pygame.font.Font(p, size)
    except Exception:
        pass
    return pygame.font.SysFont("monospace", size, bold=True)


def _asurf(w: int, h: int) -> pygame.Surface:
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    s.fill((0, 0, 0, 0))
    return s


def _ease_out(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 1.0 - (1.0 - t) ** 3


def _draw_hex_grid(surf: pygame.Surface, phase: float, alpha: int = 13):
    s    = _asurf(surf.get_width(), surf.get_height())
    size = 40
    col  = (0, 180, 220, alpha)
    h_   = size * math.sqrt(3)
    cols = int(surf.get_width()  / (size * 1.5)) + 3
    rows = int(surf.get_height() / h_) + 3
    ox   = (phase * 10) % (size * 3)
    oy   = (phase *  5) % h_
    for row in range(-1, rows):
        for ci in range(-1, cols):
            cx_ = ci * size * 1.5 + (size * 0.75 if row % 2 else 0) - ox
            cy_ = row * h_ - oy
            pts = []
            for i in range(6):
                ang = math.radians(60 * i - 30)
                pts.append((cx_ + size * math.cos(ang),
                             cy_ + size * math.sin(ang)))
            pygame.draw.polygon(s, col, pts, 1)
    surf.blit(s, (0, 0))


def _draw_scan_lines(surf: pygame.Surface, scan_y: float, alpha: int = 22):
    h = surf.get_height()
    w = surf.get_width()
    s = _asurf(w, h)
    for y in range(0, h, 4):
        pygame.draw.line(s, (0, 170, 210, int(alpha * 0.22)), (0, y), (w, y), 1)
    beam = int(scan_y * h)
    for dy in range(-10, 11):
        y = beam + dy
        if 0 <= y < h:
            frac = 1.0 - abs(dy) / 11
            a    = int(alpha * 3.5 * frac * frac)
            pygame.draw.line(s, (0, 212, 255, min(255, a)), (0, y), (w, y), 1)
    surf.blit(s, (0, 0))


def _draw_corner_marks(surf, rect, col, L=14, W=2):
    x, y, rw, rh = rect.x, rect.y, rect.w, rect.h
    segs = [
        ((x,    y   ), (x+L,  y   )), ((x,    y   ), (x,    y+L  )),
        ((x+rw, y   ), (x+rw-L, y )), ((x+rw, y   ), (x+rw, y+L  )),
        ((x,    y+rh), (x+L,  y+rh)), ((x,    y+rh), (x,    y+rh-L)),
        ((x+rw, y+rh), (x+rw-L, y+rh)), ((x+rw, y+rh), (x+rw, y+rh-L)),
    ]
    for (x0, y0), (x1, y1) in segs:
        pygame.draw.line(surf, col, (x0, y0), (x1, y1), W)


def _draw_panel_bg(surf, rect, border_col=None, alpha=175, slide=1.0):
    if slide <= 0:
        return
    if border_col is None:
        border_col = CYAN

    pw = max(1, int(rect.w * min(slide, 1.0)))
    ph = max(1, int(rect.h * min(slide, 1.0)))

    s = _asurf(pw, ph)
    s.fill(PANEL_DARK + (min(255, alpha),))
    pygame.draw.rect(s, border_col + (min(255, int(90 * slide)),),
                     pygame.Rect(0, 0, pw, ph), 1)
    pygame.draw.line(s, border_col + (min(255, int(35 * slide)),),
                     (1, 1), (pw - 2, 1), 1)
    surf.blit(s, (rect.x, rect.y))

    if slide > 0.7:
        ca = int(230 * min(1.0, (slide - 0.7) / 0.3))
        _draw_corner_marks(surf, rect, border_col + (ca,))


def _wrap_text(text: str, font, max_w: int) -> list:
    words = text.split()
    lines, cur = [], ""
    for w in words:
        test = (cur + " " + w).strip()
        if font.size(test)[0] <= max_w:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


# ══════════════════════════════════════════════════════════════════════════════
#  CORE DRAW
# ══════════════════════════════════════════════════════════════════════════════
def _draw_core(surf, cx, cy, mode, phase, ring_phase, shimmer, bars, scale=1.0):
    W, H = surf.get_width(), surf.get_height()
    s    = _asurf(W, H)

    breath = (math.sin(phase) + 1.0) / 2.0
    base_r = min(W, H) * 0.14 * scale

    if mode == "idle":
        cc, gc = (0, 185, 225),   (0,  90, 140)
    elif mode == "listening":
        cc, gc = (0, 255, 160),   (0, 130, 100)
    elif mode == "thinking":
        cc, gc = (170,  80, 255), (80,  35, 170)
    elif mode == "speaking":
        cc, gc = (0, 212, 255),   (0, 110, 210)
    elif mode == "bye":
        cc, gc = (180,  50,  50), (80,  20,  20)
    else:
        cc, gc = (0, 100, 130),   (0,  40,  70)

    # Outer glow
    glow_r = int(base_r * 2.6 + breath * base_r * 0.5)
    for gi in range(7, 0, -1):
        gr = glow_r * gi // 7
        ga = int(36 * (gi / 7) * (0.45 + 0.55 * breath))
        pygame.draw.circle(s, gc + (ga,), (int(cx), int(cy)), gr)

    # Rotating dashed arc rings
    ring_specs = [
        (1.58, 2,  1.00, True,  12),
        (1.35, 1, -0.65, False,  0),
        (1.18, 3,  1.40, False,  0),
        (1.75, 1,  0.45, True,   8),
    ]
    for r_mult, lw, spd, dashed, segs in ring_specs:
        rr  = int(base_r * r_mult)
        ang = shimmer * spd
        if dashed and segs > 0:
            for si in range(segs):
                a0 = math.radians(ang + si * (360 / segs))
                a1 = math.radians(ang + si * (360 / segs) + (360 / segs) * 0.55)
                pts_ring = []
                for t in range(15):
                    ta = a0 + (a1 - a0) * t / 14
                    pts_ring.append((cx + rr * math.cos(ta),
                                     cy + rr * math.sin(ta)))
                al = int(150 + 80 * breath)
                if len(pts_ring) > 1:
                    pygame.draw.lines(s, cc + (al,), False,
                                      [(int(x), int(y)) for x, y in pts_ring], lw)
        else:
            al = int(55 + 30 * breath)
            pygame.draw.circle(s, cc + (al,), (int(cx), int(cy)), rr, lw)

    # Mode-specific effects
    if mode == "listening":
        for i in range(4):
            off = (ring_phase + i * 1.8) % (2 * math.pi)
            exp = (math.sin(off) + 1.0) / 2.0
            rr  = int(base_r * (1.62 + exp * 1.4))
            al  = int(210 * (1.0 - exp))
            if al > 4:
                pygame.draw.circle(s, cc + (al,), (int(cx), int(cy)), rr, 2)

    elif mode == "speaking":
        n = len(bars)
        for i, amp in enumerate(bars):
            ang = math.radians(360 * i / n - 90)
            r0  = base_r * 1.68
            r1  = r0 + amp * base_r * 1.6
            x0  = cx + r0 * math.cos(ang)
            y0  = cy + r0 * math.sin(ang)
            x1  = cx + r1 * math.cos(ang)
            y1  = cy + r1 * math.sin(ang)
            al  = int(160 * amp + 70)
            col = (int(cc[0] * amp), int(cc[1] * amp + 180 * (1 - amp)), cc[2])
            lw  = max(1, int(2 * amp + 1))
            pygame.draw.line(s, col + (min(255, al),),
                             (int(x0), int(y0)), (int(x1), int(y1)), lw)

    elif mode == "thinking":
        ndots = 10
        for i in range(ndots):
            ang = math.radians(shimmer * 1.6 + i * (360 / ndots))
            dr  = base_r * 1.78
            dx  = cx + dr * math.cos(ang)
            dy  = cy + dr * math.sin(ang)
            da  = int(70 + 110 * (i / ndots))
            r   = max(2, int(4 * (i / ndots)))
            pygame.draw.circle(s, cc + (da,), (int(dx), int(dy)), r)
        for i in range(3):
            ang = math.radians(shimmer * -0.9 + i * 120)
            dr  = base_r * 0.55
            dx  = cx + dr * math.cos(ang)
            dy  = cy + dr * math.sin(ang)
            pygame.draw.circle(s, cc + (180,), (int(dx), int(dy)), 3)

    # Inner orb
    orb_r = int(base_r * (0.86 + breath * 0.12))
    for gi in range(8, 0, -1):
        gr = orb_r * gi // 5
        ga = int(50 * (gi / 8))
        pygame.draw.circle(s, cc + (ga,), (int(cx), int(cy)), gr)
    pygame.draw.circle(s, cc + (230,), (int(cx), int(cy)), orb_r)
    hx = int(cx - orb_r * 0.30)
    hy = int(cy - orb_r * 0.30)
    pygame.draw.circle(s, (255, 255, 255, 170), (hx, hy), max(2, orb_r // 5))
    pygame.draw.circle(s, (255, 255, 255, 60),
                        (int(cx + orb_r * 0.15), int(cy + orb_r * 0.25)),
                        max(1, orb_r // 8))

    surf.blit(s, (0, 0))


# ══════════════════════════════════════════════════════════════════════════════
#  BOOT SEQUENCE
# ══════════════════════════════════════════════════════════════════════════════
def _draw_boot(surf, cx, cy, progress, fonts):
    s = _asurf(surf.get_width(), surf.get_height())

    for i in range(8):
        t = max(0.0, min(1.0, progress * 1.6 - i * 0.10))
        if t <= 0:
            continue
        t_e = _ease_out(t)
        r   = int(t_e * (80 + i * 65))
        al  = int(255 * (1.0 - t * 0.75))
        lw  = max(1, int(3 - i * 0.3))
        col = (0, max(180 - i * 18, 60), 255, max(0, al))
        pygame.draw.circle(s, col, (int(cx), int(cy)), r, lw)

    cd = int(8 * min(progress * 4, 1.0))
    if cd > 0:
        pygame.draw.circle(s, CYAN + (220,), (int(cx), int(cy)), cd)

    if progress > 0.55:
        ta  = int(255 * min(1.0, (progress - 0.55) * 5))
        txt = fonts["sm"].render("FRIDAY  —  SYSTEMS ONLINE", True, CYAN)
        txt.set_alpha(ta)
        s.blit(txt, (int(cx - txt.get_width() / 2),
                     int(cy + min(surf.get_width(), surf.get_height()) * 0.22)))

    if progress > 0.3:
        pa  = int(255 * min(1.0, (progress - 0.3) * 3))
        bw  = int(surf.get_width() * 0.35 * min(1.0, (progress - 0.3) / 0.7))
        bh  = 3
        bx  = int(cx - surf.get_width() * 0.175)
        by_ = int(cy + min(surf.get_width(), surf.get_height()) * 0.27)
        pygame.draw.rect(s, CYAN_DIM + (pa,),
                         (bx - 2, by_, int(surf.get_width() * 0.35) + 4, bh))
        if bw > 0:
            pygame.draw.rect(s, CYAN + (pa,), (bx, by_, bw, bh))

    surf.blit(s, (0, 0))


# ══════════════════════════════════════════════════════════════════════════════
#  HUD PANELS
# ══════════════════════════════════════════════════════════════════════════════
def _draw_panel_system(surf, rect, sys_info, fonts, slide=1.0):
    _draw_panel_bg(surf, rect, CYAN, slide=slide)
    if slide < 0.1:
        return
    a   = int(255 * min(1.0, (slide - 0.1) / 0.5))
    pad = 10
    x, y = rect.x + pad, rect.y + pad
    w    = rect.w - pad * 2

    title = fonts["sm"].render("  SYSTEM STATUS", True, CYAN)
    title.set_alpha(a)
    surf.blit(title, (x, y)); y += title.get_height() + 6

    div = _asurf(w, 1); div.fill(CYAN_DIM + (a,)); surf.blit(div, (x, y)); y += 8

    def _bar(label, val, col):
        nonlocal y
        lbl = fonts["xs"].render(label, True, WHITE70)
        lbl.set_alpha(a); surf.blit(lbl, (x, y))
        bx, by = x + 52, y + 3
        bw, bh = w - 55, 8
        ts = _asurf(bw, bh); ts.fill((0, 40, 60, a)); surf.blit(ts, (bx, by))
        fw = max(0, int(bw * min(val, 100) / 100))
        if fw > 0:
            fs = _asurf(fw, bh); fs.fill(col + (min(255, a),)); surf.blit(fs, (bx, by))
        pygame.draw.rect(surf, CYAN_DIM + (min(100, a),),
                         pygame.Rect(bx, by, bw, bh), 1)
        pct = fonts["xs"].render(f"{val:.0f}%", True, WHITE70)
        pct.set_alpha(a); surf.blit(pct, (bx + bw + 4, y))
        y += bh + 10

    _bar("CPU", sys_info["cpu"], (0, 160, 255))
    _bar("RAM", sys_info["ram"], GREEN)

    up = fonts["xs"].render(f"UPTIME  {sys_info['uptime']}", True, WHITE70)
    up.set_alpha(a); surf.blit(up, (x, y))


def _draw_panel_clock(surf, rect, fonts, slide=1.0):
    _draw_panel_bg(surf, rect, CYAN, slide=slide)
    if slide < 0.1:
        return
    a   = int(255 * min(1.0, (slide - 0.1) / 0.5))
    pad = 10
    cx_ = rect.x + rect.w // 2

    lbl = fonts["xs"].render("  LIVE CLOCK  (IST)", True, CYAN)
    lbl.set_alpha(a); surf.blit(lbl, (rect.x + pad, rect.y + pad))

    now = datetime.datetime.now()
    ts  = fonts["lg"].render(now.strftime("%H:%M:%S"), True, CYAN)
    ts.set_alpha(a)
    surf.blit(ts, (cx_ - ts.get_width() // 2, rect.y + pad + 20))

    ds = fonts["sm"].render(now.strftime("%A, %d %b %Y"), True, WHITE70)
    ds.set_alpha(a)
    surf.blit(ds, (cx_ - ds.get_width() // 2,
                   rect.y + pad + 20 + ts.get_height() + 6))


def _draw_panel_weather(surf, rect, weather, fonts, slide=1.0):
    _draw_panel_bg(surf, rect, BLUE, slide=slide)
    if slide < 0.1:
        return
    a   = int(255 * min(1.0, (slide - 0.1) / 0.5))
    pad = 10
    x, y = rect.x + pad, rect.y + pad

    title = fonts["sm"].render("  WEATHER", True, (0, 140, 255))
    title.set_alpha(a); surf.blit(title, (x, y)); y += title.get_height() + 6

    div = _asurf(rect.w - pad * 2, 1)
    div.fill(BLUE + (min(a, 100),)); surf.blit(div, (x, y)); y += 8

    ci = fonts["sm"].render(weather["city"], True, WHITE)
    ci.set_alpha(a); surf.blit(ci, (x, y)); y += ci.get_height() + 4

    temp = fonts["hud"].render(weather["temp"], True, CYAN)
    temp.set_alpha(a); surf.blit(temp, (x, y)); y += temp.get_height() + 2

    desc = fonts["xs"].render(weather["desc"], True, WHITE70)
    desc.set_alpha(a); surf.blit(desc, (x, y))


def _draw_panel_schedule(surf, rect, fonts, slide=1.0):
    _draw_panel_bg(surf, rect, GREEN_DIM, slide=slide)
    if slide < 0.1:
        return
    a   = int(255 * min(1.0, (slide - 0.1) / 0.5))
    pad = 10
    x, y = rect.x + pad, rect.y + pad
    w    = rect.w - pad * 2

    title = fonts["sm"].render("  CLASS SCHEDULE", True, GREEN)
    title.set_alpha(a); surf.blit(title, (x, y)); y += title.get_height() + 6

    div = _asurf(w, 1); div.fill(GREEN_DIM + (min(a, 120),))
    surf.blit(div, (x, y)); y += 8

    now    = datetime.datetime.now()
    day    = now.strftime("%A")
    t_now  = now.strftime("%H:%M")
    classes = TIMETABLE.get(day, [])

    day_lbl = fonts["xs"].render(day.upper(), True, GREEN_DIM)
    day_lbl.set_alpha(a); surf.blit(day_lbl, (x, y)); y += day_lbl.get_height() + 4

    if not classes:
        nl = fonts["xs"].render("No classes today.", True, WHITE70)
        nl.set_alpha(a); surf.blit(nl, (x, y))
        return

    char_w    = max(1, fonts["xs"].size("W")[0])
    max_chars = max(1, w // char_w - 2)

    for i, (start, end, subject, room) in enumerate(classes[:6]):
        is_now  = (start <= t_now < end)
        is_next = (not is_now and start > t_now and
                   i == next((j for j, (s, e, _, _)
                               in enumerate(classes) if s > t_now), None))
        col  = CYAN   if is_now  else (GREEN  if is_next else WHITE70)
        mark = "> "   if is_now  else ("> "   if is_next else "  ")
        line = f"{mark}{start}-{end} {subject}"
        if room:
            line += f" [{room}]"
        if len(line) > max_chars:
            line = line[:max_chars - 1] + "..."
        ls = fonts["xs"].render(line, True, col)
        ls.set_alpha(a); surf.blit(ls, (x, y))
        y += ls.get_height() + 3
        if y > rect.y + rect.h - 8:
            break


def _draw_response_panel(surf, rect, text, fade, mode, fonts, slide=1.0):
    _draw_panel_bg(surf, rect, CYAN, alpha=150, slide=slide)
    if slide < 0.1:
        return
    a = int(255 * min(1.0, (slide - 0.1) / 0.5))

    if not text:
        lbl = fonts["xs"].render("  FRIDAY OUTPUT", True, CYAN_DIM)
        lbl.set_alpha(a)
        surf.blit(lbl, (rect.x + (rect.w - lbl.get_width()) // 2, rect.y + 8))
        return

    max_w  = rect.w - 24
    lines  = _wrap_text(text, fonts["sm"], max_w)
    text_a = int(min(255, fade * 300) * a / 255)
    lh     = fonts["sm"].get_height() + 3
    tot_h  = lh * min(len(lines), 4)
    sy     = rect.y + (rect.h - tot_h) // 2

    for i, line in enumerate(lines[:4]):
        ls = fonts["sm"].render(line, True, WHITE)
        ls.set_alpha(text_a)
        surf.blit(ls, (rect.x + (rect.w - ls.get_width()) // 2, sy + i * lh))

    mode_labels = {
        "speaking":  ("SPEAKING",   CYAN),
        "thinking":  ("PROCESSING", PURPLE),
        "listening": ("LISTENING",  GREEN),
    }
    if mode in mode_labels:
        tag_txt, tag_col = mode_labels[mode]
        tag = fonts["xs"].render(f"  {tag_txt}", True, tag_col)
        tag.set_alpha(a)
        surf.blit(tag, (rect.x + rect.w - tag.get_width() - 8,
                        rect.y + rect.h - tag.get_height() - 6))


def _draw_status_bar(surf, rect, mode, mic_ok, ai_ok, tts_ok, fonts):
    """Bottom status bar — mic / AI / TTS indicators."""
    _draw_panel_bg(surf, rect, CYAN_DIM, alpha=120, slide=1.0)
    pad = 8
    x   = rect.x + pad
    y   = rect.y + (rect.h - fonts["xs"].get_height()) // 2

    def _dot(label, ok):
        nonlocal x
        col = GREEN if ok else RED_DIM
        ds  = _asurf(8, 8)
        pygame.draw.circle(ds, col + (210,), (4, 4), 3)
        surf.blit(ds, (x, y + 2))
        x += 12
        lbl = fonts["xs"].render(label, True, WHITE70)
        surf.blit(lbl, (x, y)); x += lbl.get_width() + 16

    _dot("MIC", mic_ok)
    _dot("AI",  ai_ok)
    _dot("TTS", tts_ok)

    # Right side: current mode
    mode_map = {
        "idle":      ("STANDBY",    CYAN_DIM),
        "listening": ("LISTENING",  GREEN),
        "thinking":  ("PROCESSING", PURPLE),
        "speaking":  ("SPEAKING",   CYAN),
        "bye":       ("OFFLINE",    RED_DIM),
        "boot":      ("BOOTING",    CYAN_DIM),
    }
    m_txt, m_col = mode_map.get(mode, ("", CYAN_DIM))
    if m_txt:
        ms = fonts["xs"].render(m_txt, True, m_col)
        surf.blit(ms, (rect.x + rect.w - ms.get_width() - pad, y))


def _draw_friday_label(surf, cx, cy, fonts, phase, min_dim, scale=1.0):
    txt = fonts["title"].render("F  R  I  D  A  Y", True, CYAN)
    a   = int(175 + 65 * (math.sin(phase) + 1) / 2)
    txt.set_alpha(int(a * scale))
    tx  = int(cx - txt.get_width() / 2)
    ty  = int(cy - min_dim * 0.22)
    surf.blit(txt, (tx, ty))
    uw  = txt.get_width()
    uy  = ty + txt.get_height() + 2
    us  = _asurf(uw, 2); us.fill(CYAN_DIM + (int(120 * scale),))
    surf.blit(us, (tx, uy))


def _draw_state_label(surf, cx, cy, mode, fonts, min_dim, scale=1.0):
    MAP = {
        "idle":      ("STANDBY",    CYAN_DIM),
        "listening": ("LISTENING",  GREEN),
        "thinking":  ("PROCESSING", PURPLE),
        "speaking":  ("SPEAKING",   CYAN),
        "bye":       ("OFFLINE",    RED_DIM),
        "boot":      ("BOOTING",    CYAN_DIM),
    }
    txt, col = MAP.get(mode, ("", CYAN_DIM))
    if not txt:
        return
    s_  = fonts["sm"].render(txt, True, col)
    s_.set_alpha(int(220 * scale))
    sx  = int(cx - s_.get_width() / 2)
    sy  = int(cy + min_dim * 0.165)
    surf.blit(s_, (sx, sy))

    bx  = cx - 18
    by  = sy + s_.get_height() + 5
    for di in range(3):
        p  = time.time() * 3.2 + di * 1.1
        da = int(100 + 120 * (math.sin(p) + 1) / 2)
        ds = _asurf(8, 8)
        pygame.draw.circle(ds, col + (int(da * scale),), (4, 4), 3)
        surf.blit(ds, (int(bx + di * 16), int(by)))


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN HUD LOOP
# ══════════════════════════════════════════════════════════════════════════════
def run_hud():
    pygame.init()
    pygame.display.set_caption("Friday")

    info  = pygame.display.Info()
    W, H  = info.current_w, info.current_h
    WIN_W = min(W, 1600)
    WIN_H = min(H, 900)

    screen = pygame.display.set_mode((WIN_W, WIN_H), pygame.NOFRAME)

    # Always-on-top + centered (Windows)
    try:
        import ctypes
        hwnd = pygame.display.get_wm_info()["window"]
        px   = (W - WIN_W) // 2
        py   = (H - WIN_H) // 2
        F    = 0x0001 | 0x0002   # SWP_NOSIZE | SWP_NOMOVE-compat
        ctypes.windll.user32.SetWindowPos(hwnd, -1, px, py, 0, 0, F)
        ctypes.windll.user32.SetWindowPos(hwnd, -1, 0,  0,  0, 0, F)
    except Exception:
        pass

    # ── Fonts ─────────────────────────────────────────────────────────────────
    fonts = {
        "title": _font("orbitron", 28),
        "hud":   _font("orbitron", 32),
        "lg":    _font("orbitron", 26),
        "sm":    _font("rajdhani", 15),
        "xs":    _font("rajdhani", 13),
    }

    clock_pg = pygame.time.Clock()

    # ── Animation vars ────────────────────────────────────────────────────────
    phase      = 0.0
    ring_phase = 0.0
    shimmer    = 0.0
    scan_y     = 0.0
    hex_phase  = 0.0
    boot_start = time.time()
    boot_done  = False
    bye_prog   = 0.0
    core_scale = 0.0

    # ── Panel layout ──────────────────────────────────────────────────────────
    PW, PH  = 250, 175
    SCHED_H = 215
    SB_H    = 24     # status bar height
    PAD     = 20
    RESP_H  = 100
    cx, cy  = WIN_W / 2, WIN_H / 2
    min_dim = min(WIN_W, WIN_H)

    rect_sys   = pygame.Rect(PAD,              PAD,                     PW, PH)
    rect_clk   = pygame.Rect(WIN_W - PAD - PW, PAD,                     PW, PH)
    rect_wx    = pygame.Rect(PAD,              WIN_H - SB_H - PAD - PH, PW, PH)
    rect_sched = pygame.Rect(WIN_W - PAD - PW, WIN_H - SB_H - PAD - SCHED_H, PW, SCHED_H)
    RESP_W     = WIN_W - 2 * PAD - 2 * PW - 40
    rect_resp  = pygame.Rect(PAD + PW + 20,
                              WIN_H - SB_H - PAD - RESP_H,
                              RESP_W, RESP_H)
    rect_sb    = pygame.Rect(0, WIN_H - SB_H, WIN_W, SB_H)

    # ── Waveform bars ─────────────────────────────────────────────────────────
    NBAR    = 48
    bars_   = [0.0] * NBAR
    bar_vel = [random.uniform(-0.05, 0.05) for _ in range(NBAR)]

    # ── Background threads ────────────────────────────────────────────────────
    threading.Thread(target=_state_reader_loop, daemon=True).start()
    threading.Thread(target=_weather_loop,      daemon=True).start()
    threading.Thread(target=_sysstat_loop,      daemon=True).start()

    running = True
    while running:
        dt = clock_pg.tick(FPS) / 1000.0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False

        # ── Read state snapshot ───────────────────────────────────────────────
        with _lock:
            if not _state["running"]:
                bye_prog += dt * 0.65
                if bye_prog >= 1.6:
                    running = False
            mode     = _state["mode"]
            resp_txt = _state["response_text"]
            weather  = _state["weather"].copy()
            sys_info = _state["sys"].copy()
            mic_ok   = _state["mic_ok"]
            ai_ok    = _state["ai_ok"]
            tts_ok   = _state["tts_ok"]
            _state["response_age"] += dt
            if _state["response_fade"] < 1.0:
                _state["response_fade"] = min(1.0,
                    _state["response_fade"] + dt * 1.5)
            resp_fade = _state["response_fade"]

        # ── Boot timing ───────────────────────────────────────────────────────
        boot_elapsed  = time.time() - boot_start
        boot_progress = min(1.0, boot_elapsed / BOOT_DUR)
        boot_done     = boot_progress >= 1.0
        core_scale    = _ease_out(
            min(1.0, max(0.0, (boot_elapsed - 0.6) / 1.2))
        )

        def _ps(sf=0.55, df=0.30):
            t = (boot_progress - sf) / df
            return _ease_out(t)

        ps_tl = _ps(0.50, 0.35)
        ps_tr = _ps(0.58, 0.35)
        ps_bl = _ps(0.66, 0.35)
        ps_br = _ps(0.74, 0.35)
        ps_re = _ps(0.82, 0.25)

        # ── Animation ticks ───────────────────────────────────────────────────
        spd = {"idle": 1.0, "listening": 2.8, "thinking": 1.6,
               "speaking": 2.5, "boot": 0.8, "bye": 0.4}.get(mode, 1.0)

        phase      += 0.022 * spd; phase      %= 2 * math.pi
        ring_phase += 0.050 * spd; ring_phase %= 2 * math.pi
        shimmer    += 1.80  * spd; shimmer    %= 360.0
        scan_y      = (scan_y + 0.0018 * spd) % 1.0
        hex_phase  += 0.0006

        # Waveform
        if mode == "speaking":
            for i in range(NBAR):
                tgt = random.uniform(0.15, 1.0) * abs(
                    math.sin(phase * 4 + i * 0.55 + bar_vel[i]))
                bars_[i] += (tgt - bars_[i]) * 0.22
        else:
            for i in range(NBAR):
                bars_[i] *= 0.88

        # ── Draw ──────────────────────────────────────────────────────────────
        screen.fill(BG)
        _draw_hex_grid(screen, hex_phase, alpha=13)
        _draw_scan_lines(screen, scan_y, alpha=22)

        if not boot_done:
            _draw_boot(screen, cx, cy, boot_progress, fonts)
            if core_scale > 0.05:
                _draw_core(screen, cx, cy, "boot", phase, ring_phase,
                           shimmer, bars_, scale=core_scale)
        else:
            _draw_panel_system(screen,  rect_sys,   sys_info, fonts, slide=ps_tl)
            _draw_panel_clock(screen,   rect_clk,   fonts,           slide=ps_tr)
            _draw_panel_weather(screen, rect_wx,    weather,  fonts, slide=ps_bl)
            _draw_panel_schedule(screen, rect_sched, fonts,          slide=ps_br)
            _draw_response_panel(screen, rect_resp, resp_txt, resp_fade,
                                 mode, fonts, slide=ps_re)
            _draw_status_bar(screen, rect_sb, mode, mic_ok, ai_ok, tts_ok, fonts)

            live_scale = max(0.01, 1.0 - bye_prog * 1.2) if bye_prog > 0 else 1.0
            _draw_core(screen, cx, cy, mode, phase, ring_phase,
                       shimmer, bars_, scale=live_scale)
            _draw_friday_label(screen, cx, cy, fonts, phase, min_dim,
                               scale=min(1.0, ps_tl + 0.1))
            _draw_state_label(screen, cx, cy, mode, fonts, min_dim,
                              scale=min(1.0, ps_tl + 0.1))

            # Bye overlay
            if bye_prog > 0:
                ov = _asurf(WIN_W, WIN_H)
                ov.fill((0, 0, 0, min(255, int(bye_prog * 220))))
                screen.blit(ov, (0, 0))
                if bye_prog > 0.3:
                    ta  = int(min(255, (bye_prog - 0.3) * 450))
                    txt = fonts["lg"].render("SHUTTING DOWN", True, RED_DIM)
                    txt.set_alpha(ta)
                    screen.blit(txt, (int(cx - txt.get_width() / 2),
                                      int(cy - txt.get_height() / 2)))

        # Watermark
        wm = fonts["xs"].render("FRIDAY v2  |  AI ASSISTANT", True, CYAN_DIM)
        wm.set_alpha(55)
        screen.blit(wm, (WIN_W - wm.get_width() - 10, 6))

        pygame.display.flip()

    with _lock:
        _state["running"] = False
    pygame.quit()


# ══════════════════════════════════════════════════════════════════════════════
#  ENTRY POINT  (normally called by friday.py subprocess)
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    run_hud()
