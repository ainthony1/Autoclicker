"""
Autoclicker v2.1 — Dark themed, F8 toggle, CPS or MAX mode

Deps:
  pip install pynput

Features:
- Dark modern UI
- Left / Right / Middle click selection
- Single or Double click
- CPS mode (0.1-1000) with precise timing
- MAX mode (fastest possible)
- Randomized interval option (humanized clicking)
- Live click counter
- F8 hotkey toggle
- Direct Win32 SendInput for minimal CPU usage
"""

import ctypes
import ctypes.wintypes
import random
import threading
import time
import tkinter as tk
from tkinter import messagebox

try:
    from pynput import keyboard
except ImportError:
    raise SystemExit("pynput is required. Run: pip install pynput")


# ── Win32 SendInput click (bypasses pyautogui overhead entirely) ──

class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", ctypes.wintypes.LONG),
        ("dy", ctypes.wintypes.LONG),
        ("mouseData", ctypes.wintypes.DWORD),
        ("dwFlags", ctypes.wintypes.DWORD),
        ("time", ctypes.wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]

class INPUT(ctypes.Structure):
    class _INPUT(ctypes.Union):
        _fields_ = [("mi", MOUSEINPUT)]
    _fields_ = [("type", ctypes.wintypes.DWORD), ("_input", _INPUT)]

MOUSEEVENTF_LEFTDOWN   = 0x0002
MOUSEEVENTF_LEFTUP     = 0x0004
MOUSEEVENTF_RIGHTDOWN  = 0x0008
MOUSEEVENTF_RIGHTUP    = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP   = 0x0040

_BUTTON_FLAGS = {
    "left":   (MOUSEEVENTF_LEFTDOWN,   MOUSEEVENTF_LEFTUP),
    "right":  (MOUSEEVENTF_RIGHTDOWN,  MOUSEEVENTF_RIGHTUP),
    "middle": (MOUSEEVENTF_MIDDLEDOWN, MOUSEEVENTF_MIDDLEUP),
}

_SendInput = ctypes.windll.user32.SendInput
_GetCursorPos = ctypes.windll.user32.GetCursorPos

def _make_mouse_input(flags):
    mi = MOUSEINPUT(0, 0, 0, flags, 0, ctypes.pointer(ctypes.c_ulong(0)))
    inp = INPUT(type=0)
    inp._input.mi = mi
    return inp

def fast_click(button="left"):
    """Single click using SendInput — near zero overhead."""
    down_flag, up_flag = _BUTTON_FLAGS[button]
    inputs = (INPUT * 2)(_make_mouse_input(down_flag), _make_mouse_input(up_flag))
    _SendInput(2, inputs, ctypes.sizeof(INPUT))

def fast_double_click(button="left"):
    """Double click using SendInput."""
    down_flag, up_flag = _BUTTON_FLAGS[button]
    inp_down = _make_mouse_input(down_flag)
    inp_up = _make_mouse_input(up_flag)
    inputs = (INPUT * 4)(inp_down, inp_up, inp_down, inp_up)
    _SendInput(4, inputs, ctypes.sizeof(INPUT))

def _cursor_in_corner() -> bool:
    """Check if mouse is in top-left corner (failsafe)."""
    pt = ctypes.wintypes.POINT()
    _GetCursorPos(ctypes.byref(pt))
    return pt.x <= 5 and pt.y <= 5


# ── Precise sleep ──

_perf_counter = time.perf_counter
_sleep = time.sleep

def sleep_until(target: float):
    remaining = target - _perf_counter()
    if remaining <= 0:
        return
    if remaining > 0.005:
        _sleep(remaining - 0.003)
    # Spin for final precision
    while _perf_counter() < target:
        pass


# ── AutoClicker engine ──

class AutoClicker:
    def __init__(self):
        self.enabled = False
        self.stop_event = threading.Event()
        self.lock = threading.Lock()
        self.click_button = "left"
        self.double_click = False
        self.cps = 10.0
        self.max_mode = False
        self.randomize = False
        self.click_count = 0

    def set_cps(self, cps: float):
        with self.lock:
            self.cps = max(0.1, min(1000.0, float(cps)))

    def set_max_mode(self, enabled: bool):
        with self.lock:
            self.max_mode = bool(enabled)

    def toggle(self):
        with self.lock:
            self.enabled = not self.enabled
            if self.enabled:
                self.click_count = 0
        return self.enabled

    def stop(self):
        self.stop_event.set()
        with self.lock:
            self.enabled = False

    def click_loop(self, on_tick=None):
        stop = self.stop_event
        lock = self.lock

        while not stop.is_set():
            # Wait until enabled
            if not self.enabled:
                _sleep(0.02)
                continue

            # Snapshot settings once
            with lock:
                max_mode = self.max_mode
                button = self.click_button
                dbl = self.double_click
                cps = self.cps
                randomize = self.randomize

            click_fn = fast_double_click if dbl else fast_click
            failsafe_check = 0

            try:
                if max_mode:
                    while self.enabled and not stop.is_set():
                        click_fn(button)
                        self.click_count += 1
                        # Check failsafe every 256 clicks (cheap counter)
                        failsafe_check += 1
                        if failsafe_check & 0xFF == 0:
                            if _cursor_in_corner():
                                with lock:
                                    self.enabled = False
                                break
                            # Re-read settings periodically
                            with lock:
                                if not self.max_mode:
                                    break
                                button = self.click_button
                                dbl = self.double_click
                            click_fn = fast_double_click if dbl else fast_click
                else:
                    interval = 1.0 / cps
                    next_time = _perf_counter()
                    while self.enabled and not stop.is_set():
                        click_fn(button)
                        self.click_count += 1
                        next_time += interval
                        if randomize:
                            # Apply jitter: +/- 20%
                            jitter = interval * random.uniform(-0.2, 0.2)
                            sleep_until(next_time + jitter)
                        else:
                            sleep_until(next_time)
                        # Failsafe + settings refresh every 128 clicks
                        failsafe_check += 1
                        if failsafe_check & 0x7F == 0:
                            if _cursor_in_corner():
                                with lock:
                                    self.enabled = False
                                break
                            with lock:
                                if self.max_mode:
                                    break
                                new_cps = self.cps
                                button = self.click_button
                                dbl = self.double_click
                                randomize = self.randomize
                            if new_cps != cps:
                                cps = new_cps
                                interval = 1.0 / cps
                                next_time = _perf_counter()
                            click_fn = fast_double_click if dbl else fast_click
            except Exception as e:
                with lock:
                    self.enabled = False
                if on_tick:
                    on_tick(error=str(e))

            if on_tick:
                on_tick()


# ── Dark Theme ──

BG = "#1a1a2e"
BG_LIGHT = "#16213e"
FG = "#e0e0e0"
ACCENT = "#0f3460"
ACCENT_HOVER = "#533483"
GREEN = "#00c853"
RED = "#ff1744"
ENTRY_BG = "#0a0a1a"


class DarkButton(tk.Button):
    def __init__(self, parent, text="", command=None, width=12, height=1,
                 bg=ACCENT, fg=FG, hover_bg=ACCENT_HOVER, **kwargs):
        super().__init__(parent, text=text, command=command,
                         bg=bg, fg=fg, activebackground=hover_bg,
                         activeforeground=fg, bd=0, relief=tk.FLAT,
                         font=("Segoe UI", 10, "bold"), cursor="hand2",
                         width=width, height=height, **kwargs)
        self._bg = bg
        self._hover_bg = hover_bg
        self.bind("<Enter>", lambda e: self.config(bg=hover_bg))
        self.bind("<Leave>", lambda e: self.config(bg=self._bg))

    def set_text(self, text):
        self.config(text=text)

    def set_colors(self, bg, hover_bg):
        self._bg = bg
        self._hover_bg = hover_bg
        self.config(bg=bg, activebackground=hover_bg)


# ── App ──

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Autoclicker v2.1")
        self.geometry("460x400")
        self.resizable(False, False)
        self.configure(bg=BG)

        self.clicker = AutoClicker()

        # Header
        header = tk.Frame(self, bg=ACCENT, height=50)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        tk.Label(header, text="AUTOCLICKER", font=("Segoe UI", 16, "bold"),
                 bg=ACCENT, fg=FG).pack(side=tk.LEFT, padx=16)
        self.status_dot = tk.Canvas(header, width=16, height=16, bg=ACCENT, highlightthickness=0)
        self.status_dot.pack(side=tk.RIGHT, padx=16)
        self._draw_dot(False)

        main = tk.Frame(self, bg=BG, padx=20, pady=12)
        main.pack(fill=tk.BOTH, expand=True)

        # Status
        self.status_var = tk.StringVar(value="DISABLED")
        self.status_label = tk.Label(main, textvariable=self.status_var,
                                     font=("Segoe UI", 12, "bold"), bg=BG, fg=RED)
        self.status_label.pack(anchor="w", pady=(0, 8))

        # Click counter
        self.count_var = tk.StringVar(value="Clicks: 0")
        tk.Label(main, textvariable=self.count_var, font=("Segoe UI", 9),
                 bg=BG, fg="#888").pack(anchor="w", pady=(0, 10))

        # Settings
        settings = tk.LabelFrame(main, text=" Settings ", font=("Segoe UI", 9, "bold"),
                                 bg=BG_LIGHT, fg=FG, bd=1, relief=tk.GROOVE,
                                 padx=12, pady=8)
        settings.pack(fill=tk.X, pady=(0, 10))

        # CPS row
        cps_row = tk.Frame(settings, bg=BG_LIGHT)
        cps_row.pack(fill=tk.X, pady=4)
        tk.Label(cps_row, text="CPS (0.1-1000):", font=("Segoe UI", 9),
                 bg=BG_LIGHT, fg=FG).pack(side=tk.LEFT)
        self.cps_var = tk.StringVar(value="10")
        self.cps_entry = tk.Entry(cps_row, textvariable=self.cps_var, width=8,
                                  bg=ENTRY_BG, fg=FG, insertbackground=FG,
                                  font=("Consolas", 10), bd=0, relief=tk.FLAT)
        self.cps_entry.pack(side=tk.LEFT, padx=(8, 8))
        DarkButton(cps_row, text="Apply", command=self.apply_cps,
                   width=8, height=1).pack(side=tk.LEFT)

        # Mouse button row
        btn_row = tk.Frame(settings, bg=BG_LIGHT)
        btn_row.pack(fill=tk.X, pady=4)
        tk.Label(btn_row, text="Button:", font=("Segoe UI", 9),
                 bg=BG_LIGHT, fg=FG).pack(side=tk.LEFT)
        self.btn_var = tk.StringVar(value="left")
        for val, label in [("left", "Left"), ("right", "Right"), ("middle", "Middle")]:
            rb = tk.Radiobutton(btn_row, text=label, variable=self.btn_var,
                                value=val, command=self._update_button,
                                bg=BG_LIGHT, fg=FG, selectcolor=ACCENT,
                                activebackground=BG_LIGHT, activeforeground=FG,
                                font=("Segoe UI", 9))
            rb.pack(side=tk.LEFT, padx=(8, 0))

        # Click type row
        type_row = tk.Frame(settings, bg=BG_LIGHT)
        type_row.pack(fill=tk.X, pady=4)
        tk.Label(type_row, text="Click:", font=("Segoe UI", 9),
                 bg=BG_LIGHT, fg=FG).pack(side=tk.LEFT)
        self.click_type_var = tk.StringVar(value="single")
        for val, label in [("single", "Single"), ("double", "Double")]:
            rb = tk.Radiobutton(type_row, text=label, variable=self.click_type_var,
                                value=val, command=self._update_click_type,
                                bg=BG_LIGHT, fg=FG, selectcolor=ACCENT,
                                activebackground=BG_LIGHT, activeforeground=FG,
                                font=("Segoe UI", 9))
            rb.pack(side=tk.LEFT, padx=(8, 0))

        # Checkboxes row
        chk_row = tk.Frame(settings, bg=BG_LIGHT)
        chk_row.pack(fill=tk.X, pady=4)
        self.max_mode_var = tk.BooleanVar(value=False)
        tk.Checkbutton(chk_row, text="MAX mode", variable=self.max_mode_var,
                       command=self._toggle_max, bg=BG_LIGHT, fg=FG,
                       selectcolor=ACCENT, activebackground=BG_LIGHT,
                       activeforeground=FG, font=("Segoe UI", 9)).pack(side=tk.LEFT)
        self.randomize_var = tk.BooleanVar(value=False)
        tk.Checkbutton(chk_row, text="Randomize intervals", variable=self.randomize_var,
                       command=self._toggle_randomize, bg=BG_LIGHT, fg=FG,
                       selectcolor=ACCENT, activebackground=BG_LIGHT,
                       activeforeground=FG, font=("Segoe UI", 9)).pack(side=tk.LEFT, padx=(16, 0))

        # Action buttons
        action_row = tk.Frame(main, bg=BG)
        action_row.pack(fill=tk.X, pady=(4, 8))
        self.toggle_btn = DarkButton(action_row, text="ENABLE", command=self.on_toggle,
                                     width=14, height=1, bg="#006400", hover_bg=GREEN)
        self.toggle_btn.pack(side=tk.LEFT)
        DarkButton(action_row, text="QUIT", command=self.on_quit,
                   width=8, height=1, bg="#8b0000", hover_bg=RED).pack(side=tk.RIGHT)

        # Footer
        tk.Label(main, text="Press F8 to toggle  |  Move mouse to corner = emergency stop",
                 font=("Segoe UI", 8), bg=BG, fg="#555").pack(anchor="w", pady=(4, 0))

        # Worker thread
        self.worker = threading.Thread(target=self.clicker.click_loop,
                                       kwargs={"on_tick": self.on_tick}, daemon=True)
        self.worker.start()

        # Global hotkey
        self.listener = keyboard.Listener(on_press=self.on_key_press)
        self.listener.daemon = True
        self.listener.start()

        self.cps_entry.bind("<Return>", self.apply_cps)
        self.protocol("WM_DELETE_WINDOW", self.on_quit)
        self._update_counter()

    def _draw_dot(self, enabled):
        self.status_dot.delete("all")
        color = GREEN if enabled else RED
        self.status_dot.create_oval(2, 2, 14, 14, fill=color, outline="")

    def _update_button(self):
        self.clicker.click_button = self.btn_var.get()

    def _update_click_type(self):
        self.clicker.double_click = self.click_type_var.get() == "double"

    def _toggle_max(self):
        self.clicker.set_max_mode(self.max_mode_var.get())

    def _toggle_randomize(self):
        with self.clicker.lock:
            self.clicker.randomize = self.randomize_var.get()

    def _update_counter(self):
        self.count_var.set(f"Clicks: {self.clicker.click_count:,}")
        self.after(200, self._update_counter)

    def apply_cps(self, event=None):
        if self.max_mode_var.get():
            messagebox.showinfo("MAX mode", "Disable MAX mode to set CPS.")
            return
        raw = self.cps_var.get().strip()
        try:
            val = float(raw)
            self.clicker.set_cps(val)
            self.cps_var.set(f"{self.clicker.cps:.2f}".rstrip("0").rstrip("."))
            if val != self.clicker.cps:
                messagebox.showinfo("CPS", "Clamped to 0.1-1000 range.")
        except ValueError:
            messagebox.showerror("Invalid", "Enter a number (0.1-1000).")
            self.cps_var.set(f"{self.clicker.cps:.2f}".rstrip("0").rstrip("."))

    def on_key_press(self, key):
        try:
            if key == keyboard.Key.f8:
                self.after(0, self.on_toggle)
        except Exception:
            pass

    def on_toggle(self):
        now_enabled = self.clicker.toggle()
        self._draw_dot(now_enabled)
        self.status_var.set("ENABLED" if now_enabled else "DISABLED")
        self.status_label.config(fg=GREEN if now_enabled else RED)
        self.toggle_btn.set_text("DISABLE" if now_enabled else "ENABLE")
        if now_enabled:
            self.toggle_btn.set_colors("#8b0000", RED)
        else:
            self.toggle_btn.set_colors("#006400", GREEN)

    def on_tick(self, error: str | None = None):
        if error:
            self.after(0, lambda: messagebox.showerror("Error", error))
            self.after(0, lambda: self.on_toggle())

    def on_quit(self):
        try:
            self.clicker.stop()
            if self.listener:
                self.listener.stop()
        finally:
            self.destroy()


if __name__ == "__main__":
    try:
        App().mainloop()
    except KeyboardInterrupt:
        pass
