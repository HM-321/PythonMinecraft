"""Headless LAN server for MinecraftBuild."""

import argparse
import json
import math
import signal
import socket
import sys
import threading
import time
from pathlib import Path

from config import (PLAYER_HEIGHT, PLAYER_RADIUS, SAVE_VERSION, WORLD_SIZE)
from network_protocol import MessageBuffer, ProtocolError, encode_message


DEFAULT_PORT = 25565
BASE_DIR = Path(sys.executable if getattr(sys, 'frozen', False) else __file__).resolve().parent
DEFAULT_WORLD_PATH = BASE_DIR / 'saves' / 'server_world.json'
MAX_PLAYERS = 2
SAVE_INTERVAL = 30.0


class ServerWorld:
    def __init__(self, path):
        self.path = Path(path)
        self.blocks = {}
        self._load_or_create()

    def _load_or_create(self):
        if self.path.exists():
            with self.path.open(encoding='utf-8') as world_file:
                data = json.load(world_file)
            for entry in data.get('blocks', []):
                if len(entry) < 4:
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
        return [
            [x, y, z, block_id, orientation]
            for (x, y, z), (block_id, orientation) in self.blocks.items()
        ]

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            'version': SAVE_VERSION,
            'name': self.path.stem,
            'last_played': time.strftime('%Y-%m-%dT%H:%M:%S'),
            'player': [WORLD_SIZE / 2, 3, WORLD_SIZE / 2],
            'blocks': self.snapshot(),
        }
        temporary_path = self.path.with_suffix(self.path.suffix + '.tmp')
        with temporary_path.open('w', encoding='utf-8') as world_file:
            json.dump(data, world_file, ensure_ascii=False)
        temporary_path.replace(self.path)


class ClientSession:
    def __init__(self, connection, address, player_id):
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
            'moving': False,
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
        self._run_control_panel()

    def _serve_network(self):
        self.listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.listener.bind((self.host, self.port))
        self.listener.listen(MAX_PLAYERS)
        self.listener.settimeout(1.0)
        print(f'MinecraftBuild server listening on {self.host}:{self.port}')
        last_save = time.monotonic()
        try:
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
                        session = ClientSession(connection, address, player_id)
                        with self.sessions_lock:
                            self.sessions[player_id] = session
                        threading.Thread(target=self._client_loop,
                                         args=(session,), daemon=True).start()
                        print(f'player {player_id} connected from '
                              f'{address[0]}:{address[1]}')
                if time.monotonic() - last_save >= SAVE_INTERVAL:
                    self.world.save()
                    last_save = time.monotonic()
        finally:
            self.shutdown()

    def _run_control_panel(self):
        try:
            import tkinter as tk
            from tkinter import messagebox
        except ImportError:
            print('tkinter is unavailable; press Ctrl+C to stop the server')
            network_thread = threading.Thread(target=self._serve_network, daemon=True)
            network_thread.start()
            try:
                while not self.stop_event.wait(1.0):
                    pass
            except KeyboardInterrupt:
                self.shutdown()
            return

        root = tk.Tk()
        root.title('MinecraftBuild Server')
        root.geometry('520x520')
        root.resizable(False, False)
        tk.Label(root, text='MinecraftBuild Server',
                 font=('Arial', 16, 'bold')).pack(pady=(16, 2))
        tk.Label(root, text=f'LAN port: {self.port}').pack(pady=(0, 10))

        tk.Label(root, text='Select a world',
                 font=('Arial', 12, 'bold')).pack(anchor='w', padx=28)
        world_list = tk.Listbox(root, height=10, width=58, exportselection=False)
        world_list.pack(padx=28, pady=6)

        saves_dir = BASE_DIR / 'saves'
        saves_dir.mkdir(parents=True, exist_ok=True)
        world_paths = sorted(saves_dir.glob('*.json'))
        for path in world_paths:
            world_list.insert(tk.END, path.name)
        if world_paths:
            world_list.selection_set(0)

        tk.Label(root, text='New world name (optional)').pack(anchor='w', padx=28)
        world_name = tk.Entry(root, width=48)
        world_name.pack(padx=28, pady=(3, 6))
        use_template = tk.BooleanVar(value=True)
        tk.Checkbutton(root, text='Use Template.json for a new world',
                       variable=use_template).pack(anchor='w', padx=28)

        player_label = tk.Label(root, text='Players: 0 / 2')
        player_label.pack(pady=(12, 4))
        status_label = tk.Label(root, text='Choose a world, then start the server',
                                fg='gray')
        status_label.pack(pady=3)

        controls = []

        def set_controls_enabled(enabled):
            state = tk.NORMAL if enabled else tk.DISABLED
            for control in controls:
                control.config(state=state)

        def start_server():
            name = world_name.get().strip()
            if name:
                safe_name = ''.join(char for char in name
                                    if char.isalnum() or char in '_-')
                if not safe_name:
                    messagebox.showerror('Invalid name', 'Enter a valid world name.')
                    return
                selected_path = saves_dir / f'{safe_name}.json'
                if selected_path.exists() and not messagebox.askyesno(
                        'Overwrite world', 'Replace this existing world?'):
                    return
                self._create_selected_world(selected_path, use_template.get())
            else:
                selected = world_list.curselection()
                if not selected:
                    messagebox.showerror('No world selected',
                                         'Select a saved world or enter a new name.')
                    return
                selected_path = world_paths[selected[0]]
                self.world = ServerWorld(selected_path)

            status_label.config(text=f'Running: {selected_path.name}', fg='green')
            set_controls_enabled(False)
            network_thread = threading.Thread(target=self._serve_network, daemon=True)
            network_thread.start()

        start_button = tk.Button(root, text='Start server', command=start_server,
                                 width=24, height=2)
        start_button.pack(pady=(12, 4))
        controls.extend([world_list, world_name, start_button])

        def refresh():
            if self.stop_event.is_set():
                root.destroy()
                return
            with self.sessions_lock:
                count = len(self.sessions)
            player_label.config(text=f'Players: {count} / {MAX_PLAYERS}')
            root.after(500, refresh)

        def reset_world():
            if messagebox.askyesno(
                    'New world',
                    'Save the current world and create a new flat world?'):
                self.create_new_world()

        reset_button = tk.Button(root, text='New world while running',
                     command=reset_world, width=24)
        reset_button.pack(pady=8)
        controls.append(reset_button)
        def close_panel():
            self.shutdown()
            root.destroy()

        root.protocol('WM_DELETE_WINDOW', close_panel)
        root.after(0, refresh)
        root.mainloop()

    def _create_selected_world(self, path, use_template):
        self.world = ServerWorld(path)
        if use_template:
            template_path = BASE_DIR / 'Template.json'
            if template_path.exists():
                self.world.blocks.clear()
                with template_path.open(encoding='utf-8') as template_file:
                    data = json.load(template_file)
                for entry in data.get('blocks', []):
                    if len(entry) < 4:
                        continue
                    x, y, z, block_id = entry[:4]
                    orientation = entry[4] if len(entry) > 4 else 'y'
                    self.world.blocks[(int(x), int(y), int(z))] = [
                        int(block_id), orientation]
        self.world.save()

    def create_new_world(self):
        self.world.save()
        self.world.blocks = {
            (x, 0, z): [0, 'y']
            for x in range(WORLD_SIZE)
            for z in range(WORLD_SIZE)
        }
        self.world.save()
        with self.sessions_lock:
            sessions = list(self.sessions.values())
        for session in sessions:
            try:
                session.send({
                    'type': 'world_reset',
                    'blocks': self.world.snapshot(),
                })
            except OSError:
                self._remove_session(session)
        print('new world created and sent to connected players')

    def shutdown(self):
        if self.stop_event.is_set() and self.listener is None:
            return
        self.stop_event.set()
        if self.listener:
            self.listener.close()
            self.listener = None
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
            session.send({
                'type': 'world_snapshot',
                'player_id': session.player_id,
                'blocks': self.world.snapshot(),
                'players': self._player_snapshot(),
            })
            self._broadcast({'type': 'player_join',
                             'player': self._public_player(session)},
                            exclude=session.player_id)
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
            self._remove_session(session)

    def _handle_message(self, session, message):
        if message['type'] == 'player_state':
            self._update_state(session, message)
            self._broadcast({'type': 'player_state',
                             'player': self._public_player(session)},
                            exclude=session.player_id)
        elif message['type'] in ('place_block', 'break_block'):
            self._handle_block_request(session, message)

    def _update_state(self, session, message):
        for key in ('x', 'y', 'z', 'yaw', 'pitch'):
            value = message.get(key)
            if isinstance(value, (int, float)):
                session.state[key] = max(-10000, min(10000, float(value)))
        for key in ('gravity_on', 'moving'):
            if isinstance(message.get(key), bool):
                session.state[key] = message[key]

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
            if not 0 <= block_id <= 255 or position in self.world.blocks:
                return
            self._update_position_from_request(session, message)
            if self._block_overlaps_player(position, session):
                print(f'player {session.player_id} place rejected: '
                      f'block intersects player at {position}')
                return
            orientation = message.get('orientation', 'y')
            if orientation not in ('x', 'y', 'z'):
                orientation = 'y'
            self.world.blocks[position] = [block_id, orientation]
            event = {'type': 'block_changed', 'action': 'place',
                     'x': position[0], 'y': position[1], 'z': position[2],
                     'block_id': block_id, 'orientation': orientation}
        else:
            if position not in self.world.blocks:
                return
            del self.world.blocks[position]
            print(f'player {session.player_id} broke block: {position}')
            event = {'type': 'block_changed', 'action': 'break',
                     'x': position[0], 'y': position[1], 'z': position[2]}
        self._broadcast(event)

    def _update_position_from_request(self, session, message):
        for key in ('x', 'y', 'z'):
            value = message.get(f'player_{key}')
            if isinstance(value, (int, float)):
                session.state[key] = max(-10000, min(10000, float(value)))

    def _block_overlaps_player(self, block_position, placing_session):
        block_x, block_y, block_z = block_position
        for session in self.sessions.values():
            if session is not placing_session:
                player = session.state
            else:
                player = placing_session.state
            overlaps = (
                player['x'] - PLAYER_RADIUS < block_x + 0.5 and
                player['x'] + PLAYER_RADIUS > block_x - 0.5 and
                player['y'] < block_y and
                player['y'] + PLAYER_HEIGHT > block_y - 1 and
                player['z'] - PLAYER_RADIUS < block_z + 0.5 and
                player['z'] + PLAYER_RADIUS > block_z - 0.5
            )
            if overlaps:
                return True
        return False

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
            return [self._public_player(session)
                    for session in self.sessions.values()]

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
            player_id = 1
            while player_id in used:
                player_id += 1
            self.next_player_id = player_id + 1
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
    parser.add_argument('--world', default=str(DEFAULT_WORLD_PATH))
    args = parser.parse_args()
    server = MinecraftBuildServer(args.host, args.port, args.world)
    signal.signal(signal.SIGINT, lambda *_: server.shutdown())
    server.serve_forever()


if __name__ == '__main__':
    main()
