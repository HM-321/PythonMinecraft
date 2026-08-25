from ursina import Entity, Text, Button, camera, color, destroy, mouse, window
from panda3d.core import WindowProperties


class PauseMenu:
    def __init__(self, on_resume, on_quit, app):
        self.on_resume = on_resume
        self.on_quit = on_quit
        self.app = app

        # カーソル表示
        props = WindowProperties()
        props.setCursorHidden(False)
        app.win.requestProperties(props)
        mouse.visible = True
        mouse.locked = False

        self.root = Entity(parent=camera.ui)

        # 半透明背景（全画面）
        Entity(parent=self.root, model='quad',
               color=color.rgba32(0, 0, 0, 200),
               scale=(window.aspect_ratio * 2 + 1, 2),
               z=0.5)

        Text(parent=self.root, text='PAUSED',
             origin=(0, 0), y=0.25, scale=3,
             color=color.white, z=-1)

        Button(parent=self.root, text='RESUME',
               y=0.05, scale=(0.25, 0.06),
               color=color.azure,
               on_click=self._resume, z=-1)

        Button(parent=self.root, text='OPTIONS',
               y=-0.04, scale=(0.25, 0.06),
               color=color.dark_gray,
               on_click=self._options, z=-1)

        Button(parent=self.root, text='SAVE & QUIT',
               y=-0.13, scale=(0.25, 0.06),
               color=color.red,
               on_click=self._quit, z=-1)
        
        import __main__
        if __main__.game.get('hotbar'):
            __main__.game['hotbar'].root.enabled = False
        if __main__.game.get('crosshair'):
            __main__.game['crosshair'].root.enabled = False
        if __main__.game.get('selection'):
            __main__.game['selection'].hide()


    def _resume(self):
        props = WindowProperties()
        props.setCursorHidden(True)
        props.setMouseMode(WindowProperties.M_relative)
        self.app.win.requestProperties(props)
        mouse.visible = False

        import __main__
        __main__.game['first_frame'] = True

        # UI 復元
        if __main__.game.get('hotbar'):
            __main__.game['hotbar'].root.enabled = True
        if __main__.game.get('crosshair'):
            __main__.game['crosshair'].root.enabled = True
        # selection は raycast側で自動制御されるので不要

        destroy(self.root)
        self.on_resume()

    def _options(self):
        destroy(self.root)
        from options import OptionsScreen
        OptionsScreen(on_back=self._reopen)

    def _reopen(self):
        import __main__
        if hasattr(__main__, 'game'):
            __main__.game['paused'] = True   # ← 追加
        new_menu = PauseMenu(self.on_resume, self.on_quit, self.app)
        if hasattr(__main__, 'game'):
            __main__.game['pause_menu'] = new_menu

    def _quit(self):
        destroy(self.root)
        self.on_quit()