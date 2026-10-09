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


def claim_desktop_instance():
    if sys.platform != 'win32':
        return True
    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
    kernel32.CreateMutexW.restype = wintypes.HANDLE
    global _desktop_mutex
    _desktop_mutex = kernel32.CreateMutexW(None, False, 'Local\\FDGCastDesktop')
    if not _desktop_mutex:
        raise ctypes.WinError(ctypes.get_last_error())
    if ctypes.get_last_error() != 183:  # ERROR_ALREADY_EXISTS
        return True
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle(_desktop_mutex)
    user32 = ctypes.windll.user32
    user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
    user32.FindWindowW.restype = wintypes.HWND
    user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    hwnd = user32.FindWindowW(None, WINDOW_TITLE)
    if hwnd:
        user32.ShowWindow(hwnd, 9)
        user32.SetForegroundWindow(hwnd)
    return False


def launch():
    if '--stream-self-check' in sys.argv:
        # CI runs this inside the frozen EXE, without credentials or networking.
        from forgecast.youtube_stream import proto, response_dict, quota_retry_seconds
        import grpc
        response = proto.LiveChatMessageListResponse(next_page_token='test-cursor')
        assert response_dict(response)['nextPageToken'] == 'test-cursor'
        assert quota_retry_seconds() > 0
        assert grpc.ssl_channel_credentials() is not None
        return
    if not claim_desktop_instance():
        return
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

