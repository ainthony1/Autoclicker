"""
Autoclicker — F4 toggle, CPS (0.1–500) or MAX mode

Deps:
  pip install pyautogui pynput

Notes:
- MAX mode: no intentional sleeps; clicks as fast as possible (CPU heavy).
- CPS mode: precise 0.1–500 CPS with high-res scheduling + brief busy-wait.
"""

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

# Remove PyAutoGUI's built-in throttles (critical to exceed ~10 CPS)
pyautogui.PAUSE = 0.0
for attr in ("MINIMUM_SLEEP", "MINIMUM_DURATION"):
    if hasattr(pyautogui, attr):
        setattr(pyautogui, attr, 0.0)
if hasattr(pyautogui, "DARWIN_CATCH_UP_TIME"):
    pyautogui.DARWIN_CATCH_UP_TIME = 0


def sleep_until(target_time: float):
    """
    Sleep efficiently until target_time using coarse sleep, then a short busy-wait.
    This helps achieve high CPS despite OS timer granularity limits.
    """
    while True:
        now = time.perf_counter()
        remaining = target_time - now
        if remaining <= 0:
            return
        # Coarse sleep when there is comfortable margin
        if remaining > 0.002:  # >2 ms remaining
            time.sleep(remaining - 0.001)  # leave ~1 ms for final spin
        else:
            # Final busy-wait for sub-ms precision
            while time.perf_counter() < target_time:
                pass
            return


class AutoClicker:
    def __init__(self):
        self.enabled = False
        self.stop_event = threading.Event()
        self.lock = threading.Lock()
        self.click_button = 'left'
        self.cps = 10.0        # active CPS for CPS mode
        self.max_mode = False  # fast-as-possible mode

    def set_cps(self, cps: float):
        with self.lock:
            # Clamp to 0.1..500.0
            self.cps = max(0.1, min(500.0, float(cps)))

    def set_max_mode(self, enabled: bool):
        with self.lock:
            self.max_mode = bool(enabled)

    def get_interval(self) -> float:
        with self.lock:
            cps = self.cps
        return 1.0 / cps

    def toggle(self):
        with self.lock:
            self.enabled = not self.enabled
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

    def click_loop(self, on_tick=None):
        """
        Worker thread: in MAX mode, clicks in a tight loop (no intentional sleeps).
        In CPS mode, uses a high-res schedule with brief busy-wait for precision.
        """
        while not self.stop_event.is_set():
            if not self.is_enabled():
                time.sleep(0.02)  # tiny idle while disabled
                if on_tick:
                    on_tick()
                continue

            if self.is_max_mode():
                # Tight loop: click as fast as possible (CPU intensive).
                try:
                    while self.is_enabled() and not self.stop_event.is_set() and self.is_max_mode():
                        pyautogui.click(button=self.click_button)
                        # intentionally no sleep
                except Exception as e:
                    with self.lock:
                        self.enabled = False
                    if on_tick:
                        on_tick(error=str(e))
            else:
                # CPS mode with precise scheduling
                interval = self.get_interval()
                next_time = time.perf_counter()
                try:
                    while self.is_enabled() and not self.stop_event.is_set() and not self.is_max_mode():
                        pyautogui.click(button=self.click_button)
                        next_time += interval
                        # Sleep efficiently until the exact next_time
                        sleep_until(next_time)
                except Exception as e:
                    with self.lock:
                        self.enabled = False
                    if on_tick:
                        on_tick(error=str(e))

            if on_tick:
                on_tick()


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Autoclicker — F4 to Toggle")
        self.geometry("440x270")
        self.resizable(False, False)

        self.clicker = AutoClicker()

        # UI state
        self.status_var = tk.StringVar(value="Status: Disabled (press F4 or click Enable)")
        self.cps_var = tk.StringVar(value=f"{self.clicker.cps}")
        self.max_mode_var = tk.BooleanVar(value=False)

        pad = 10
        frm = ttk.Frame(self, padding=pad)
        frm.pack(fill=tk.BOTH, expand=True)

        # Status
        ttk.Label(frm, textvariable=self.status_var, font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(0, pad))

        # Mode row
        mode_row = ttk.Frame(frm)
        mode_row.pack(fill=tk.X, pady=(0, 6))
        self.max_chk = ttk.Checkbutton(
            mode_row,
            text="MAX mode (no delays; fastest possible)",
            variable=self.max_mode_var,
            command=self.on_toggle_max_mode
        )
        self.max_chk.pack(side=tk.LEFT)

        # CPS row
        cps_row = ttk.Frame(frm)
        cps_row.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(cps_row, text="Clicks per second (0.1–500):").pack(side=tk.LEFT)
        self.cps_entry = ttk.Entry(cps_row, textvariable=self.cps_var, width=10)
        self.cps_entry.pack(side=tk.LEFT, padx=(6, 8))
        self.apply_btn = ttk.Button(cps_row, text="Apply CPS", command=self.apply_cps)
        self.apply_btn.pack(side=tk.LEFT)

        # Buttons
        btn_row = ttk.Frame(frm)
        btn_row.pack(fill=tk.X, pady=(6, pad))
        self.toggle_btn = ttk.Button(btn_row, text="Enable", command=self.on_toggle)
        self.toggle_btn.pack(side=tk.LEFT)
        ttk.Button(btn_row, text="Quit", command=self.on_quit).pack(side=tk.RIGHT)

        ttk.Label(
            frm,
            text="Hotkey: F4 toggles on/off\nTip: Move mouse to a safe area before enabling.",
            foreground="#555"
        ).pack(anchor="w")

        # Worker thread
        self.worker = threading.Thread(target=self.clicker.click_loop, kwargs={"on_tick": self.on_tick}, daemon=True)
        self.worker.start()

        # Global hotkey listener (F4)
        self.listener = keyboard.Listener(on_press=self.on_key_press)
        self.listener.daemon = True
        self.listener.start()

        # Styling (optional)
        try:
            self.style = ttk.Style(self)
            if 'vista' in self.style.theme_names():
                self.style.theme_use('vista')
        except Exception:
            pass

        # PyAutoGUI failsafe: move mouse to top-left corner to abort
        pyautogui.FAILSAFE = True

        # Enter key applies CPS
        self.cps_entry.bind("<Return>", self.apply_cps)
        self.protocol("WM_DELETE_WINDOW", self.on_quit)

    def on_key_press(self, key):
        try:
            if key == keyboard.Key.f4:
                self.safe_toggle()
        except Exception:
            pass

    def on_toggle_max_mode(self):
        self.clicker.set_max_mode(self.max_mode_var.get())
        self.update_status(self.clicker.is_enabled())

    def apply_cps(self, event=None):
        if self.max_mode_var.get():
            messagebox.showinfo("MAX mode active", "Disable MAX mode to set a CPS limit.")
            return
        raw = self.cps_var.get().strip()
        try:
            val = float(raw)
            before = val
            self.clicker.set_cps(val)
            # normalize text to actual clamped value
            self.cps_var.set(f"{self.clicker.cps:.2f}".rstrip('0').rstrip('.'))
            if before != self.clicker.cps:
                messagebox.showinfo("CPS adjusted", "CPS was clamped to the 0.1–500 range.")
        except ValueError:
            messagebox.showerror("Invalid input", "Please enter a number for CPS (0.1–500).")
            self.cps_var.set(f"{self.clicker.cps:.2f}".rstrip('0').rstrip('.'))

        self.update_status(self.clicker.is_enabled())

    def safe_toggle(self):
        now_enabled = self.clicker.toggle()
        self.update_status(now_enabled)

    def on_toggle(self):
        self.safe_toggle()

    def update_status(self, enabled: bool):
        self.toggle_btn.config(text="Disable" if enabled else "Enable")
        mode = "MAX" if self.max_mode_var.get() else f"{self.cps_var.get()} CPS"
        self.status_var.set(f"Status: {'Enabled' if enabled else 'Disabled'} (F4 to toggle) — Mode: {mode}")

    def on_tick(self, error: str | None = None):
        if error:
            messagebox.showerror("Autoclick error", f"Clicking stopped due to error:\n{error}")
            self.update_status(False)

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
