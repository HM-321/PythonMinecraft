import hid
import struct
import threading
import time

try:
    import sdl2
except ImportError:
    sdl2 = None


class Controller:
    VID = 0x45e
    PID = 0xb12
    LOGICOOL_VID = 0x46d
    LOGICOOL_PID = 0xc219

    def __init__(self):
        self.connected = False
        self.state = None
        self.dev = None
        self.sdl_joy = None

        self._prev_buttons = {}
        self._button_pressed_this_frame = {}

        self._prev_lt = False
        self._prev_rt = False
        self._lt_edge = False
        self._rt_edge = False
        self._state_lock = threading.Lock()

        self.deadzone_left = 0.15
        self.deadzone_right = 0.15

        self._detect()

        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()

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
            self._detect_sdl()

    def _detect_sdl(self):
        if sdl2 is None:
            self.sdl_joy = None
            self.connected = False
            return
        try:
            sdl2.SDL_Init(sdl2.SDL_INIT_JOYSTICK)
            for index in range(sdl2.SDL_NumJoysticks()):
                if (sdl2.SDL_JoystickGetDeviceVendor(index) == self.LOGICOOL_VID
                        and sdl2.SDL_JoystickGetDeviceProduct(index) == self.LOGICOOL_PID):
                    self.sdl_joy = sdl2.SDL_JoystickOpen(index)
                    if self.sdl_joy:
                        self.connected = True
                        print(f'Controller: {sdl2.SDL_JoystickName(self.sdl_joy).decode()}')
                        return
        except Exception as e:
            print(f'No SDL controller: {e}')
        self.sdl_joy = None
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

            if self.sdl_joy:
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
        if self.sdl_joy:
            self._update_sdl()

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

    def _update_sdl(self):
        sdl2.SDL_JoystickUpdate()
        axis_count = sdl2.SDL_JoystickNumAxes(self.sdl_joy)
        button_count = sdl2.SDL_JoystickNumButtons(self.sdl_joy)
        hat = sdl2.SDL_JoystickGetHat(self.sdl_joy, 0) if sdl2.SDL_JoystickNumHats(self.sdl_joy) else 0

        def axis(index):
            if index >= axis_count:
                return 0
            return sdl2.SDL_JoystickGetAxis(self.sdl_joy, index) / 32767.0

        def button(index):
            return bool(index < button_count and sdl2.SDL_JoystickGetButton(self.sdl_joy, index))

        state = {
            'A': button(0),
            'B': button(1),
            'X': button(2),
            'Y': button(3),
            'LB': button(4),
            'RB': button(5),
            'dpad_up': bool(hat & sdl2.SDL_HAT_UP),
            'dpad_down': bool(hat & sdl2.SDL_HAT_DOWN),
            'dpad_left': bool(hat & sdl2.SDL_HAT_LEFT),
            'dpad_right': bool(hat & sdl2.SDL_HAT_RIGHT),
            'LT': 0,
            'RT': 0,
            'LX': axis(0),
            'LY': axis(1),
            'RX': axis(2),
            'RY': axis(3),
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