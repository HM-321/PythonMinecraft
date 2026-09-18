import os
import runpy
import sys
import traceback
import atexit
import subprocess
import time

from config import CRASH_LOG_PATH, ensure_data_dirs


_mac_caffeinate_process = None
_mac_last_activity = 0.0


def keep_macos_awake():
    """コントローラー操作中にmacOSのスクリーンセーバー移行を防ぐ。"""
    global _mac_caffeinate_process, _mac_last_activity
    if sys.platform != 'darwin':
        return

    now = time.monotonic()
    if now - _mac_last_activity < 30:
        return
    if _mac_caffeinate_process is not None:
        if _mac_caffeinate_process.poll() is None:
            return
        _mac_caffeinate_process = None
    try:
        _mac_caffeinate_process = subprocess.Popen(
            ['/usr/bin/caffeinate', '-u', '-t', '60'],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        _mac_last_activity = now
    except (OSError, subprocess.SubprocessError):
        _mac_caffeinate_process = None


def release_macos_awake():
    global _mac_caffeinate_process, _mac_last_activity
    if _mac_caffeinate_process is not None:
        try:
            _mac_caffeinate_process.terminate()
        except Exception:
            pass
    _mac_caffeinate_process = None
    _mac_last_activity = 0.0


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