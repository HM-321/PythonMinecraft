from ursina import Entity, Text, Button, camera, color, destroy, mouse, window
from panda3d.core import WindowProperties


class PauseMenu:
    def __init__(
        self,
        on_resume,
        on_quit,
        app,
        on_open_lan=None,
        lan_status=None,
        on_lan_save=None,
        on_lan_reset=None,
        on_lan_stop=None,
    ):
        self.on_resume = on_resume
        self.on_quit = on_quit
        self.app = app
        self.on_open_lan = on_open_lan
        self.lan_status = lan_status
        self.on_lan_save = on_lan_save
        self.on_lan_reset = on_lan_reset
        self.on_lan_stop = on_lan_stop
        self.use_template = False
        self.root = None
        self._show_main()

        props = WindowProperties()
        props.setCursorHidden(False)
        app.win.requestProperties(props)
        mouse.visible = True
        mouse.locked = False

        import __main__
        if __main__.game.get('hotbar'):
            __main__.game['hotbar'].root.enabled = False
        if __main__.game.get('crosshair'):
            __main__.game['crosshair'].root.enabled = False
        if __main__.game.get('selection'):
            __main__.game['selection'].hide()

    def _new_root(self):
        if self.root is not None:
            destroy(self.root)
        self.root = Entity(parent=camera.ui)
        Entity(
            parent=self.root,
            model='quad',
            color=color.rgba(0, 0, 0, 200/255),
            scale=(window.aspect_ratio * 2 + 1, 2),
            z=0.5,
        )

    def _button(self, text, y, on_click, button_color):
        return Button(
            parent=self.root,
            text=text,
            y=y,
            scale=(0.28, 0.06),
            color=button_color,
            on_click=on_click,
            z=-1,
        )

    def _show_main(self):
        self._new_root()
        Text(
            parent=self.root,
            text='PAUSED',
            origin=(0, 0),
            y=0.27,
            scale=3,
            color=color.white,
            z=-1,
        )
        self._button('RESUME', 0.08, self._resume, color.azure)
        self._button('OPTIONS', -0.01, self._options, color.dark_gray)
        if self.on_open_lan is not None:
            self._button('OPEN TO LAN', -0.10, self._open_lan, color.green)
        elif self.lan_status is not None:
            self._button('LAN SETTINGS', -0.10, self._show_lan_settings, color.green)
        self._button('SAVE & QUIT', -0.19, self._quit, color.red)

    def _show_lan_settings(self):
        self._new_root()
        status = self.lan_status() if self.lan_status else {}
        Text(
            parent=self.root,
            text='LAN WORLD',
            origin=(0, 0),
            y=0.34,
            scale=2.4,
            color=color.white,
            z=-1,
        )
        details = (
            f"Address: {status.get('address', '-')}\n"
            f"Players: {status.get('players', 0)} / {status.get('max_players', 0)}\n"
            f"Seed: {status.get('seed', '-')}\n"
            f"Generator: {status.get('generator', '-')}"
        )
        Text(
            parent=self.root,
            text=details,
            origin=(0, 0),
            y=0.19,
            scale=1.15,
            line_height=1.25,
            color=color.white,
            z=-1,
        )
        self._button('SAVE NOW', -0.01, self._save_lan, color.azure)
        template_text = (
            'USE TEMPLATE: ON' if self.use_template
            else 'USE TEMPLATE: OFF'
        )
        self._button(
            template_text,
            -0.10,
            self._toggle_template,
            color.dark_gray,
        )
        self._button('RESET WORLD', -0.19, self._confirm_reset, color.orange)
        self._button('STOP LAN', -0.28, self._stop_lan, color.red)
        self._button('BACK', -0.37, self._show_main, color.dark_gray)

    def _show_message(self, title, body, back):
        self._new_root()
        Text(parent=self.root, text=title, origin=(0, 0), y=0.22,
             scale=2.2, color=color.white, z=-1)
        Text(parent=self.root, text=body, origin=(0, 0), y=0.08,
             scale=1.15, color=color.white, z=-1)
        self._button('BACK', -0.13, back, color.dark_gray)

    def _toggle_template(self):
        self.use_template = not self.use_template
        self._show_lan_settings()

    def _save_lan(self):
        if self.on_lan_save:
            self.on_lan_save()
        self._show_message('SAVED', 'The LAN world was saved.', self._show_lan_settings)

    def _confirm_reset(self):
        self._new_root()
        Text(parent=self.root, text='RESET WORLD?', origin=(0, 0), y=0.22,
             scale=2.2, color=color.white, z=-1)
        reset_kind = 'Template world' if self.use_template else 'Grassland world'
        Text(parent=self.root,
             text=(
                 f'{reset_kind} will be generated.\n'
                 'All buildings and changes will be removed.\n'
                 'A backup is created before reset.'
             ),
             origin=(0, 0), y=0.07, scale=1.05, color=color.white, z=-1)
        self._button('RESET', -0.10, self._reset_lan, color.red)
        self._button('CANCEL', -0.19, self._show_lan_settings, color.dark_gray)

    def _reset_lan(self):
        result = (
            self.on_lan_reset(self.use_template)
            if self.on_lan_reset else None
        )
        if result:
            body = (
                f"Generator: {result.get('generator', '-')}\n"
                f"Seed: {result.get('seed', '-')}"
            )
        else:
            body = 'The world was reset.'
        self._show_message(
            'WORLD RESET',
            body,
            self._show_lan_settings,
        )

    def _stop_lan(self):
        if self.on_lan_stop:
            self.on_lan_stop()

    def _open_lan(self):
        if self.on_open_lan is not None:
            self.on_open_lan()

    def _resume(self):
        props = WindowProperties()
        props.setCursorHidden(True)
        props.setMouseMode(WindowProperties.M_relative)
        self.app.win.requestProperties(props)
        mouse.visible = False
        import __main__
        __main__.game['first_frame'] = True
        if __main__.game.get('hotbar'):
            __main__.game['hotbar'].root.enabled = True
        if __main__.game.get('crosshair'):
            __main__.game['crosshair'].root.enabled = True
        destroy(self.root)
        self.on_resume()

    def _options(self):
        destroy(self.root)
        from options import OptionsScreen
        OptionsScreen(on_back=self._reopen)

    def _reopen(self):
        import __main__
        if hasattr(__main__, 'game'):
            __main__.game['paused'] = True
            __main__._open_pause_menu()

    def _quit(self):
        destroy(self.root)
        self.on_quit()
