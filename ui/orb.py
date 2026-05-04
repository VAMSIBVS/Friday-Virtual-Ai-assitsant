"""
Friday UI — Floating Orb Interface
====================================
A frameless, always-on-top ambient presence window.
Pure QPainter rendering — no heavy assets.

States → Visual behavior:
  idle      → slow breathing cyan/teal glow
  listening → faster active pulse with expanding rings
  thinking  → rotating shimmer gradient
  speaking  → neon ripple radiating outward
"""

import math
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QApplication, QSizePolicy
)
from PyQt5.QtCore import (
    Qt, QTimer, QPointF, QRectF, QPropertyAnimation,
    QEasingCurve, pyqtProperty, QThread
)
from PyQt5.QtGui import (
    QPainter, QColor, QRadialGradient, QLinearGradient,
    QBrush, QPen, QPainterPath, QFont, QFontDatabase
)


# ── Color Palette ───────────────────────────────────────────────────────────
C_BG        = QColor(8, 8, 16)           # Near-black background
C_ORB_CORE  = QColor(0, 220, 255)        # Cyan core
C_ORB_MID   = QColor(0, 160, 210, 180)  # Mid cyan
C_ORB_GLOW  = QColor(0, 100, 180, 60)   # Outer glow
C_IDLE      = QColor(0, 200, 240)        # Idle ring color
C_LISTEN    = QColor(0, 255, 200)        # Listening — teal-green
C_THINK     = QColor(140, 80, 255)       # Thinking — purple
C_SPEAK     = QColor(0, 230, 160)        # Speaking — bright teal
C_TEXT      = QColor(160, 220, 240)      # Status label text
C_TEXT_DIM  = QColor(60, 100, 120)       # Dim text

# State labels shown below the orb
STATE_LABELS = {
    "idle":      "",
    "listening": "Listening...",
    "thinking":  "Thinking...",
    "speaking":  "Speaking...",
}


class FridayOrbWidget(QWidget):
    """
    The animated orb — drawn entirely via QPainter.
    Receives state changes and animates accordingly.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._state = "idle"
        self._phase = 0.0          # 0.0 – 2π, drives breathing / pulse
        self._ring_phase = 0.0     # Ripple ring offset
        self._shimmer_angle = 0.0  # Thinking rotation angle
        self._alpha = 1.0          # Overall opacity for transitions

        # Timer drives all animation (60 fps target)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(16)  # ~60 fps

        self._tick_count = 0

        # Orb size (will be scaled from widget size)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumSize(200, 200)

    def set_state(self, state: str):
        if state not in STATE_LABELS:
            return
        self._state = state
        self._ring_phase = 0.0

    def _tick(self):
        self._tick_count += 1

        # Phase increments depend on state
        if self._state == "idle":
            self._phase += 0.025          # slow breathing
        elif self._state == "listening":
            self._phase += 0.07           # faster pulse
            self._ring_phase += 0.04
        elif self._state == "thinking":
            self._phase += 0.04
            self._shimmer_angle += 2.0    # rotate shimmer
        elif self._state == "speaking":
            self._phase += 0.06
            self._ring_phase += 0.06      # ripple outward

        # Keep phase in [0, 2π]
        self._phase %= (2 * math.pi)
        self._shimmer_angle %= 360.0
        self._ring_phase %= (2 * math.pi)

        self.update()

    def paintEvent(self, event):
        # BUG 4 FIX: wrap entire paint loop — no exception (including
        # KeyboardInterrupt) should ever propagate out of paintEvent.
        try:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setRenderHint(QPainter.SmoothPixmapTransform)

            w, h = self.width(), self.height()
            cx, cy = w / 2.0, h / 2.0
            base_r = min(w, h) * 0.32  # Orb radius

            # ── Background ───────────────────────────────────────────────────
            painter.fillRect(self.rect(), C_BG)

            # ── Draw based on state ──────────────────────────────────────────
            if self._state == "idle":
                self._draw_idle(painter, cx, cy, base_r)
            elif self._state == "listening":
                self._draw_listening(painter, cx, cy, base_r)
            elif self._state == "thinking":
                self._draw_thinking(painter, cx, cy, base_r)
            elif self._state == "speaking":
                self._draw_speaking(painter, cx, cy, base_r)

            painter.end()
        except Exception:
            # Silently swallow — never let a paint failure kill the process
            pass

    def _breath_value(self, speed=1.0) -> float:
        """Returns a 0.0–1.0 sine-wave value, creating a breathing effect."""
        return (math.sin(self._phase * speed) + 1.0) / 2.0

    def _draw_core_orb(self, painter, cx, cy, r, color_core=None, color_mid=None, glow_alpha=80):
        """Draws the central orb sphere with radial gradient."""
        cc = color_core or C_ORB_CORE
        cm = color_mid or C_ORB_MID

        grad = QRadialGradient(QPointF(cx - r * 0.25, cy - r * 0.25), r * 1.3)
        grad.setColorAt(0.0, QColor(255, 255, 255, 200))   # bright highlight
        grad.setColorAt(0.15, cc)
        grad.setColorAt(0.55, cm)
        grad.setColorAt(0.85, QColor(cc.red(), cc.green(), cc.blue(), 40))
        grad.setColorAt(1.0, QColor(0, 0, 0, 0))

        painter.setBrush(QBrush(grad))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QPointF(cx, cy), r, r)

    def _draw_glow_ring(self, painter, cx, cy, radius, color, width=3, alpha=180):
        """Draws a single glowing ring."""
        pen_color = QColor(color.red(), color.green(), color.blue(), alpha)
        pen = QPen(pen_color, width)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(QPointF(cx, cy), radius, radius)

    # ── Idle: calm breathing glow ────────────────────────────────────────────
    def _draw_idle(self, painter, cx, cy, base_r):
        breath = self._breath_value()

        # Outer diffuse glow (pulses with breath)
        glow_r = base_r * 1.05 + breath * base_r * 0.18
        glow_alpha = int(30 + breath * 40)
        grad = QRadialGradient(QPointF(cx, cy), glow_r)
        glow_c = C_IDLE
        grad.setColorAt(0.0, QColor(glow_c.red(), glow_c.green(), glow_c.blue(), glow_alpha))
        grad.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.setBrush(QBrush(grad))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QPointF(cx, cy), glow_r * 1.6, glow_r * 1.6)

        # Soft orbit ring
        ring_r = base_r * 1.12 + breath * base_r * 0.08
        ring_a = int(40 + breath * 60)
        self._draw_glow_ring(painter, cx, cy, ring_r, C_IDLE, width=1, alpha=ring_a)

        # Core orb (scaled with breath)
        orb_r = base_r * (0.90 + breath * 0.07)
        self._draw_core_orb(painter, cx, cy, orb_r)

    # ── Listening: active pulse with expanding rings ──────────────────────────
    def _draw_listening(self, painter, cx, cy, base_r):
        breath = self._breath_value(speed=1.8)

        # Three expanding pulse rings
        for i in range(3):
            offset = (self._ring_phase + i * (2 * math.pi / 3)) % (2 * math.pi)
            expand = (math.sin(offset) + 1.0) / 2.0
            ring_r = base_r * (1.1 + expand * 0.7)
            alpha = int(180 * (1.0 - expand))
            if alpha > 0:
                self._draw_glow_ring(painter, cx, cy, ring_r, C_LISTEN,
                                     width=max(1, int(2 * (1 - expand))), alpha=alpha)

        # Bright inner glow
        glow_r = base_r * (1.0 + breath * 0.15)
        grad = QRadialGradient(QPointF(cx, cy), glow_r * 1.2)
        grad.setColorAt(0.0, QColor(C_LISTEN.red(), C_LISTEN.green(), C_LISTEN.blue(), 50))
        grad.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.setBrush(QBrush(grad))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QPointF(cx, cy), glow_r * 1.2, glow_r * 1.2)

        # Core orb (slightly larger, brighter)
        orb_r = base_r * (0.92 + breath * 0.06)
        self._draw_core_orb(painter, cx, cy, orb_r,
                            color_core=C_LISTEN,
                            color_mid=QColor(0, 200, 180, 180))

    # ── Thinking: rotating shimmer gradient ──────────────────────────────────
    def _draw_thinking(self, painter, cx, cy, base_r):
        breath = self._breath_value()

        # Rotating outer arc (shimmer)
        painter.save()
        painter.translate(cx, cy)
        painter.rotate(self._shimmer_angle)

        pen = QPen(C_THINK, 2)
        pen.setCapStyle(Qt.RoundCap)
        pen.setDashPattern([4, 6, 2, 6])
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        arc_r = base_r * 1.18
        painter.drawEllipse(QPointF(0, 0), arc_r, arc_r)

        # Opposite direction arc
        painter.rotate(180)
        pen2 = QPen(QColor(200, 120, 255, 120), 1)
        pen2.setDashPattern([2, 8])
        painter.setPen(pen2)
        painter.drawEllipse(QPointF(0, 0), arc_r * 0.85, arc_r * 0.85)
        painter.restore()

        # Pulsing glow
        glow_r = base_r * (1.05 + breath * 0.1)
        grad = QRadialGradient(QPointF(cx, cy), glow_r)
        grad.setColorAt(0.0, QColor(C_THINK.red(), C_THINK.green(), C_THINK.blue(), 30))
        grad.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.setBrush(QBrush(grad))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QPointF(cx, cy), glow_r * 1.4, glow_r * 1.4)

        # Core orb
        orb_r = base_r * (0.88 + breath * 0.05)
        self._draw_core_orb(painter, cx, cy, orb_r,
                            color_core=QColor(180, 120, 255),
                            color_mid=QColor(140, 80, 220, 180))

    # ── Speaking: neon ripple radiating outward ───────────────────────────────
    def _draw_speaking(self, painter, cx, cy, base_r):
        breath = self._breath_value(speed=2.0)

        # Four ripple rings radiating out
        for i in range(4):
            offset = (self._ring_phase + i * (math.pi / 2)) % (2 * math.pi)
            progress = (math.sin(offset) + 1.0) / 2.0
            ring_r = base_r * (1.05 + progress * 0.9)
            alpha = int(200 * (1.0 - progress) * (0.5 + 0.5 * math.sin(offset * 3)))
            width = max(1, int(3 * (1.0 - progress * 0.7)))
            if alpha > 5:
                self._draw_glow_ring(painter, cx, cy, ring_r, C_SPEAK,
                                     width=width, alpha=alpha)

        # Inner warm glow
        glow_r = base_r * (1.0 + breath * 0.12)
        grad = QRadialGradient(QPointF(cx, cy), glow_r)
        grad.setColorAt(0.0, QColor(C_SPEAK.red(), C_SPEAK.green(), C_SPEAK.blue(), 60))
        grad.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.setBrush(QBrush(grad))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QPointF(cx, cy), glow_r * 1.3, glow_r * 1.3)

        # Core orb
        orb_r = base_r * (0.91 + breath * 0.07)
        self._draw_core_orb(painter, cx, cy, orb_r,
                            color_core=C_SPEAK,
                            color_mid=QColor(0, 200, 140, 180))


class FridayOrb(QWidget):
    """
    Main Friday window — frameless, always-on-top, draggable.
    Contains the orb widget + state label.
    """

    def __init__(self):
        super().__init__()
        self._drag_pos = None
        self._setup_window()
        self._setup_ui()

    def _setup_window(self):
        self.setWindowTitle("Friday")
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool               # Doesn't appear in taskbar
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_NoSystemBackground)
        self.resize(280, 320)

        # Position: bottom-right corner
        screen = QApplication.primaryScreen().availableGeometry()
        self.move(
            screen.right() - self.width() - 24,
            screen.bottom() - self.height() - 24
        )

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 16)
        layout.setSpacing(8)

        # The animated orb
        self.orb = FridayOrbWidget(self)
        layout.addWidget(self.orb, stretch=1)

        # Status label
        self.status_label = QLabel("", self)
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setFixedHeight(22)
        self._apply_label_style(self.status_label, bright=False)
        layout.addWidget(self.status_label)

        # "FRIDAY" name label (small, always visible)
        self.name_label = QLabel("F R I D A Y", self)
        self.name_label.setAlignment(Qt.AlignCenter)
        self.name_label.setFixedHeight(18)
        self._apply_label_style(self.name_label, bright=True, size=9)
        layout.addWidget(self.name_label)

    def _apply_label_style(self, label: QLabel, bright=False, size=10):
        color = "#80DCF0" if bright else "#3C647A"
        label.setStyleSheet(
            f"color: {color}; "
            f"font-family: 'Consolas', 'Courier New', monospace; "
            f"font-size: {size}px; "
            f"letter-spacing: 2px; "
            f"background: transparent; "
            f"border: none;"
        )

    # ── Public API ────────────────────────────────────────────────────────────
    def set_state(self, state: str):
        """Update the orb state and status label. Call from any thread via signal."""
        self.orb.set_state(state)
        label_text = STATE_LABELS.get(state, "")
        self.status_label.setText(label_text)

        # Update status label color to match state
        colors = {
            "idle":      "#3C647A",
            "listening": "#00FFC8",
            "thinking":  "#8C50FF",
            "speaking":  "#00E6A0",
        }
        c = colors.get(state, "#3C647A")
        self.status_label.setStyleSheet(
            f"color: {c}; "
            f"font-family: 'Consolas', 'Courier New', monospace; "
            f"font-size: 10px; "
            f"letter-spacing: 2px; "
            f"background: transparent; "
            f"border: none;"
        )

    # ── Drag support ──────────────────────────────────────────────────────────
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and self._drag_pos is not None:
            self.move(event.globalPos() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
