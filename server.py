"""Headless LAN server for MinecraftBuild.

Run with: python server.py --world saves/新規ワールド.json
The Windows build packages this module as a console executable.
"""

import argparse
import json
import math
            if position not in self.world.blocks:
import sys
import threading
            del self.world.blocks[position]
            print(f'player {session.player_id} broke block: {position}')
from config import SAVE_VERSION, WORLD_SIZE
                     'x': position[0], 'y': position[1], 'z': position[2]}

                    continue
                x, y, z, block_id = entry[:4]
                orientation = entry[4] if len(entry) > 4 else 'y'
                self.blocks[(int(x), int(y), int(z))] = [int(block_id), orientation]
            return

        self.blocks = {
            (x, 0, z): [0, 'y']
            for x in range(WORLD_SIZE)
            for z in range(WORLD_SIZE)
        }

    def snapshot(self):
        blocks = [
            [x, y, z, block_id, orientation]
            for (x, y, z), (block_id, orientation) in self.blocks.items()
        ]
        return blocks

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            'version': SAVE_VERSION,
            'name': self.path.stem,
            'last_played': time.strftime('%Y-%m-%dT%H:%M:%S'),
            'player': list(self.player_positions.get('server', (WORLD_SIZE / 2, 3, WORLD_SIZE / 2))),
            'blocks': self.snapshot(),
        }
        temporary_path = self.path.with_suffix(self.path.suffix + '.tmp')
        with temporary_path.open('w', encoding='utf-8') as world_file:
            json.dump(data, world_file, ensure_ascii=False)
        temporary_path.replace(self.path)


class ClientSession:
    def __init__(self, server, connection, address, player_id):
        self.server = server
        self.connection = connection
        self.address = address
        self.player_id = player_id
        self.send_lock = threading.Lock()
        self.alive = True
        self.state = {
            'x': WORLD_SIZE / 2 + player_id * 2,
            'y': 2,
            'z': WORLD_SIZE / 2,
            'yaw': 0,
            'pitch': 0,
            'gravity_on': True,
        }

    def send(self, message):
        payload = encode_message(message)
        with self.send_lock:
            self.connection.sendall(payload)

    def close(self):
        self.alive = False
        try:
            self.connection.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        self.connection.close()


class MinecraftBuildServer:
    def __init__(self, host, port, world_path):
        self.host = host
        self.port = port
        self.world = ServerWorld(world_path)
        self.sessions = {}
        self.sessions_lock = threading.Lock()
        self.stop_event = threading.Event()
        self.listener = None
        self.next_player_id = 1

    def serve_forever(self):
        self.listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.listener.bind((self.host, self.port))
        self.listener.listen(MAX_PLAYERS)
        self.listener.settimeout(1.0)
        print(f'MinecraftBuild server listening on {self.host}:{self.port}')
        last_save = time.monotonic()

        while not self.stop_event.is_set():
            try:
                connection, address = self.listener.accept()
            except socket.timeout:
                connection = None
            except OSError:
                break

            if connection is not None:
                with self.sessions_lock:
                    full = len(self.sessions) >= MAX_PLAYERS
                if full:
                    self._reject(connection, 'server_full')
                else:
                    player_id = self._allocate_player_id()
                    session = ClientSession(self, connection, address, player_id)
                    with self.sessions_lock:
                        self.sessions[player_id] = session
                    threading.Thread(target=self._client_loop, args=(session,), daemon=True).start()
                    print(f'player {player_id} connected from {address[0]}:{address[1]}')

            if time.monotonic() - last_save >= SAVE_INTERVAL:
                self.world.save()
                last_save = time.monotonic()

        self.shutdown()

    def shutdown(self):
        self.stop_event.set()
        if self.listener:
            self.listener.close()
        with self.sessions_lock:
            sessions = list(self.sessions.values())
            self.sessions.clear()
        for session in sessions:
            session.close()
        self.world.save()
        print('server stopped; world saved')

    def _client_loop(self, session):
        buffer = MessageBuffer()
        session.connection.settimeout(1.0)
        try:
            session.send({'type': 'world_snapshot', 'player_id': session.player_id,
                          'blocks': self.world.snapshot(), 'players': self._player_snapshot()})
            self._broadcast({'type': 'player_join', 'player': self._public_player(session)}, exclude=session.player_id)
            while not self.stop_event.is_set() and session.alive:
                try:
                    data = session.connection.recv(65536)
                except socket.timeout:
                    continue
                if not data:
                    break
                for message in buffer.feed(data):
                    self._handle_message(session, message)
        except (OSError, ProtocolError) as exc:
            print(f'player {session.player_id} disconnected: {exc}')
        finally:
            try:
                buffer.finish()
            except ProtocolError:
                pass
            self._remove_session(session)

    def _handle_message(self, session, message):
        message_type = message['type']
        if message_type == 'player_state':
            self._update_state(session, message)
            self._broadcast({'type': 'player_state', 'player': self._public_player(session)},
                            exclude=session.player_id)
        elif message_type in ('place_block', 'break_block'):
            self._handle_block_request(session, message)

    def _update_state(self, session, message):
        for key in ('x', 'y', 'z', 'yaw', 'pitch'):
            value = message.get(key)
            if isinstance(value, (int, float)):
                session.state[key] = max(-10000, min(10000, float(value)))
        if isinstance(message.get('gravity_on'), bool):
            session.state['gravity_on'] = message['gravity_on']
        if isinstance(message.get('moving'), bool):
            session.state['moving'] = message['moving']

    def _handle_block_request(self, session, message):
        try:
            position = tuple(int(message[key]) for key in ('x', 'y', 'z'))
            block_id = int(message.get('block_id', 0))
        except (KeyError, TypeError, ValueError):
            session.send({'type': 'error', 'message': 'invalid block request'})
            return
        if any(abs(value) > WORLD_SIZE * 4 for value in position):
            return

        if message['type'] == 'place_block':
            if not 0 <= block_id <= 255:
                return
            distance = math.sqrt(sum(
                (position[index] - session.state[axis]) ** 2
                for index, axis in enumerate(('x', 'y', 'z'))
            ))
            if distance > 8:
                print(f'player {session.player_id} block request out of reach: '
                      f'position={position}, player={session.state}, distance={distance:.2f}')
                return
            if position in self.world.blocks:
                print(f'player {session.player_id} tried to place an occupied block: {position}')
                return
            orientation = message.get('orientation', 'y')
            if orientation not in ('x', 'y', 'z'):
                orientation = 'y'
            self.world.blocks[position] = [block_id, orientation]
            event = {'type': 'block_changed', 'action': 'place', 'x': position[0],
                     'y': position[1], 'z': position[2], 'block_id': block_id,
                     'orientation': orientation}
        else:
            if position not in self.world.blocks:
                print(f'player {session.player_id} tried to break a missing block: {position}')
                return
            del self.world.blocks[position]
            print(f'player {session.player_id} broke block: {position}')
            event = {'type': 'block_changed', 'action': 'break',
                     'x': position[0], 'y': position[1], 'z': position[2]}
        self._broadcast(event)

    def _broadcast(self, message, exclude=None):
        with self.sessions_lock:
            sessions = list(self.sessions.values())
        for session in sessions:
            if session.player_id == exclude:
                continue
            try:
                session.send(message)
            except OSError:
                self._remove_session(session)

    def _player_snapshot(self):
        with self.sessions_lock:
            return [self._public_player(session) for session in self.sessions.values()]

    @staticmethod
    def _public_player(session):
        return {'id': session.player_id, **session.state}

    def _remove_session(self, session):
        with self.sessions_lock:
            if self.sessions.pop(session.player_id, None) is None:
                return
        session.close()
        self._broadcast({'type': 'player_leave', 'id': session.player_id})
        print(f'player {session.player_id} left')

    def _allocate_player_id(self):
        with self.sessions_lock:
            used = set(self.sessions)
            while self.next_player_id in used:
                self.next_player_id += 1
            player_id = self.next_player_id
            self.next_player_id += 1
            return player_id

    @staticmethod
    def _reject(connection, reason):
        try:
            connection.sendall(encode_message({'type': 'error', 'message': reason}))
        finally:
            connection.close()


def main():
    parser = argparse.ArgumentParser(description='MinecraftBuild LAN server')
    parser.add_argument('--host', default='0.0.0.0')
    parser.add_argument('--port', type=int, default=DEFAULT_PORT)
    parser.add_argument('--world', default=str(DEFAULT_WORLD_PATH),
                        help='path to the server world JSON')
    args = parser.parse_args()

    server = MinecraftBuildServer(args.host, args.port, args.world)
    signal.signal(signal.SIGINT, lambda *_: server.shutdown())
    server.serve_forever()


if __name__ == '__main__':
    main()