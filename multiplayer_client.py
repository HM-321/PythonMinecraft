import queue
import socket
import threading

from network_protocol import MessageBuffer, ProtocolError, encode_message


class MultiplayerClient:
    """Threaded client transport; game objects are only touched by poll()."""

    def __init__(self, host, port, name='Mac player'):
        self.host = host
        self.port = int(port)
        self.name = name[:32]
        self.events = queue.Queue()
        self._socket = None
        self._send_lock = threading.Lock()
        self._thread = None
        self._stop_event = threading.Event()
        self._pending_breaks = set()

    def connect(self, timeout=5):
        if self._thread and self._thread.is_alive():
            raise RuntimeError('client is already connected')
        connection = socket.create_connection((self.host, self.port), timeout=timeout)
        connection.settimeout(1.0)
        self._socket = connection
        self._stop_event.clear()
        self._send({'type': 'hello', 'name': self.name})
        self._thread = threading.Thread(target=self._receive_loop, daemon=True)
        self._thread.start()

    def poll(self, limit=100):
        messages = []
        for _ in range(limit):
            try:
                messages.append(self.events.get_nowait())
            except queue.Empty:
                break
        return messages

    def send_player_state(self, state):
        message = {'type': 'player_state'}
        message.update({key: state[key] for key in
                        ('x', 'y', 'z', 'yaw', 'pitch', 'gravity_on', 'moving')
                        if key in state})
        self._send(message)

    def request_place(self, x, y, z, block_id, orientation='y', player_state=None):
        message = {
            'type': 'place_block', 'x': int(x), 'y': int(y), 'z': int(z),
            'block_id': int(block_id), 'orientation': orientation,
        }
        if player_state:
            for key in ('x', 'y', 'z'):
                if key in player_state:
                    message[f'player_{key}'] = player_state[key]
        self._send(message)

    def request_break(self, x, y, z):
        position = (int(x), int(y), int(z))
        if position in self._pending_breaks:
            return False
        self._pending_breaks.add(position)
        try:
            self._send({'type': 'break_block', 'x': position[0],
                        'y': position[1], 'z': position[2]})
        except (OSError, RuntimeError):
            self._pending_breaks.discard(position)
            raise
        return True

    def acknowledge_break(self, x, y, z):
        self._pending_breaks.discard((int(x), int(y), int(z)))

    def close(self):
        self._stop_event.set()
        self._pending_breaks.clear()
        connection = self._socket
        self._socket = None
        if connection:
            try:
                connection.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            connection.close()
        if self._thread and self._thread is not threading.current_thread():
            self._thread.join(timeout=1)
        self._thread = None

    def _send(self, message):
        connection = self._socket
        if not connection:
            raise RuntimeError('client is not connected')
        payload = encode_message(message)
        with self._send_lock:
            connection.sendall(payload)

    def _receive_loop(self):
        buffer = MessageBuffer()
        reason = 'connection closed'
        try:
            while not self._stop_event.is_set():
                try:
                    data = self._socket.recv(65536)
                except socket.timeout:
                    continue
                if not data:
                    break
                for message in buffer.feed(data):
                    self.events.put(message)
        except (OSError, ProtocolError) as exc:
            reason = str(exc)
        finally:
            if not self._stop_event.is_set():
                self.events.put({'type': 'disconnected', 'reason': reason})