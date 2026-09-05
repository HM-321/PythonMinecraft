import os
import hid
import struct
import threading
import time

# SDL2のHIDAPIジョイスティックドライバはmacOSで
# hid_report_callback内の二重解放によりクラッシュする既知の不具合があるため、
# 無効化して従来のIOKit直結の安定したドライバを使わせる。
# (pygame.joystick.init()より前、pygameのimportより前に設定する必要がある)
os.environ.setdefault('SDL_JOYSTICK_HIDAPI', '0')

try:
    import pygame
    import pygame._sdl2.controller as sdl_controller
except ImportError:
    pygame = None
    sdl_controller = None


class Controller:
    # Xbox系コントローラー(生HIDレポートを直接パースする専用ルート)
    VID = 0x45e
    PID = 0xb12

    # SDL(gamecontrollerdb)側のマッピング定義がXbox系と上下逆になっている機種。
    # コントローラー名(小文字)にこの文字列が含まれていたらY軸の符号を反転する。
    Y_INVERTED_CONTROLLER_NAMES = (
        'f710', 'f310', 'f510', 'rumblepad',
        'switch pro', 'pro controller', 'nintendo'
    )

    def __init__(self):
        self.connected = False
        self.state = None
        self.dev = None
        self.gc = None  # pygame._sdl2.controller.Controller
        self._invert_y = False

        self._prev_buttons = {}
        self._button_pressed_this_frame = {}

        self._prev_lt = False
        self._prev_rt = False
        self._lt_edge = False
        self._rt_edge = False
        self._state_lock = threading.Lock()

        self.deadzone_left = 0.15
        self.deadzone_right = 0.15

        self._pygame_ready = self._init_pygame_controller_subsystem()

        self._detect()

        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()

    def _init_pygame_controller_subsystem(self):
        if pygame is None or sdl_controller is None:
            return False
        try:
            if not pygame.joystick.get_init():
                pygame.joystick.init()
            if not sdl_controller.get_init():
                sdl_controller.init()
                # イベントキューには積まず、update()で都度状態だけ取りに行く
                sdl_controller.set_eventstate(False)
            return True
        except Exception as e:
            print(f'pygame controller init failed: {e}')
            return False

    def _detect(self):
        try:
            self.dev = hid.device()
            self.dev.open(self.VID, self.PID)
            self.dev.set_nonblocking(True)
            self.connected = True
            print(f'Controller: {self.dev.get_product_string()}')
        except Exception as e:
            print(f'No controller: {e}')
            self.dev = None
            self._detect_pygame()

    def _detect_pygame(self):
        if not self._pygame_ready:
            self.gc = None
            self.connected = False
            return
        try:
            # 新しく挿さった機器を拾うため、joystickサブシステムを再スキャンする
            pygame.joystick.quit()
            pygame.joystick.init()

            for index in range(pygame.joystick.get_count()):
                # pygame(SDL)内蔵のgamecontrollerdbにより、
                # Xbox / Logicool F710 / Switch Proコン等を
                # 個別のVID/PID指定なしに自動でボタン配置ごと認識できる。
                if sdl_controller.is_controller(index):
                    gc = sdl_controller.Controller(index)
                    self.gc = gc
                    self.connected = True
                    name = gc.name or ''
                    self._invert_y = any(
                        n in name.lower() for n in self.Y_INVERTED_CONTROLLER_NAMES
                    )
                    print(f'Controller: {name}')
                    return
        except Exception as e:
            print(f'No pygame controller: {e}')
        self.gc = None
        self._invert_y = False
        self.connected = False

    def is_connected(self):
        return self.connected

    def _read_loop(self):
        while True:
            if not self.connected:
                self._detect()
                if not self.connected:
                    time.sleep(1)
                    continue

            if self.gc:
                if not self.gc.attached():
                    print('Controller disconnected')
                    self.connected = False
                    self.gc = None
                    with self._state_lock:
                        self.state = None
                    continue
                time.sleep(0.01)
                continue

            try:
                data = self.dev.read(64)
                if data and len(data) >= 18 and data[0] == 0x20:
                    self._parse(data)
                elif not data:
                    time.sleep(0.001)
            except Exception as e:
                print(f'read error: {e}')
                self.connected = False
                with self._state_lock:
                    self.state = None
                try:
                    self.dev.close()
                except Exception:
                    pass

    def _parse(self, data):
        raw = bytes(data)
        b1 = data[4]
        b2 = data[5]
        state = {
            'A': bool(b1 & 0x10),
            'B': bool(b1 & 0x20),
            'X': bool(b1 & 0x40),
            'Y': bool(b1 & 0x80),
            'LB': bool(b2 & 0x10),
            'RB': bool(b2 & 0x20),
            'dpad_up': bool(b2 & 0x01),
            'dpad_down': bool(b2 & 0x02),
            'dpad_left': bool(b2 & 0x04),
            'dpad_right': bool(b2 & 0x08),
            'LT': struct.unpack_from('<H', raw, 6)[0],
            'RT': struct.unpack_from('<H', raw, 8)[0],
            'LX': struct.unpack_from('<h', raw, 10)[0] / 32767.0,
            'LY': struct.unpack_from('<h', raw, 12)[0] / 32767.0,
            'RX': struct.unpack_from('<h', raw, 14)[0] / 32767.0,
            'RY': struct.unpack_from('<h', raw, 16)[0] / 32767.0,
        }
        with self._state_lock:
            self.state = state

    def update(self):
        if self.gc:
            self._update_pygame()

        with self._state_lock:
            state = self.state.copy() if self.state else None
        if not state:
            return

        self._button_pressed_this_frame = {}
        for key in ('A', 'B', 'X', 'Y', 'LB', 'RB',
                    'dpad_up', 'dpad_down', 'dpad_left', 'dpad_right'):
            now = state.get(key, False)
            prev = self._prev_buttons.get(key, False)
            if now and not prev:
                self._button_pressed_this_frame[key] = True
            self._prev_buttons[key] = now

        THRESH = 500
        now_lt = state.get('LT', 0) > THRESH
        self._lt_edge = now_lt and not self._prev_lt
        self._prev_lt = now_lt

        now_rt = state.get('RT', 0) > THRESH
        self._rt_edge = now_rt and not self._prev_rt
        self._prev_rt = now_rt

    def _update_pygame(self):
        if not self.gc.attached():
            self.connected = False
            self.gc = None
            with self._state_lock:
                self.state = None
            return

        sdl_controller.update()

        y_sign = -1 if self._invert_y else 1

        def axis(axis_id):
            return self.gc.get_axis(axis_id) / 32767.0

        def axis_y(axis_id):
            return axis(axis_id) * y_sign

        def trigger(axis_id):
            # トリガーは0(離す)〜32767(全押し)。
            # 既存のTHRESH=500判定に合わせて元のXbox HIDスケール(0-1023)に正規化する。
            v = self.gc.get_axis(axis_id)
            return max(0, int(v / 32767.0 * 1023))

        def button(btn_id):
            return bool(self.gc.get_button(btn_id))

        state = {
            'A': button(pygame.CONTROLLER_BUTTON_A),
            'B': button(pygame.CONTROLLER_BUTTON_B),
            'X': button(pygame.CONTROLLER_BUTTON_X),
            'Y': button(pygame.CONTROLLER_BUTTON_Y),
            'LB': button(pygame.CONTROLLER_BUTTON_LEFTSHOULDER),
            'RB': button(pygame.CONTROLLER_BUTTON_RIGHTSHOULDER),
            'dpad_up': button(pygame.CONTROLLER_BUTTON_DPAD_UP),
            'dpad_down': button(pygame.CONTROLLER_BUTTON_DPAD_DOWN),
            'dpad_left': button(pygame.CONTROLLER_BUTTON_DPAD_LEFT),
            'dpad_right': button(pygame.CONTROLLER_BUTTON_DPAD_RIGHT),
            'LT': trigger(pygame.CONTROLLER_AXIS_TRIGGERLEFT),
            'RT': trigger(pygame.CONTROLLER_AXIS_TRIGGERRIGHT),
            'LX': axis(pygame.CONTROLLER_AXIS_LEFTX),
            'LY': axis_y(pygame.CONTROLLER_AXIS_LEFTY),
            'RX': axis(pygame.CONTROLLER_AXIS_RIGHTX),
            'RY': axis_y(pygame.CONTROLLER_AXIS_RIGHTY),
        }
        with self._state_lock:
            self.state = state

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
        return -self._apply_deadzone(self.state['LY'], self.deadzone_left)

    def look_x(self):
        if not self.state:
            return 0
        return self._apply_deadzone(self.state['RX'], self.deadzone_right)

    def look_y(self):
        if not self.state:
            return 0
        return -self._apply_deadzone(self.state['RY'], self.deadzone_right)

    def zl_just_pressed(self):
        return self._lt_edge

    def zr_just_pressed(self):
        return self._rt_edge

    def zl_held(self):
        if not self.state:
            return False
        return self.state.get('LT', 0) > 500

    def zr_held(self):
        if not self.state:
            return False
        return self.state.get('RT', 0) > 500