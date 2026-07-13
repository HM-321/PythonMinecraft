import hid
import struct
import threading


class Controller:
    VID = 0x45e
    PID = 0xb12

    def __init__(self):
        self.connected = False
        self.state = None
        self.dev = None

        self._prev_buttons = {}
        self._button_pressed_this_frame = {}

        self._prev_lt = False
        self._prev_rt = False
        self._lt_edge = False
        self._rt_edge = False

        self.deadzone_left = 0.15
        self.deadzone_right = 0.15

        self._detect()

        if self.connected:
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

    def is_connected(self):
        return self.connected

    def _read_loop(self):
        while self.connected:
            try:
                data = self.dev.read(64)
                if data and len(data) >= 18 and data[0] == 0x20:
                    self._parse(data)
            except Exception as e:
                print(f'read error: {e}')
                self.connected = False
                break

    def _parse(self, data):
        raw = bytes(data)
        b1 = data[4]
        b2 = data[5]
        self.state = {
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

    def update(self):
        if not self.state:
            return

        self._button_pressed_this_frame = {}
        for key in ('A', 'B', 'X', 'Y', 'LB', 'RB',
                    'dpad_up', 'dpad_down', 'dpad_left', 'dpad_right'):
            now = self.state.get(key, False)
            prev = self._prev_buttons.get(key, False)
            if now and not prev:
                self._button_pressed_this_frame[key] = True
            self._prev_buttons[key] = now

        THRESH = 500
        now_lt = self.state.get('LT', 0) > THRESH
        self._lt_edge = now_lt and not self._prev_lt
        self._prev_lt = now_lt

        now_rt = self.state.get('RT', 0) > THRESH
        self._rt_edge = now_rt and not self._prev_rt
        self._prev_rt = now_rt

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