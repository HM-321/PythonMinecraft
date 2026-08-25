import os
import runpy
import sys
import traceback

from config import CRASH_LOG_PATH, ensure_data_dirs


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