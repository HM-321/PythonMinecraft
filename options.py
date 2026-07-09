from ursina import Entity, Text, Button, camera, color, destroy, Slider
from settings import settings


sound_mgr = None


class OptionsScreen:
    def __init__(self, on_back):
        self.on_back = on_back
        self.root = Entity(parent=camera.ui)
        self.root.input = self._input

        self.pending = {}
        self._capturing_key = None
        self._capturing_btn = None



        # 背景
        Entity(parent=self.root, model='quad',
               color=color.rgb(20, 40, 70),
               scale=(3, 1.8),
               z=1)

        Text(parent=self.root, text='OPTIONS',
             origin=(0, 0), y=0.42, scale=2.5, color=color.white)

        self.sliders = {}
        step = 0.08

        # 左列: スライダー
        y = 0.28
        self._make_slider('Sensitivity', 'sensitivity', 0.05, 0.5, y, x_offset=-0.35)
        y -= step
        self._make_slider('FOV', 'fov', 60, 110, y, x_offset=-0.35)
        y -= step
        self._make_slider('Render Dist', 'render_distance', 10, 40, y, x_offset=-0.35)
        y -= step
        self._make_slider('BGM Vol', 'bgm_volume', 0.0, 1.0, y, x_offset=-0.35)
        y -= step
        self._make_slider('SE Vol', 'se_volume', 0.0, 1.0, y, x_offset=-0.35)
        y -= step
        self._make_slider('Max FPS', 'max_fps', 20, 120, y, x_offset=-0.35)

        # 右列: キー割当
        y = 0.28
        Text(parent=self.root, text='-- Keys --',
             origin=(0, 0), position=(0.35, y + 0.05),
             scale=1.0, color=color.yellow)

        self._make_key_bind('Jump', 'key_jump', y, x_offset=0.35)
        y -= step
        self._make_key_bind('Sneak', 'key_sneak', y, x_offset=0.35)
        y -= step
        self._make_key_bind('Sprint', 'key_sprint', y, x_offset=0.35)
        y -= step
        self._make_key_bind('Debug', 'key_debug', y, x_offset=0.35)
        y -= step
        self._make_key_bind('Screenshot', 'key_screenshot', y, x_offset=0.35)
        y -= step
        self._make_key_bind('SS Folder', 'key_open_screenshots', y, x_offset=0.35)

        Button(parent=self.root, text='BACK',
               position=(-0.15, -0.4), scale=(0.15, 0.05),
               color=color.gray,
               on_click=self._back)
        Button(parent=self.root, text='SAVE',
               position=(0.15, -0.4), scale=(0.15, 0.05),
               color=color.azure,
               on_click=self._save)
        
        
        import __main__
        from ursina import invoke
        
        def _check_size(label):
            p = __main__.app.win.getProperties()
            print(f'>>> {label}: {p.getXSize()}x{p.getYSize()}')
        
        _check_size('Options opened')
        invoke(lambda: _check_size('0.5s later'), delay=0.5)
        invoke(lambda: _check_size('1s later'), delay=1.0)
        invoke(lambda: _check_size('2s later'), delay=2.0)


    def _make_slider(self, label, key, min_v, max_v, y, x_offset=0):
        Text(parent=self.root, text=label,
             position=(x_offset - 0.25, y), origin=(-0.5, 0),
             scale=0.9, color=color.white)

        sl = Slider(
            parent=self.root,
            min=min_v, max=max_v,
            default=settings.get(key),
            position=(x_offset + 0.05, y),
            scale=0.25,
            step=(max_v - min_v) / 40,
        )
        sl.on_value_changed = lambda k=key, s=sl: self._on_change(k, s)
        self.sliders[key] = sl

        val = settings.get(key)
        val_str = f'{int(val)}' if key == 'max_fps' else f'{val:.2f}'
        val_text = Text(parent=self.root, text=val_str,
                        position=(x_offset + 0.22, y), origin=(-0.5, 0),
                        scale=0.9, color=color.light_gray)
        sl._val_text = val_text

    def _make_key_bind(self, label, key, y, x_offset=0):
        Text(parent=self.root, text=label,
             position=(x_offset - 0.15, y), origin=(-0.5, 0),
             scale=0.9, color=color.white)

        current = settings.get(key)
        btn = Button(
            parent=self.root,
            text=current,
            position=(x_offset + 0.1, y),
            scale=(0.18, 0.045),
            color=color.dark_gray,
        )
        btn.on_click = lambda: self._start_key_capture(key, btn)
        self.sliders[key] = btn

    def _start_key_capture(self, key, btn):
        if self._capturing_key and self._capturing_btn:
            prev_val = self.pending.get(
                self._capturing_key, settings.get(self._capturing_key))
            self._capturing_btn.text = prev_val
            self._capturing_btn.color = color.dark_gray

        btn.text = 'press key...'
        btn.color = color.orange
        self._capturing_key = key
        self._capturing_btn = btn

    def _input(self, key):
        if self._capturing_key:
            if key == 'escape':
                val = self.pending.get(
                    self._capturing_key, settings.get(self._capturing_key))
                self._capturing_btn.text = val
                self._capturing_btn.color = color.dark_gray
                self._capturing_key = None
                self._capturing_btn = None
                return
            if key.endswith(' up') or key.endswith(' hold'):
                return
            self.pending[self._capturing_key] = key
            self._capturing_btn.text = key
            self._capturing_btn.color = color.dark_gray
            self._capturing_key = None
            self._capturing_btn = None
            return

        if key == 'escape':
            self._back()

    def _on_change(self, key, slider):
        v = slider.value
        self.pending[key] = v
        slider._val_text.text = f'{int(v)}' if key == 'max_fps' else f'{v:.2f}'

    def _save(self):
        for k, v in self.pending.items():
            if k == 'max_fps':
                v = int(v)
            settings.set(k, v)
        settings.save()
        if sound_mgr:
            sound_mgr.reload_volumes()
        self._back()



    def _back(self):
        self.pending = {}
        destroy(self.root)
        import __main__
        from ursina import invoke
        if hasattr(__main__, '_maximize_window'):
            invoke(__main__._maximize_window, delay=0.1)
            invoke(__main__._maximize_window, delay=0.5)
        self.on_back()

