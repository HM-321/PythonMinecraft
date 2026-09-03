from ursina import Button, Entity, Text, camera, color, destroy
from ursina.prefabs.input_field import InputField
from settings import settings


class MultiplayerMenu:
    def __init__(self, on_join, on_back):
        self.on_join = on_join
        self.on_back = on_back
        self.root = Entity(parent=camera.ui)

        Text(parent=self.root, text='JOIN SERVER', origin=(0, 0),
             y=0.35, scale=2.2, color=color.white)
        Text(parent=self.root, text='SERVER IP', origin=(-0.5, 0),
             y=0.16, scale=1, color=color.light_gray)
        self.host = InputField(parent=self.root,
                     default_value=settings.get('last_server_host'),
                             y=0.08)
        Text(parent=self.root, text='PORT', origin=(-0.5, 0),
             y=-0.01, scale=1, color=color.light_gray)
        self.port = InputField(parent=self.root,
                     default_value=str(settings.get('last_server_port')),
                             y=-0.09)
        self.message = Text(parent=self.root, text='', origin=(0, 0),
                            y=-0.21, scale=0.9, color=color.yellow)

        Button(parent=self.root, text='JOIN', y=-0.32, scale=(0.2, 0.06),
               color=color.rgb(60, 150, 100), on_click=self._join)
        Button(parent=self.root, text='BACK', y=-0.41, scale=(0.2, 0.06),
               color=color.dark_gray, on_click=self._back)

    def _join(self):
        host = self.host.text.strip()
        try:
            port = int(self.port.text.strip())
            if not host or not 1 <= port <= 65535:
                raise ValueError
        except ValueError:
            self.message.text = 'INVALID SERVER ADDRESS'
            return
        settings.set('last_server_host', host)
        settings.set('last_server_port', port)
        settings.save()
        self.message.text = 'CONNECTING...'
        self.on_join(host, port, self)

    def show_error(self, message):
        self.message.text = str(message).upper()

    def close(self):
        destroy(self.root)

    def _back(self):
        self.close()
        self.on_back()