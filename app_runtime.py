import os
import runpy
import sys
import traceback
import atexit
import ctypes
import time

from config import CRASH_LOG_PATH, ensure_data_dirs


_mac_idle_assertion = None
_mac_last_activity = 0.0
_mac_iokit = None
_mac_core_graphics = None
_mac_core_foundation = None


def keep_macos_awake():
    """コントローラー操作中にmacOSのスクリーンセーバー移行を防ぐ。"""
    global _mac_idle_assertion, _mac_last_activity
    if sys.platform != 'darwin':
        return

    now = time.monotonic()
    try:
        if _mac_idle_assertion is None:
            _load_macos_frameworks()
            assertion_type = _mac_core_foundation.CFStringCreateWithCString(
                None,
                b'PreventUserIdleDisplaySleep',
                0x08000100,
            )
            assertion_name = _mac_core_foundation.CFStringCreateWithCString(
                None,
                b'PythonMinecraft controller activity',
                0x08000100,
            )
            assertion_id = ctypes.c_uint32()
            result = _mac_iokit.IOPMAssertionCreateWithName(
                assertion_type,
                255,
                assertion_name,
                ctypes.byref(assertion_id),
            )
            _mac_core_foundation.CFRelease(assertion_type)
            _mac_core_foundation.CFRelease(assertion_name)
            if result != 0:
                return
            _mac_idle_assertion = assertion_id.value

        if now - _mac_last_activity >= 30:
            event = _mac_core_graphics.CGEventCreate(None)
            if event:
                _mac_core_graphics.CGEventPost(0, event)
                _mac_core_foundation.CFRelease(event)
            _mac_last_activity = now
    except Exception:
        release_macos_awake()


def release_macos_awake():
    global _mac_idle_assertion, _mac_last_activity
    if _mac_idle_assertion is not None and _mac_iokit is not None:
        try:
            _mac_iokit.IOPMAssertionRelease(_mac_idle_assertion)
        except Exception:
            pass
    _mac_idle_assertion = None
    _mac_last_activity = 0.0


def _load_macos_frameworks():
    global _mac_iokit, _mac_core_graphics, _mac_core_foundation
    if _mac_iokit is not None:
        return
    _mac_iokit = ctypes.CDLL('/System/Library/Frameworks/IOKit.framework/IOKit')
    _mac_core_graphics = ctypes.CDLL(
        '/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics'
    )
    _mac_core_foundation = ctypes.CDLL(
        '/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation'
    )
    _mac_core_foundation.CFStringCreateWithCString.restype = ctypes.c_void_p
    _mac_core_foundation.CFStringCreateWithCString.argtypes = [
        ctypes.c_void_p, ctypes.c_char_p, ctypes.c_uint32
    ]
    _mac_core_foundation.CFRelease.argtypes = [ctypes.c_void_p]
    _mac_iokit.IOPMAssertionCreateWithName.argtypes = [
        ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_uint32)
    ]
    _mac_iokit.IOPMAssertionCreateWithName.restype = ctypes.c_int
    _mac_iokit.IOPMAssertionRelease.argtypes = [ctypes.c_uint32]
    _mac_iokit.IOPMAssertionRelease.restype = ctypes.c_int
    _mac_core_graphics.CGEventCreate.restype = ctypes.c_void_p
    _mac_core_graphics.CGEventCreate.argtypes = [ctypes.c_void_p]
    _mac_core_graphics.CGEventPost.argtypes = [ctypes.c_uint32, ctypes.c_void_p]


atexit.register(release_macos_awake)


def write_crash_log(exc_type, exc_value, exc_traceback):
    ensure_data_dirs()
    with open(CRASH_LOG_PATH, 'a') as log_file:
        log_file.write('\n=== MinecraftBuild crash ===\n')
        traceback.print_exception(exc_type, exc_value, exc_traceback, file=log_file)


def install_crash_logging():
    def _hook(exc_type, exc_value, exc_traceback):
        write_crash_log(exc_type, exc_value, exc_traceback)
        sys.__excepthook__(exc_type, exc_value, exc_traceback)

    sys.excepthook = _hook


def run_main():
    install_crash_logging()
    runpy.run_module('main', run_name='__main__')


if __name__ == '__main__':
    os.environ.setdefault('PYTHONUNBUFFERED', '1')
    run_main()