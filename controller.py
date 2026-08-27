import glob
import os
import sys
import threading
import time


def _bootstrap_sdl2_dll_path():
    """
    pysdl2-dll はApple SiliconなどでSDL2のバイナリを持たない
    "source-only" 状態でインストールされてしまうことがあり、その場合
    pysdl2は無効になってしまう(pysdl2-dll is installed as
    source-only ... と警告が出る)。

    その場合でも、同じ環境の pygame が同梱している SDL2 の共有ライブラリ
    (pygame自体は正常に動いている = そのSDL2は読み込める実体)を
    PYSDL2_DLL_PATH として教えてやることで、pysdl2にも同じものを
    使わせることができる。
    """
    if os.environ.get('PYSDL2_DLL_PATH'):
        return
    try:
        import pygame
        pygame_dir = os.path.dirname(pygame.__file__)
    except Exception:
        return

    patterns = ['*SDL2*.dylib', '*SDL2*.so*', 'SDL2.dll', '*SDL2*.dll']
    for pattern in patterns:
        matches = glob.glob(os.path.join(pygame_dir, '**', pattern), recursive=True)
        if matches:
            os.environ['PYSDL2_DLL_PATH'] = os.path.dirname(matches[0])
            break


_bootstrap_sdl2_dll_path()

try:
    import sdl2
except Exception as _sdl2_import_error:  # ImportError以外(共有ライブラリ未検出時のRuntimeErrorなど)も捕捉
    _sdl2_import_error_msg = str(_sdl2_import_error)
    sdl2 = None
else:
    _sdl2_import_error_msg = None


def _log(msg):
    """コンソールが存在しないビルド(windowed/noconsole)でも例外を出さずに出力する"""
    try:
        print(msg)
    except Exception:
        pass


if _sdl2_import_error_msg:
    _log(f'sdl2 の読み込みに失敗しました。コントローラーは無効になります: {_sdl2_import_error_msg}')


class Controller:
    """
    SDL2 の GameController API を使ってコントローラーを扱うクラス。

    以前は特定のVID/PIDを直接指定してHIDレポートをバイト単位で解析する
    実装だったため、対応できる機種が実質1〜2種類に限られ、環境(USBポート
    やOS、機種)を変えると認識できなくなっていた。

    SDL2にはXbox系・PlayStation系・Nintendo Switch Pro・8BitDoなど
    多くの市販ゲームパッドのボタン配置を統一的に扱うためのマッピングDB
    (SDL_GameControllerDB)が内蔵されており、VID/PIDやレポート形式を
    こちらで意識しなくても「A/B/X/Y」「LB/RB」「十字キー」「スティック」
    「トリガー」という共通の名前で入力を取得できる。これによりケーブル
    接続・Bluetooth接続を問わず、多くのコントローラーで動作する。
    """

    # 実行ファイルと同じ場所に gamecontrollerdb.txt を置いておくと、
    # SDL標準DBに無い/古い機種のマッピングを追加で読み込める(任意)。
    EXTRA_MAPPINGS_FILENAME = 'gamecontrollerdb.txt'

    def __init__(self):
        self.connected = False
        self.state = None
        self.name = None

        self._ctrl = None
        self._sdl_ready = False

        self._prev_buttons = {}
        self._button_pressed_this_frame = {}

        self._prev_lt = False
        self._prev_rt = False
        self._lt_edge = False
        self._rt_edge = False
        self._state_lock = threading.Lock()

        self.deadzone_left = 0.15
        self.deadzone_right = 0.15

        self._init_sdl()
        self._detect()

        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()

    # ------------------------------------------------------------------
    # 初期化・検出
    # ------------------------------------------------------------------
    def _init_sdl(self):
        if sdl2 is None:
            _log('コントローラー機能を使うには pysdl2 が必要です '
                  '(pip install pysdl2 pysdl2-dll)')
            self._sdl_ready = False
            return
        try:
            sdl2.SDL_SetHint(sdl2.SDL_HINT_JOYSTICK_ALLOW_BACKGROUND_EVENTS, b'1')
            sdl2.SDL_Init(sdl2.SDL_INIT_GAMECONTROLLER | sdl2.SDL_INIT_JOYSTICK)
            self._sdl_ready = True
            self._load_extra_mappings()
        except Exception as e:
            _log(f'SDL init error: {e}')
            self._sdl_ready = False

    def _load_extra_mappings(self):
        """実行ファイルと同じフォルダに gamecontrollerdb.txt があれば読み込む"""
        try:
            base_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
            path = os.path.join(base_dir, self.EXTRA_MAPPINGS_FILENAME)
            if os.path.isfile(path):
                n = sdl2.SDL_GameControllerAddMappingsFromFile(path.encode('utf-8'))
                if n >= 0:
                    _log(f'コントローラーマッピングを追加読み込み: {n}件 ({path})')
        except Exception as e:
            _log(f'追加マッピング読み込みエラー: {e}')

    def _detect(self):
        if not self._sdl_ready:
            self.connected = False
            return
        try:
            sdl2.SDL_JoystickUpdate()
            for index in range(sdl2.SDL_NumJoysticks()):
                if not sdl2.SDL_IsGameController(index):
                    continue
                ctrl = sdl2.SDL_GameControllerOpen(index)
                if not ctrl:
                    continue
                self._ctrl = ctrl
                name = sdl2.SDL_GameControllerName(ctrl)
                self.name = name.decode('utf-8', 'ignore') if name else 'Unknown Controller'
                self.connected = True
                _log(f'Controller: {self.name}')
                return
        except Exception as e:
            _log(f'No controller: {e}')

        self._ctrl = None
        self.connected = False

    def is_connected(self):
        return self.connected

    @property
    def name_display(self):
        return self.name or 'Not connected'

    def _read_loop(self):
        # 未接続の間だけ、バックグラウンドで再検出を試み続ける。
        # (接続後の入力読み取りはメインスレッドの update() で行う)
        while True:
            if not self._sdl_ready:
                time.sleep(1)
                continue
            if self.connected:
                time.sleep(0.2)
                continue
            self._detect()
            if not self.connected:
                time.sleep(1)

    # ------------------------------------------------------------------
    # 毎フレーム更新
    # ------------------------------------------------------------------
    def update(self):
        if not self.connected or self._ctrl is None:
            return

        try:
            sdl2.SDL_GameControllerUpdate()
            if not sdl2.SDL_GameControllerGetAttached(self._ctrl):
                raise RuntimeError('controller detached')
            state = self._read_state()
        except Exception as e:
            _log(f'コントローラーが切断されました: {e}')
            self._disconnect()
            return

        with self._state_lock:
            self.state = state

        self._button_pressed_this_frame = {}
        for key in ('A', 'B', 'X', 'Y', 'LB', 'RB',
                    'dpad_up', 'dpad_down', 'dpad_left', 'dpad_right'):
            now = state.get(key, False)
            prev = self._prev_buttons.get(key, False)
            if now and not prev:
                self._button_pressed_this_frame[key] = True
            self._prev_buttons[key] = now

        THRESH = 0.5
        now_lt = state.get('LT', 0.0) > THRESH
        self._lt_edge = now_lt and not self._prev_lt
        self._prev_lt = now_lt

        now_rt = state.get('RT', 0.0) > THRESH
        self._rt_edge = now_rt and not self._prev_rt
        self._prev_rt = now_rt

    def _disconnect(self):
        try:
            if self._ctrl:
                sdl2.SDL_GameControllerClose(self._ctrl)
        except Exception:
            pass
        self._ctrl = None
        self.connected = False
        with self._state_lock:
            self.state = None

    def _read_state(self):
        c = self._ctrl

        def axis(a):
            return sdl2.SDL_GameControllerGetAxis(c, a) / 32767.0

        def button(b):
            return bool(sdl2.SDL_GameControllerGetButton(c, b))

        return {
            'A': button(sdl2.SDL_CONTROLLER_BUTTON_A),
            'B': button(sdl2.SDL_CONTROLLER_BUTTON_B),
            'X': button(sdl2.SDL_CONTROLLER_BUTTON_X),
            'Y': button(sdl2.SDL_CONTROLLER_BUTTON_Y),
            'LB': button(sdl2.SDL_CONTROLLER_BUTTON_LEFTSHOULDER),
            'RB': button(sdl2.SDL_CONTROLLER_BUTTON_RIGHTSHOULDER),
            'dpad_up': button(sdl2.SDL_CONTROLLER_BUTTON_DPAD_UP),
            'dpad_down': button(sdl2.SDL_CONTROLLER_BUTTON_DPAD_DOWN),
            'dpad_left': button(sdl2.SDL_CONTROLLER_BUTTON_DPAD_LEFT),
            'dpad_right': button(sdl2.SDL_CONTROLLER_BUTTON_DPAD_RIGHT),
            # トリガーは0.0(離す)〜1.0(全押し)に正規化
            'LT': max(0.0, axis(sdl2.SDL_CONTROLLER_AXIS_TRIGGERLEFT)),
            'RT': max(0.0, axis(sdl2.SDL_CONTROLLER_AXIS_TRIGGERRIGHT)),
            'LX': axis(sdl2.SDL_CONTROLLER_AXIS_LEFTX),
            'LY': axis(sdl2.SDL_CONTROLLER_AXIS_LEFTY),
            'RX': axis(sdl2.SDL_CONTROLLER_AXIS_RIGHTX),
            'RY': axis(sdl2.SDL_CONTROLLER_AXIS_RIGHTY),
        }

    # ------------------------------------------------------------------
    # 入力取得(以前と同じ公開API)
    # ------------------------------------------------------------------
    def button_held(self, key):
        if not self.state:
            return False
        return self.state.get(key, False)

    def button_pressed(self, key):
        return self._button_pressed_this_frame.get(key, False)

    def _apply_deadzone(self, v, dz):
        if abs(v) < dz:
            return 0
        sign = 1 if v > 0 else -1
        return sign * (abs(v) - dz) / (1 - dz)

    def move_x(self):
        if not self.state:
            return 0
        return self._apply_deadzone(self.state['LX'], self.deadzone_left)

    def move_y(self):
        if not self.state:
            return 0
        return self._apply_deadzone(self.state['LY'], self.deadzone_left)

    def look_x(self):
        if not self.state:
            return 0
        return self._apply_deadzone(self.state['RX'], self.deadzone_right)

    def look_y(self):
        if not self.state:
            return 0
        return self._apply_deadzone(self.state['RY'], self.deadzone_right)

    def zl_just_pressed(self):
        return self._lt_edge

    def zr_just_pressed(self):
        return self._rt_edge

    def zl_held(self):
        if not self.state:
            return False
        return self.state.get('LT', 0.0) > 0.5

    def zr_held(self):
        if not self.state:
            return False
        return self.state.get('RT', 0.0) > 0.5