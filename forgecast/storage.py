"""Local metadata plus Windows DPAPI secrets. No plaintext credential fallback."""
import base64
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path


def data_directory():
    return Path(os.environ.get('LOCALAPPDATA', str(Path.home()/'.local/share'))) / 'ForgeCast'


def atomic_json(path, data):
    path = Path(path)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(data, indent=2), encoding='utf-8')
    if os.name != 'nt':
        tmp.chmod(0o600)
    tmp.replace(path)


class Vault:
    def __init__(self, directory, memory=False):
        self.path = Path(directory)/'secrets.dpapi.json'
        self.memory = memory or os.name != 'nt'
        self.values = {} if self.memory or not self.path.exists() else json.loads(self.path.read_text())

    def crypt(self, data, protect):
        class Blob(ctypes.Structure):
            _fields_ = [('cbData', wintypes.DWORD), ('pbData', ctypes.POINTER(ctypes.c_ubyte))]
        buf = ctypes.create_string_buffer(data)
        src = Blob(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_ubyte)))
        dst = Blob()
        function = ctypes.windll.crypt32.CryptProtectData if protect else ctypes.windll.crypt32.CryptUnprotectData
        function.restype = wintypes.BOOL
        ctypes.windll.kernel32.LocalFree.argtypes = [ctypes.c_void_p]
        ctypes.windll.kernel32.LocalFree.restype = ctypes.c_void_p
        if not function(ctypes.byref(src), None, None, None, None, 1, ctypes.byref(dst)):
            raise RuntimeError('Windows credential encryption failed; nothing was saved.')
        try:
            return ctypes.string_at(dst.pbData, dst.cbData)
        finally:
            ctypes.windll.kernel32.LocalFree(dst.pbData)

    def get(self, key):
        raw = self.values.get(key, '')
        return raw if self.memory or not raw else self.crypt(base64.b64decode(raw), False).decode()

    def set(self, key, value):
        self.values[key] = value if self.memory else base64.b64encode(self.crypt(value.encode(), True)).decode()
        if not self.memory:
            atomic_json(self.path, self.values)

    def delete(self, key):
        self.values.pop(key, None)
        if not self.memory:
            atomic_json(self.path, self.values)
