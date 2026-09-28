"""Windows desktop entrypoint: keep the local bridge behind a ForgeCast window."""
import queue
import sys
import threading
import time
from urllib.request import urlopen

from forgecast.server import main


def launch():
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

    threading.Thread(target=serve, name='ForgeCast bridge', daemon=True).start()
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
            raise RuntimeError('The local ForgeCast service did not start.')
        import webview
        webview.create_window('ForgeCast · Forged Destiny Gaming', result,
                              width=1200, height=800, min_size=(760, 520),
                              background_color='#151719')
        webview.start(gui='edgechromium')
    except Exception as exc:
        if sys.platform == 'win32':
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, str(exc), 'ForgeCast could not start', 0x10)
        else:
            raise


if __name__ == '__main__':
    launch()
