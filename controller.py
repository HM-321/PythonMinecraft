import os
os.environ['SDL_JOYSTICK_HIDAPI_SWITCH'] = '1'

import pygame


class Controller:
    # Switch Proコン ボタン番号（実測）
    BTN_A = 0
    BTN_B = 1
    BTN_X = 2
    BTN_Y = 3
    BTN_L = 9
    BTN_R = 10
    BTN_MINUS = 4       # 実測で確認して修正
    BTN_PLUS = 6        # 実測で確認して修正
    BTN_LSTICK = 7      # 実測で確認して修正
    BTN_RSTICK = 8      # 実測で確認して修正

    # ZL/ZR はaxis
    AXIS_ZL = 4         # 実測で確認して修正
    AXIS_ZR = 5         # 実測で確認して修正

    HAT_UP = (0, 1)
    HAT_DOWN = (0, -1)
    HAT_LEFT = (-1, 0)
    HAT_RIGHT = (1, 0)

    def __init__(self):
        if not pygame.get_init():
            pygame.init()
        pygame.joystick.init()

        self.joy = None
        self.deadzones = {
            0: 0.5,
            1: 0.5,
            2: 0.5,
            3: 0.5,
        }
        self.axis_offsets = {}

        self._prev_buttons = {}
        self._prev_hat = (0, 0)
        self._button_pressed_this_frame = {}
        self._hat_pressed_this_frame = None

        self._prev_zl = False
        self._prev_zr = False
        self._zl_edge = False
        self._zr_edge = False

        self._detect()

    def _detect(self):
        if pygame.joystick.get_count() > 0:
            self.joy = pygame.joystick.Joystick(0)
            self.joy.init()
            print(f'Controller: {self.joy.get_name()}')
            print(f'Buttons: {self.joy.get_numbuttons()}')
            print(f'Axes: {self.joy.get_numaxes()}')
            print(f'Hats: {self.joy.get_numhats()}')
        else:
            print('No controller')

    def is_connected(self):
        return self.joy is not None

    def calibrate(self):
        if not self.joy:
            return
        pygame.event.pump()
        for i in range(self.joy.get_numaxes()):
            self.axis_offsets[i] = self.joy.get_axis(i)
        print(f'calibrated: {self.axis_offsets}')

    def update(self):
        try:
            pygame.event.pump()
        except pygame.error:
            return

        self._button_pressed_this_frame = {}
        self._hat_pressed_this_frame = None

        if not self.joy:
            return

        # ボタンのエッジ検出
        for i in range(self.joy.get_numbuttons()):
            now = self.joy.get_button(i) == 1
            prev = self._prev_buttons.get(i, False)
            if now and not prev:
                self._button_pressed_this_frame[i] = True
            self._prev_buttons[i] = now

        # 十字キーのエッジ検出
        if self.joy.get_numhats() > 0:
            now_hat = self.joy.get_hat(0)
            if now_hat != self._prev_hat and now_hat != (0, 0):
                self._hat_pressed_this_frame = now_hat
            self._prev_hat = now_hat

        # ZL/ZR エッジ検出
        now_zl = self._zl_held()
        self._zl_edge = now_zl and not self._prev_zl
        self._prev_zl = now_zl

        now_zr = self._zr_held()
        self._zr_edge = now_zr and not self._prev_zr
        self._prev_zr = now_zr

    def _axis(self, i):
        if not self.joy or i >= self.joy.get_numaxes():
            return 0
        raw = self.joy.get_axis(i)
        offset = self.axis_offsets.get(i, 0)
        v = raw - offset
        dz = self.deadzones.get(i, 0.2)
        if abs(v) < dz:
            return 0
        sign = 1 if v > 0 else -1
        v = sign * (abs(v) - dz) / (1 - dz)
        return max(-1, min(1, v))

    def move_x(self):
        return self._axis(0)

    def move_y(self):
        return self._axis(1)

    def look_x(self):
        return self._axis(2)

    def look_y(self):
        return self._axis(3)

    def button_held(self, i):
        if not self.joy or i >= self.joy.get_numbuttons():
            return False
        return self.joy.get_button(i) == 1

    def button_pressed(self, i):
        return self._button_pressed_this_frame.get(i, False)

    def hat_pressed(self, direction):
        return self._hat_pressed_this_frame == direction

    def get_hat(self):
        if not self.joy or self.joy.get_numhats() == 0:
            return (0, 0)
        return self.joy.get_hat(0)

    def _zl_held(self):
        if not self.joy or self.AXIS_ZL >= self.joy.get_numaxes():
            return False
        return self.joy.get_axis(self.AXIS_ZL) > 0.5

    def _zr_held(self):
        if not self.joy or self.AXIS_ZR >= self.joy.get_numaxes():
            return False
        return self.joy.get_axis(self.AXIS_ZR) > 0.5

    def zl_just_pressed(self):
        return self._zl_edge

    def zr_just_pressed(self):
        return self._zr_edge

    def zl_held(self):
        return self._zl_held()

    def zr_held(self):
        return self._zr_held()