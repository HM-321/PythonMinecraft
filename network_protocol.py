"""Small, dependency-free JSON protocol used by the LAN server and clients."""

import json


MAX_MESSAGE_BYTES = 256 * 1024
MAX_LINE_BYTES = MAX_MESSAGE_BYTES + 1


class ProtocolError(ValueError):
    """Raised when a network message is malformed or too large."""


def encode_message(message):
    if not isinstance(message, dict):
        raise ProtocolError('message must be an object')
    _validate_message(message)
    payload = json.dumps(message, separators=(',', ':'), ensure_ascii=True).encode('utf-8')
    if len(payload) > MAX_MESSAGE_BYTES:
        raise ProtocolError('message is too large')
    return payload + b'\n'


def decode_message(line):
    if len(line) > MAX_LINE_BYTES:
        raise ProtocolError('message is too large')
    try:
        message = json.loads(line.decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProtocolError('invalid JSON message') from exc
    if not isinstance(message, dict):
        raise ProtocolError('message must be an object')
    _validate_message(message)
    return message


class MessageBuffer:
    """Collect newline-delimited messages from arbitrarily split TCP reads."""

    def __init__(self):
        self._buffer = bytearray()

    def feed(self, data):
        if not isinstance(data, (bytes, bytearray)):
            raise TypeError('data must be bytes')
        self._buffer.extend(data)
        if len(self._buffer) > MAX_LINE_BYTES and b'\n' not in self._buffer:
            raise ProtocolError('message is too large')

        messages = []
        while b'\n' in self._buffer:
            line, _, remainder = self._buffer.partition(b'\n')
            self._buffer = bytearray(remainder)
            if line:
                messages.append(decode_message(bytes(line)))
        return messages

    def finish(self):
        if self._buffer:
            raise ProtocolError('connection ended mid-message')


def _validate_message(message):
    message_type = message.get('type')
    if not isinstance(message_type, str) or not message_type:
        raise ProtocolError('message type is required')
    if len(message_type) > 40:
        raise ProtocolError('message type is too long')


def hello(name):
    return {'type': 'hello', 'name': str(name)[:32]}


def world_snapshot(blocks, players, player_id):
    return {
        'type': 'world_snapshot',
        'blocks': blocks,
        'players': players,
        'player_id': player_id,
    }