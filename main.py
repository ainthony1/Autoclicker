"""
Autoclicker v2 — Dark themed, F6 toggle, CPS or MAX mode

Deps:
  pip install pyautogui pynput

Features:
- Dark modern UI
- Left / Right / Middle click selection
- Single or Double click
- CPS mode (0.1-500) with precise timing
- MAX mode (fastest possible)
- Randomized interval option (humanized clicking)
- Live click counter
- F6 hotkey toggle (changed from F4 to avoid browser conflicts)
"""

import random
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox

try:
    import pyautogui
except ImportError:
    raise SystemExit("pyautogui is required. Run: pip install pyautogui")

try:
    from pynput import keyboard
except ImportError:
    raise SystemExit("pynput is required. Run: pip install pynput")

# Remove PyAutoGUI's built-in throttles
pyautogui.PAUSE = 0.0
for attr in ("MINIMUM_SLEEP", "MINIMUM_DURATION"):
    if hasattr(pyautogui, attr):
        setattr(pyautogui, attr, 0.0)
if hasattr(pyautogui, "DARWIN_CATCH_UP_TIME"):
    pyautogui.DARWIN_CATCH_UP_TIME = 0


def sleep_until(target_time: float):
    while True:
        remaining = target_time - time.perf_counter()
        if remaining <= 0:
            return
        if remaining > 0.002:
            time.sleep(remaining - 0.001)
        else:
            while time.perf_counter() < target_time:
                pass
            return


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
            self.cps = max(0.1, min(500.0, float(cps)))

    def set_max_mode(self, enabled: bool):
        with self.lock:
            self.max_mode = bool(enabled)

    def get_interval(self) -> float:
        with self.lock:
            interval = 1.0 / self.cps
            if self.randomize:
                # +/- 20% randomization
                interval *= random.uniform(0.8, 1.2)
        return interval

    def toggle(self):
        with self.lock:
            self.enabled = not self.enabled
            if self.enabled:
                self.click_count = 0
        return self.enabled

    def is_enabled(self) -> bool:
        with self.lock:
            return self.enabled

    def is_max_mode(self) -> bool:
        with self.lock:
            return self.max_mode

    def stop(self):
        self.stop_event.set()
        with self.lock:
            self.enabled = False

    def do_click(self):
        if self.double_click:
            pyautogui.doubleClick(button=self.click_button)
        else:
            pyautogui.click(button=self.click_button)
        with self.lock:
            self.click_count += 1

    def click_loop(self, on_tick=None):
        while not self.stop_event.is_set():
            if not self.is_enabled():
                time.sleep(0.02)
                if on_tick:
                    on_tick()
                continue

            if self.is_max_mode():
                try:
                    while self.is_enabled() and not self.stop_event.is_set() and self.is_max_mode():
                        self.do_click()
                except Exception as e:
                    with self.lock:
                        self.enabled = False
                    if on_tick:
                        on_tick(error=str(e))
            else:
                next_time = time.perf_counter()
                try:
                    while self.is_enabled() and not self.stop_event.is_set() and not self.is_max_mode():
                        self.do_click()
                        interval = self.get_interval()
                        next_time += interval
                        sleep_until(next_time)
                except Exception as e:
                    with self.lock:
                        self.enabled = False
                    if on_tick:
                        on_tick(error=str(e))

            if on_tick:
                on_tick()


# -- Dark Theme Colors --
BG = "#1a1a2e"
BG_LIGHT = "#16213e"
FG = "#e0e0e0"
ACCENT = "#0f3460"
ACCENT_HOVER = "#533483"
GREEN = "#00c853"
RED = "#ff1744"
ENTRY_BG = "#0a0a1a"
BORDER = "#2a2a4a"


class DarkButton(tk.Canvas):
    """Custom rounded dark button."""

    def __init__(self, parent, text="", command=None, width=120, height=34,
                 bg=ACCENT, fg=FG, hover_bg=ACCENT_HOVER, **kwargs):
        super().__init__(parent, width=width, height=height,
                         bg=parent["bg"], highlightthickness=0, **kwargs)
        self.command = command
        self._bg = bg
        self._hover_bg = hover_bg
        self._fg = fg
        self._text = text
        self._w = width
        self._h = height
        self._draw(bg)
        self.bind("<Enter>", lambda e: self._draw(hover_bg))
        self.bind("<Leave>", lambda e: self._draw(bg))
        self.bind("<Button-1>", lambda e: self._on_click())

    def _draw(self, fill):
        self.delete("all")
        r = 8
        self.create_round_rect(2, 2, self._w - 2, self._h - 2, r, fill=fill, outline="")
        self.create_text(self._w // 2, self._h // 2, text=self._text,
                         fill=self._fg, font=("Segoe UI", 10, "bold"))

    def create_round_rect(self, x1, y1, x2, y2, r, **kwargs):
        points = [
            x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
            x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
            x1, y2, x1, y2 - r, x1, y1 + r, x1, y1,
        ]
        return self.create_polygon(points, smooth=True, **kwargs)

    def _on_click(self):
        if self.command:
            self.command()

    def set_text(self, text):
        self._text = text
        self._draw(self._bg)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Autoclicker v2")
        self.geometry("460x400")
        self.resizable(False, False)
        self.configure(bg=BG)

        self.clicker = AutoClicker()

        # -- Header --
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

        # -- Status --
        self.status_var = tk.StringVar(value="DISABLED")
        self.status_label = tk.Label(main, textvariable=self.status_var,
                                     font=("Segoe UI", 12, "bold"), bg=BG, fg=RED)
        self.status_label.pack(anchor="w", pady=(0, 8))

        # -- Click counter --
        self.count_var = tk.StringVar(value="Clicks: 0")
        tk.Label(main, textvariable=self.count_var, font=("Segoe UI", 9),
                 bg=BG, fg="#888").pack(anchor="w", pady=(0, 10))

        # -- Settings frame --
        settings = tk.LabelFrame(main, text=" Settings ", font=("Segoe UI", 9, "bold"),
                                 bg=BG_LIGHT, fg=FG, bd=1, relief=tk.GROOVE,
                                 padx=12, pady=8)
        settings.pack(fill=tk.X, pady=(0, 10))

        # CPS row
        cps_row = tk.Frame(settings, bg=BG_LIGHT)
        cps_row.pack(fill=tk.X, pady=4)
        tk.Label(cps_row, text="CPS (0.1-500):", font=("Segoe UI", 9),
                 bg=BG_LIGHT, fg=FG).pack(side=tk.LEFT)
        self.cps_var = tk.StringVar(value="10")
        self.cps_entry = tk.Entry(cps_row, textvariable=self.cps_var, width=8,
                                  bg=ENTRY_BG, fg=FG, insertbackground=FG,
                                  font=("Consolas", 10), bd=0, relief=tk.FLAT)
        self.cps_entry.pack(side=tk.LEFT, padx=(8, 8))
        DarkButton(cps_row, text="Apply", command=self.apply_cps,
                   width=70, height=28).pack(side=tk.LEFT)

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

        # -- Action buttons --
        action_row = tk.Frame(main, bg=BG)
        action_row.pack(fill=tk.X, pady=(4, 8))
        self.toggle_btn = DarkButton(action_row, text="ENABLE", command=self.on_toggle,
                                     width=140, height=38, bg="#006400", hover_bg=GREEN)
        self.toggle_btn.pack(side=tk.LEFT)
        DarkButton(action_row, text="QUIT", command=self.on_quit,
                   width=80, height=38, bg="#8b0000", hover_bg=RED).pack(side=tk.RIGHT)

        # -- Footer --
        tk.Label(main, text="Press F6 to toggle  |  Move mouse to corner = emergency stop",
                 font=("Segoe UI", 8), bg=BG, fg="#555").pack(anchor="w", pady=(4, 0))

        # Worker thread
        self.worker = threading.Thread(target=self.clicker.click_loop,
                                       kwargs={"on_tick": self.on_tick}, daemon=True)
        self.worker.start()

        # Global hotkey (F6)
        self.listener = keyboard.Listener(on_press=self.on_key_press)
        self.listener.daemon = True
        self.listener.start()

        pyautogui.FAILSAFE = True
        self.cps_entry.bind("<Return>", self.apply_cps)
        self.protocol("WM_DELETE_WINDOW", self.on_quit)

        # Periodic UI update for click counter
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
        with self.clicker.lock:
            count = self.clicker.click_count
        self.count_var.set(f"Clicks: {count:,}")
        self.after(100, self._update_counter)

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
                messagebox.showinfo("CPS", "Clamped to 0.1-500 range.")
        except ValueError:
            messagebox.showerror("Invalid", "Enter a number (0.1-500).")
            self.cps_var.set(f"{self.clicker.cps:.2f}".rstrip("0").rstrip("."))

    def on_key_press(self, key):
        try:
            if key == keyboard.Key.f6:
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
            self.toggle_btn._bg = "#8b0000"
            self.toggle_btn._hover_bg = RED
        else:
            self.toggle_btn._bg = "#006400"
            self.toggle_btn._hover_bg = GREEN
        self.toggle_btn._draw(self.toggle_btn._bg)

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
