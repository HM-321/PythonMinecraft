from ursina import Entity, Text, Button, camera, color, destroy, window, mouse
from panda3d.core import WindowProperties


class TitleScreen:
    def __init__(self, on_start):
        self.on_start = on_start

        # カーソル表示
        import __main__
        props = WindowProperties()
        props.setCursorHidden(False)
        __main__.app.win.requestProperties(props)
        mouse.visible = True

        self.root = Entity(parent=camera.ui)
        self.root.input = self._input

        # 背景
        Entity(parent=self.root, model='quad',
               color=color.rgb(30, 60, 100),
               scale=(2 * window.aspect_ratio, 1.5),
               z=1)

        # タイトル
        Text(parent=self.root, text='ミネ CRAFT',
             origin=(0, 0), y=0.25, scale=5, color=color.white)

        Text(parent=self.root, text='Python + Ursina',
             origin=(0, 0), y=0.13, scale=1.2, color=color.light_gray)

        Text(parent=self.root,
             text=('WASD:移動  Space:ジャンプ/上昇  Shift:スニーク/下降\n'
                   'マウス左:破壊  右:設置  ホイール:切替  :デバッグ\n'
                   'Space2連打:飛行切替  Esc:ポーズ  P:スクショ'),
             origin=(0, 0), y=-0.02, scale=0.9, color=color.light_gray)

        Button(parent=self.root, text='START',
               y=-0.18, scale=(0.2, 0.06),
               color=color.azure,
               on_click=self._start)

        Button(parent=self.root, text='OPTIONS',
               y=-0.27, scale=(0.2, 0.06),
               color=color.dark_gray,
               on_click=self._options)

        Text(parent=self.root, text='v1.0',
             origin=(0, 0), y=-0.45, scale=0.7, color=color.gray)

    def _input(self, key):
        # タイトル画面ではEscで何もしない
        pass

    def _start(self):
        destroy(self.root)
        self.on_start()

    def _options(self):
        destroy(self.root)
        from options import OptionsScreen
        OptionsScreen(on_back=self._reopen_title)

    def _reopen_title(self):
        TitleScreen(on_start=self.on_start)

    def close(self):
        destroy(self.root)
