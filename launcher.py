"""Windows desktop entrypoint: keep the local bridge behind an FDGCast window."""
import ctypes
from ctypes import wintypes
from pathlib import Path
import queue
import sys
import threading
import time
from urllib.request import urlopen

from forgecast.server import main


WINDOW_TITLE = 'FDGCast · Forged Destiny Gaming'


def set_windows_identity():
    """Give the packaged window a stable taskbar identity across launches."""
    if sys.platform == 'win32':
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('ForgedDestinyGaming.FDGCast')


def apply_window_icon():
    """Apply the same icon to the window caption, Alt+Tab and taskbar."""
    if sys.platform != 'win32':
        return
    root = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
    icon_file = root / 'packaging' / 'FDGCast.ico'
    if not icon_file.exists():
        return
    user32 = ctypes.windll.user32
    user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
    user32.FindWindowW.restype = wintypes.HWND
    user32.LoadImageW.argtypes = [wintypes.HINSTANCE, wintypes.LPCWSTR, wintypes.UINT,
                                 ctypes.c_int, ctypes.c_int, wintypes.UINT]
    user32.LoadImageW.restype = wintypes.HANDLE
    user32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    user32.SendMessageW.restype = wintypes.LPARAM
    for _ in range(40):
        hwnd = user32.FindWindowW(None, WINDOW_TITLE)
        if hwnd:
            # Keep the loaded icon handles alive for the lifetime of this process.
            load_from_file = 0x10
            for size, slot in ((32, 1), (16, 0)):
                handle = user32.LoadImageW(None, str(icon_file), 1, size, size, load_from_file)
                if handle:
                    user32.SendMessageW(hwnd, 0x80, slot, handle)
            return
        time.sleep(0.25)


def launch():
    set_windows_identity()
    if '--headless' in sys.argv:
        sys.argv = [sys.argv[0], '--no-browser']
        main()
        return

    ready = queue.Queue(maxsize=1)
    original_argv = sys.argv

    def serve():
        sys.argv = [original_argv[0], '--no-browser']
        try:
            main(on_ready=ready.put)
        except Exception as exc:
            if ready.empty():
                ready.put(exc)

    threading.Thread(target=serve, name='FDGCast bridge', daemon=True).start()
    try:
        result = ready.get(timeout=15)
        if isinstance(result, Exception):
            raise result
        # The startup callback precedes aiohttp's listening stage.
        for _ in range(60):
            try:
                with urlopen('http://127.0.0.1:17654/', timeout=1) as response:
                    if response.status == 200:
                        break
            except OSError:
                time.sleep(0.2)
        else:
            raise RuntimeError('The local FDGCast service did not start.')
        import webview
        webview.create_window(WINDOW_TITLE, result,
                              width=1200, height=800, min_size=(760, 520),
                              background_color='#151719')
        webview.start(apply_window_icon, gui='edgechromium')
    except Exception as exc:
        if sys.platform == 'win32':
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, str(exc), 'FDGCast could not start', 0x10)
        else:
            raise


if __name__ == '__main__':
    launch()
