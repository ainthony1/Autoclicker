# Autoclicker

A minimal Tkinter-based GUI autoclicker built around [`pyautogui`](https://pypi.org/project/pyautogui/) for mouse clicking and [`pynput`](https://pypi.org/project/pynput/) for global hotkey listening. Packaged with PyInstaller (see [main.spec](main.spec)).

## Features
- Start/stop clicking via GUI button or global hotkey.
- Adjustable clicks per second (CPS).
- Threaded click loop keeps UI responsive.
- Error handling: any exception during clicking disables the autoclicker and shows a message.
- Uses `pyautogui.FAILSAFE = True` (moving mouse to top-left aborts).

## Files
- [main.py](main.py): Application entry point; defines classes:
  - [`AutoClicker`](main.py): State management, timing, and click loop.
    - [`AutoClicker.set_cps`](main.py): Clamps CPS (currently 0.1–10000.0; UI label says 0.1–100).
    - [`AutoClicker.get_interval`](main.py)
    - [`AutoClicker.toggle`](main.py)
    - [`AutoClicker.is_enabled`](main.py)
    - [`AutoClicker.stop`](main.py)
    - [`AutoClicker.click_loop`](main.py)
  - [`App`](main.py): Tkinter GUI.
    - [`App.on_key_press`](main.py)
    - [`App.validate_cps`](main.py)
    - [`App.safe_toggle`](main.py)
    - [`App.on_toggle`](main.py)
    - [`App.update_status`](main.py)
    - [`App.on_tick`](main.py)
    - [`App.on_quit`](main.py)
- [main.spec](main.spec): PyInstaller build configuration (one-file windowed executable, no console).

Build artifacts reside under `build/` and are generated; they do not need to be committed.

## How It Works
1. GUI initializes an [`AutoClicker`](main.py) instance and starts:
   - A worker thread running [`AutoClicker.click_loop`](main.py).
   - A global keyboard listener (`pynput.keyboard.Listener`) invoking [`App.on_key_press`](main.py).
2. The click loop:
   - Checks `enabled` state via [`AutoClicker.is_enabled`](main.py).
   - Performs `pyautogui.click(button=self.click_button)` then sleeps for `1 / cps`.
   - Calls the UI callback `on_tick` every iteration; passes an error string if an exception occurs.
3. Toggling:
   - GUI button or hotkey calls [`AutoClicker.toggle`](main.py) and updates labels.
4. CPS input:
   - User edits the entry; on blur or Enter, [`App.validate_cps`](main.py) parses and normalizes it.
5. Shutdown:
   - [`App.on_quit`](main.py) stops the clicker and listener gracefully, then destroys the window.

## Hotkey
- Code currently checks for `keyboard.Key.f5` in [`App.on_key_press`](main.py) while all UI text labels say “F9”. This is a mismatch; change to `keyboard.Key.f9` for consistency.

## Usage
Install dependencies:
```sh
pip install pyautogui pynput
python main.py
```
Move mouse to a safe area before enabling. Adjust CPS, press Enable, or use the hotkey. Move mouse to top-left corner to trigger PyAutoGUI failsafe if needed.

## Building (PyInstaller)
```sh
pip install pyinstaller
pyinstaller main.spec
```
Output executable appears under `dist/`.

## Configuration / Extensibility
- Change `self.click_button` in [`AutoClicker.__init__`](main.py) or expose a GUI dropdown to allow right/middle clicks.
- Clamp range inconsistency: `set_cps` allows up to 10000.0 but label shows 0.1–100. Adjust one for clarity.
- Add random jitter by modifying [`AutoClicker.get_interval`](main.py) if desired.

## Threading Model
- Click loop runs in a daemon thread.
- Global listener runs in its own thread.
- All UI updates happen on the Tk main thread (callbacks are simple and lightweight).

## Error Handling
- Any exception in `pyautogui.click` disables clicking and shows a one-time error dialog via [`App.on_tick`](main.py).

## Safety / Responsible Use
Use only where automated clicking is permitted. Some applications or games may forbid automation.

## Known Issues
- Hotkey label vs implementation mismatch (F9 vs F5).
- CPS clamp comment says “0.1..100” but code clamps to 10000.0.
- Rapid dialog spam prevented by disabling on first click error, but long-running errors still trigger per loop iteration’s `on_tick()` (lightweight but unnecessary). Could gate calls when no state change.

## Possible Improvements
- Add start delay.
- Add per-button selection (left/right/middle).
- Add statistics (total clicks).
- Add system tray integration.
- Persist last CPS in a config file.

## License
Add an explicit license file (none present).
