"""Headless LAN server for MinecraftBuild."""

import argparse
import json
import math
import secrets
import signal
import socket
import sys
import threading
import time
from pathlib import Path

from config import (PLAYER_HEIGHT, PLAYER_RADIUS, SAVE_VERSION, WORLD_SIZE)
from network_protocol import MessageBuffer, ProtocolError, encode_message
from terrain_generator import (
    GENERATOR_ID, TREE_GENERATOR_ID,
    iter_grassland_blocks, iter_grassland_v2_blocks,
)


DEFAULT_PORT = 25565
APP_DIR = Path(sys.executable if getattr(sys, 'frozen', False) else __file__).resolve().parent
RESOURCE_DIR = Path(getattr(sys, '_MEIPASS', APP_DIR))
DEFAULT_WORLD_PATH = APP_DIR / 'saves' / 'server_world.json'
DEFAULT_MAX_PLAYERS = 8
MAX_PLAYERS_LIMIT = 128
SAVE_INTERVAL = 30.0
SAND_BLOCK_ID = 5
SAND_TICK = 0.04
SAND_COLUMN_INTERVAL = 0.11
SAND_ACCELERATION = 24.0
SAND_TERMINAL_SPEED = 28.0
SAND_MIN_Y = -64


def get_local_ip():
    """Return the LAN address other computers can use to reach this server."""
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(('8.8.8.8', 80))
        return probe.getsockname()[0]
    except OSError:
        return '127.0.0.1'
    finally:
        probe.close()


class ServerWorld:
    def __init__(self, path):
        self.path = Path(path)
        self.blocks = {}
        self.generated_positions = set()
        self.placed_blocks = {}
        self.removed_blocks = set()
        self.generator = TREE_GENERATOR_ID
        self.seed = secrets.randbits(64)
        self._load_or_create()

    @staticmethod
    def _template_data():
        resource_path = RESOURCE_DIR / 'Template.json'
        template_path = resource_path if resource_path.exists() else APP_DIR / 'Template.json'
        with template_path.open(encoding='utf-8') as template_file:
            return json.load(template_file)

    def _generated_template(self):
        blocks = {}
        for entry in self._template_data().get('blocks', []):
            if len(entry) >= 4:
                position = tuple(int(value) for value in entry[:3])
                blocks[position] = [
                    int(entry[3]), entry[4] if len(entry) > 4 else 'y'
                ]
        return blocks

    def _generated_grassland(self):
        return {
            (x, y, z): [block_id, orientation]
            for x, y, z, block_id, orientation in iter_grassland_blocks(
                self.seed, WORLD_SIZE
            )
        }

    def _generated_grassland_v2(self):
        return {
            (x, y, z): [block_id, orientation]
            for x, y, z, block_id, orientation in iter_grassland_v2_blocks(
                self.seed, WORLD_SIZE
            )
        }

    def _load_or_create(self):
        if self.path.exists():
            with self.path.open(encoding='utf-8') as world_file:
                data = json.load(world_file)
            self.seed = int(data.get('seed', secrets.randbits(64)))
            self.generator = data.get('generator')
            if self.generator == 'template_v1':
                self.blocks = self._generated_template()
                self.generated_positions = set(self.blocks)
                for entry in data.get('removed_blocks', []):
                    if len(entry) >= 3:
                        self.blocks.pop(tuple(map(int, entry[:3])), None)
                for entry in data.get('placed_blocks', []):
                    if len(entry) >= 4:
                        self.blocks[tuple(map(int, entry[:3]))] = [
                            int(entry[3]),
                            entry[4] if len(entry) > 4 else 'y',
                        ]
            elif self.generator == TREE_GENERATOR_ID:
                self.blocks = self._generated_grassland_v2()
                self.generated_positions = set(self.blocks)
                for e in data.get('removed_blocks', []):
                    if len(e) >= 3:
                        self.blocks.pop(tuple(map(int, e[:3])), None)
                for e in data.get('placed_blocks', []):
                    if len(e) >= 4:
                        self.blocks[tuple(map(int, e[:3]))] = [
                            int(e[3]), e[4] if len(e) > 4 else 'y'
                        ]
            elif self.generator == GENERATOR_ID:
                self.blocks = self._generated_grassland()
                self.generated_positions = set(self.blocks)
                for e in data.get('removed_blocks', []):
                    if len(e) >= 3: self.blocks.pop(tuple(map(int, e[:3])), None)
                for e in data.get('placed_blocks', []):
                    if len(e) >= 4: self.blocks[tuple(map(int, e[:3]))] = [int(e[3]), e[4] if len(e) > 4 else 'y']
            elif self.generator == 'flat_v1':
                self.blocks = {(x, 0, z): [0, 'y'] for x in range(WORLD_SIZE) for z in range(WORLD_SIZE)}
                self.generated_positions = set(self.blocks)
                for e in data.get('removed_blocks', []):
                    if len(e) >= 3: self.blocks.pop(tuple(map(int, e[:3])), None)
                for e in data.get('placed_blocks', []):
                    if len(e) >= 4: self.blocks[tuple(map(int, e[:3]))] = [int(e[3]), e[4] if len(e) > 4 else 'y']
            else:
                self.generator = None
                self.blocks = {}
                for e in data.get('blocks', []):
                    if len(e) >= 4: self.blocks[tuple(map(int, e[:3]))] = [int(e[3]), e[4] if len(e) > 4 else 'y']
                self.generated_positions = set(self.blocks)
            self.placed_blocks = {tuple(map(int,e[:3])):[int(e[3]),e[4] if len(e)>4 else 'y'] for e in data.get('placed_blocks',[]) if len(e)>=4}
            self.removed_blocks = {tuple(map(int,e[:3])) for e in data.get('removed_blocks',[]) if len(e)>=3}
            self.generated_positions.difference_update(self.placed_blocks)
            return
        self.generator = TREE_GENERATOR_ID
        self.blocks = self._generated_grassland_v2()
        self.generated_positions = set(self.blocks)
        self.placed_blocks.clear()
        self.removed_blocks.clear()

    def snapshot(self):
        return [
            [x, y, z, block_id, orientation]
            for (x, y, z), (block_id, orientation) in self.blocks.items()
        ]

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            'version': SAVE_VERSION,
            'seed': self.seed,
            'name': self.path.stem,
            'last_played': time.strftime('%Y-%m-%dT%H:%M:%S'),
            'player': [WORLD_SIZE / 2, 3, WORLD_SIZE / 2],
            'generator': self.generator,
            'placed_blocks': [
                [x, y, z, value[0], value[1]]
                for (x, y, z), value in self.placed_blocks.items()
            ],
            'removed_blocks': [list(position) for position in sorted(self.removed_blocks)],
        }
        if self.generator is None:
            data['blocks'] = self.snapshot()
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
            'sneaking': False,
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
    def __init__(self, host, port, world_path, max_players=DEFAULT_MAX_PLAYERS):
        self.host = host
        self.port = port
        self.max_players = max(1, min(MAX_PLAYERS_LIMIT, int(max_players)))
        self.world = ServerWorld(world_path)
        self.sessions = {}
        self.sessions_lock = threading.Lock()
        self.stop_event = threading.Event()
        self.listener = None
        self.next_player_id = 1
        self.falling_sand = {}
        self.sand_lock = threading.Lock()
        self.next_fall_id = 1
        self.sand_column_ready = {}

    def serve_forever(self):
        self._run_control_panel()

    def _serve_network(self):
        self.listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.listener.bind((self.host, self.port))
        self.listener.listen(max(self.max_players, 8))
        self.listener.settimeout(1.0)
        threading.Thread(target=self._sand_loop, daemon=True).start()
        display_host = get_local_ip() if self.host in ('', '0.0.0.0') else self.host
        print(f'MinecraftBuild server listening on {display_host}:{self.port}')
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
                        full = len(self.sessions) >= self.max_players
                    if full:
                        self._reject(connection, 'server_full')
                    else:
                        player_id = self._allocate_player_id()
                        session = ClientSession(connection, address, player_id)
                        spawn = self._find_safe_spawn(player_id)
                        session.state['x'] = spawn[0]
                        session.state['y'] = spawn[1]
                        session.state['z'] = spawn[2]
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

    def _find_safe_spawn(self, player_id=1):
        """ワールド中央から外側へ探索して、安全な地表を返す。"""
        center_x = int(WORLD_SIZE // 2) + (player_id - 1) * 2
        center_z = int(WORLD_SIZE // 2)
        max_radius = max(WORLD_SIZE, 32)

        columns = {}
        for (x, y, z), (block_id, _orientation) in self.world.blocks.items():
            columns.setdefault((x, z), []).append((y, block_id))

        for radius in range(max_radius + 1):
            for dx in range(-radius, radius + 1):
                for dz in range(-radius, radius + 1):
                    if max(abs(dx), abs(dz)) != radius:
                        continue

                    x = center_x + dx
                    z = center_z + dz
                    column = columns.get((x, z))
                    if not column:
                        continue

                    # 上から順に、砂以外の安定した床を探す。
                    for floor_y, block_id in sorted(column, reverse=True):
                        if block_id == SAND_BLOCK_ID:
                            continue

                        feet_block = (x, floor_y + 1, z)
                        head_block = (x, floor_y + 2, z)
                        if (
                            feet_block not in self.world.blocks
                            and head_block not in self.world.blocks
                        ):
                            return (
                                x + 0.001,
                                floor_y + 0.01,
                                z + 0.001,
                            )

        # 安全地点がない場合だけ、従来に近い中央上空へ退避する。
        return (WORLD_SIZE / 2, 3.0, WORLD_SIZE / 2)

    def _run_control_panel(self):
        try:
            import tkinter as tk
            from tkinter import messagebox, ttk
        except ImportError:
            print('tkinter is unavailable; press Ctrl+C to stop the server')
            network_thread = threading.Thread(
                target=self._serve_network, daemon=True
            )
            network_thread.start()
            try:
                while not self.stop_event.wait(1.0):
                    pass
            except KeyboardInterrupt:
                self.shutdown()
            return

        root = tk.Tk()
        root.title('MinecraftBuild Server')
        root.geometry('560x620')
        root.minsize(520, 560)

        style = ttk.Style(root)
        style.configure('Title.TLabel', font=('Arial', 17, 'bold'))
        style.configure('Section.TLabelframe.Label', font=('Arial', 11, 'bold'))
        style.configure('Status.TLabel', font=('Arial', 11, 'bold'))

        main = ttk.Frame(root, padding=16)
        main.pack(fill='both', expand=True)
        main.columnconfigure(0, weight=1)
        main.rowconfigure(2, weight=1)

        display_host = (
            get_local_ip() if self.host in ('', '0.0.0.0') else self.host
        )
        saves_dir = APP_DIR / 'saves'
        saves_dir.mkdir(parents=True, exist_ok=True)
        world_paths = []
        running = False

        ttk.Label(
            main, text='MinecraftBuild Server', style='Title.TLabel'
        ).grid(row=0, column=0, sticky='w', pady=(0, 12))

        status_box = ttk.LabelFrame(
            main, text='Server', padding=12, style='Section.TLabelframe'
        )
        status_box.grid(row=1, column=0, sticky='ew', pady=(0, 12))
        status_box.columnconfigure(1, weight=1)

        ttk.Label(status_box, text='Status').grid(row=0, column=0, sticky='w')
        status_label = ttk.Label(
            status_box, text='Stopped', foreground='#777777',
            style='Status.TLabel'
        )
        status_label.grid(row=0, column=1, sticky='w', padx=(12, 0))

        ttk.Label(status_box, text='Address').grid(row=1, column=0, sticky='w')
        address_var = tk.StringVar(value=f'{display_host}:{self.port}')
        address_entry = ttk.Entry(
            status_box, textvariable=address_var, state='readonly'
        )
        address_entry.grid(row=1, column=1, sticky='ew', padx=(12, 0), pady=3)

        ttk.Label(status_box, text='Players').grid(row=2, column=0, sticky='w')
        players_label = ttk.Label(status_box, text=f'0 / {self.max_players}')
        players_label.grid(row=2, column=1, sticky='w', padx=(12, 0))

        ttk.Label(status_box, text='Seed').grid(row=3, column=0, sticky='w')
        seed_var = tk.StringVar(value=str(self.world.seed))
        seed_entry = ttk.Entry(
            status_box, textvariable=seed_var, state='readonly'
        )
        seed_entry.grid(row=3, column=1, sticky='ew', padx=(12, 0), pady=3)

        ttk.Label(status_box, text='Generator').grid(row=4, column=0, sticky='w')
        generator_label = ttk.Label(
            status_box, text=self.world.generator or 'legacy'
        )
        generator_label.grid(row=4, column=1, sticky='w', padx=(12, 0))

        world_box = ttk.LabelFrame(
            main, text='World', padding=12, style='Section.TLabelframe'
        )
        world_box.grid(row=2, column=0, sticky='nsew', pady=(0, 12))
        world_box.columnconfigure(0, weight=1)
        world_box.rowconfigure(1, weight=1)

        ttk.Label(world_box, text='Saved worlds').grid(
            row=0, column=0, sticky='w', pady=(0, 4)
        )
        list_frame = ttk.Frame(world_box)
        list_frame.grid(row=1, column=0, sticky='nsew')
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)
        world_list = tk.Listbox(
            list_frame, height=9, exportselection=False,
            activestyle='dotbox'
        )
        world_list.grid(row=0, column=0, sticky='nsew')
        scrollbar = ttk.Scrollbar(
            list_frame, orient='vertical', command=world_list.yview
        )
        scrollbar.grid(row=0, column=1, sticky='ns')
        world_list.configure(yscrollcommand=scrollbar.set)

        form = ttk.Frame(world_box)
        form.grid(row=2, column=0, sticky='ew', pady=(10, 0))
        form.columnconfigure(1, weight=1)
        ttk.Label(form, text='New world name').grid(row=0, column=0, sticky='w')
        world_name = ttk.Entry(form)
        world_name.grid(row=0, column=1, sticky='ew', padx=(10, 0))

        ttk.Label(form, text='Maximum players').grid(
            row=1, column=0, sticky='w', pady=(7, 0)
        )
        max_players_var = tk.IntVar(value=self.max_players)
        max_players_spin = ttk.Spinbox(
            form, from_=1, to=MAX_PLAYERS_LIMIT,
            textvariable=max_players_var, width=8
        )
        max_players_spin.grid(row=1, column=1, sticky='w', padx=(10, 0), pady=(7, 0))

        use_template = tk.BooleanVar(value=False)
        template_check = ttk.Checkbutton(
            form, text='Use Template.json', variable=use_template
        )
        template_check.grid(row=2, column=1, sticky='w', padx=(10, 0), pady=(7, 0))

        buttons = ttk.Frame(main)
        buttons.grid(row=3, column=0, sticky='ew')
        for column in range(3):
            buttons.columnconfigure(column, weight=1)

        startup_controls = []

        def selected_world_path():
            selected = world_list.curselection()
            if not selected:
                return None
            return world_paths[selected[0]]

        def refresh_world_list(select_path=None):
            nonlocal world_paths
            world_paths = sorted(saves_dir.glob('*.json'))
            world_list.delete(0, tk.END)
            for world_path in world_paths:
                world_list.insert(tk.END, world_path.name)
            if select_path in world_paths:
                world_list.selection_set(world_paths.index(select_path))
            elif world_paths:
                world_list.selection_set(0)

        def read_player_limit():
            try:
                value = int(max_players_var.get())
            except (TypeError, ValueError):
                value = 0
            if not 1 <= value <= MAX_PLAYERS_LIMIT:
                messagebox.showerror(
                    'Invalid player count',
                    f'Enter a number from 1 to {MAX_PLAYERS_LIMIT}.'
                )
                return None
            return value

        def set_running_state(world_path):
            nonlocal running
            running = True
            status_label.config(text=f'Running: {world_path.name}', foreground='#16803a')
            for control in startup_controls:
                control.config(state=tk.DISABLED)

        def launch_network():
            threading.Thread(target=self._serve_network, daemon=True).start()

        def start_selected():
            limit = read_player_limit()
            selected = selected_world_path()
            if limit is None:
                return
            if selected is None:
                messagebox.showerror('No world selected', 'Select a saved world first.')
                return
            self.max_players = limit
            self.world = ServerWorld(selected)
            set_running_state(selected)
            launch_network()

        def create_and_start():
            limit = read_player_limit()
            if limit is None:
                return
            name = world_name.get().strip()
            if name:
                safe_name = ''.join(
                    character for character in name
                    if character.isalnum() or character in '_-'
                )
                if not safe_name:
                    messagebox.showerror('Invalid name', 'Enter a valid world name.')
                    return
                selected = saves_dir / f'{safe_name}.json'
                if selected.exists() and not messagebox.askyesno(
                    'Overwrite world', f'Replace "{selected.name}"?'
                ):
                    return
            else:
                selected = self._next_world_path(saves_dir)
            self.max_players = limit
            self._create_selected_world(selected, use_template.get())
            refresh_world_list(selected)
            set_running_state(selected)
            launch_network()

        def save_now():
            self._save_world()
            status_label.config(text='Saved', foreground='#16803a')

        def switch_world():
            selected = selected_world_path()
            if selected is None:
                messagebox.showerror('No world selected', 'Select a saved world first.')
                return
            if not running:
                start_selected()
                return
            if selected == self.world.path:
                return
            if messagebox.askyesno(
                'Switch world', f'Switch to "{selected.name}"?'
            ):
                self.load_existing_world(selected)
                status_label.config(
                    text=f'Running: {selected.name}', foreground='#16803a'
                )

        def new_running_world():
            if not running:
                create_and_start()
                return
            if messagebox.askyesno(
                'New world', 'Save the current world and create a new world?'
            ):
                self.create_new_world()
                refresh_world_list(self.world.path)
                status_label.config(
                    text=f'Running: {self.world.path.name}', foreground='#16803a'
                )

        def delete_selected():
            selected = selected_world_path()
            if selected is None:
                messagebox.showerror('No world selected', 'Select a saved world first.')
                return
            if running:
                messagebox.showerror('Server is running', 'Stop the server before deleting worlds.')
                return
            if not messagebox.askyesno(
                'Delete world', f'Delete {selected.name} permanently?'
            ):
                return
            try:
                selected.unlink()
            except OSError as exc:
                messagebox.showerror('Delete failed', str(exc))
                return
            refresh_world_list()

        start_button = ttk.Button(
            buttons, text='Start selected', command=start_selected
        )
        start_button.grid(row=0, column=0, sticky='ew', padx=(0, 4))
        create_button = ttk.Button(
            buttons, text='Create and start', command=create_and_start
        )
        create_button.grid(row=0, column=1, sticky='ew', padx=4)
        save_button = ttk.Button(buttons, text='Save now', command=save_now)
        save_button.grid(row=0, column=2, sticky='ew', padx=(4, 0))

        switch_button = ttk.Button(
            buttons, text='Switch selected', command=switch_world
        )
        switch_button.grid(row=1, column=0, sticky='ew', padx=(0, 4), pady=(8, 0))
        new_button = ttk.Button(
            buttons, text='New world', command=new_running_world
        )
        new_button.grid(row=1, column=1, sticky='ew', padx=4, pady=(8, 0))
        delete_button = ttk.Button(
            buttons, text='Delete selected', command=delete_selected
        )
        delete_button.grid(row=1, column=2, sticky='ew', padx=(4, 0), pady=(8, 0))

        startup_controls.extend([
            world_name, max_players_spin, template_check,
            start_button, create_button,
        ])

        def refresh():
            if self.stop_event.is_set():
                root.destroy()
                return
            with self.sessions_lock:
                player_count = len(self.sessions)
            players_label.config(text=f'{player_count} / {self.max_players}')
            seed_var.set(str(self.world.seed))
            generator_label.config(text=self.world.generator or 'legacy')
            root.after(500, refresh)

        def close_panel():
            self.shutdown()
            root.destroy()

        def confirm_shutdown():
            if not messagebox.askyesno(
                'Close server',
                'Save the world and close the server?',
            ):
                return

            status_label.config(
                text='Stopping...',
                foreground='#a03030',
            )
            root.update_idletasks()
            close_panel()

        close_button = ttk.Button(
            buttons,
            text='Save and close server',
            command=confirm_shutdown,
        )
        close_button.grid(
            row=2,
            column=0,
            columnspan=3,
            sticky='ew',
            pady=(12, 0),
        )

        refresh_world_list(self.world.path)
        world_list.bind('<Double-Button-1>', lambda _event: switch_world())
        root.protocol('WM_DELETE_WINDOW', close_panel)
        root.after(0, refresh)
        root.mainloop()

    def _create_selected_world(self, path, use_template):
        self.world = ServerWorld(path)
        if use_template:
            self.world.generator = 'template_v1'
            self.world.blocks = self.world._generated_template()
            self.world.generated_positions = set(self.world.blocks)
            self.world.placed_blocks.clear()
            self.world.removed_blocks.clear()
        self.world.save()

    @staticmethod
    def _next_world_path(saves_dir, base_name='新規ワールド'):
        candidate = saves_dir / f'{base_name}.json'
        if not candidate.exists():
            return candidate
        number = 1
        while True:
            candidate = saves_dir / f'{base_name}（{number}）.json'
            if not candidate.exists():
                return candidate
            number += 1

    def create_new_world(self):
        self._save_world()
        new_path = self._next_world_path(APP_DIR / 'saves', '新規ワールド')
        self.world = ServerWorld(new_path)
        self._save_world()
        self._broadcast_world_reset()
        print('new world created and sent to connected players')

    def create_template_world(self):
        self._save_world()
        new_path = self._next_world_path(
            APP_DIR / 'saves', 'テンプレートワールド'
        )
        new_world = ServerWorld(new_path)
        new_world.generator = 'template_v1'
        new_world.blocks = new_world._generated_template()
        new_world.generated_positions = set(new_world.blocks)
        new_world.placed_blocks.clear()
        new_world.removed_blocks.clear()
        self.world = new_world
        self._save_world()
        self._broadcast_world_reset()
        print('template world regenerated and sent to connected players')

    def load_existing_world(self, path):
        self._save_world()
        self.world = ServerWorld(path)
        self._save_world()
        self._broadcast_world_reset()
        print(f'existing world "{Path(path).name}" loaded and sent to connected players')

    def _world_sync_payload(self):
        payload = {
            'seed': self.world.seed,
            'generator': self.world.generator,
            'placed_blocks': [
                [x, y, z, value[0], value[1]]
                for (x, y, z), value in self.world.placed_blocks.items()
            ],
            'removed_blocks': [
                list(position) for position in sorted(self.world.removed_blocks)
            ],
        }
        if self.world.generator is None:
            payload['blocks'] = self.world.snapshot()
        return payload

    def _broadcast_world_reset(self):
        with self.sessions_lock:
            sessions = list(self.sessions.values())
        for session in sessions:
            try:
                session.send({
                    'type': 'world_reset',
                    **self._world_sync_payload(),
                })
            except OSError:
                self._remove_session(session)

    @staticmethod
    def _template_path():
        resource_path = RESOURCE_DIR / 'Template.json'
        if resource_path.exists():
            return resource_path
        return APP_DIR / 'Template.json'

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
        self._save_world()
        print('server stopped; world saved')

    def _save_world(self):
        if self.world:
            self.world.save()

    def _client_loop(self, session):
        buffer = MessageBuffer()
        session.connection.settimeout(1.0)
        try:
            session.send({
                'type': 'world_snapshot',
                'player_id': session.player_id,
                'players': self._player_snapshot(),
                **self._world_sync_payload(),
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
        for key in ('gravity_on', 'moving', 'sneaking'):
            if isinstance(message.get(key), bool):
                session.state[key] = message[key]

    def _handle_block_request(self, session, message):
        try:
            position = tuple(int(round(float(message[key]))) for key in ('x', 'y', 'z'))
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
            self.world.placed_blocks[position] = [block_id, orientation]
            self.world.removed_blocks.discard(position)
            event = {'type': 'block_changed', 'action': 'place',
                     'x': position[0], 'y': position[1], 'z': position[2],
                     'block_id': block_id, 'orientation': orientation}
        else:
            if position not in self.world.blocks:
                return
            del self.world.blocks[position]
            if position in self.world.placed_blocks:
                self.world.placed_blocks.pop(position, None)
            elif position in self.world.generated_positions:
                self.world.removed_blocks.add(position)
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
        # クライアント側block_overlaps()と同じ許容誤差を使う。
        # 壁への微小な食い込みで壁上への設置を拒否しない。
        horizontal_margin = 0.03
        vertical_margin = 0.01
        radius = max(0.0, PLAYER_RADIUS - horizontal_margin)

        with self.sessions_lock:
            sessions = list(self.sessions.values())

        for session in sessions:
            player = session.state
            overlaps = (
                player['x'] - radius < block_x + 0.5 and
                player['x'] + radius > block_x - 0.5 and
                player['y'] + vertical_margin < block_y and
                player['y'] + PLAYER_HEIGHT - vertical_margin > block_y - 1 and
                player['z'] - radius < block_z + 0.5 and
                player['z'] + radius > block_z - 0.5
            )
            if overlaps:
                return True
        return False


    def _sand_loop(self):
        last = time.monotonic()
        while not self.stop_event.wait(SAND_TICK):
            now = time.monotonic()
            dt = min(0.1, now - last)
            last = now
            with self.sand_lock:
                self._start_unstable_sand(now)
                self._advance_falling_sand(dt, now)

    def _start_unstable_sand(self, now):
        falling_sources = {item['source'] for item in self.falling_sand.values()}
        candidates = []
        for (x, y, z), (block_id, orientation) in tuple(self.world.blocks.items()):
            if block_id != SAND_BLOCK_ID or (x, y, z) in falling_sources:
                continue
            if y <= SAND_MIN_Y or (x, y - 1, z) in self.world.blocks:
                continue
            column = (x, z)
            if now < self.sand_column_ready.get(column, 0.0):
                continue
            candidates.append((y, x, z, orientation))
        if not candidates:
            return

        y, x, z, orientation = min(candidates)
        source = (x, y, z)
        current = self.world.blocks.get(source)
        if not current or current[0] != SAND_BLOCK_ID:
            return
        del self.world.blocks[source]
        fall_id = self.next_fall_id
        self.next_fall_id += 1
        self.falling_sand[fall_id] = {
            'source': source, 'x': x, 'z': z, 'y': float(y),
            'velocity': 0.0, 'orientation': orientation,
        }
        self.sand_column_ready[(x, z)] = now + SAND_COLUMN_INTERVAL
        self._broadcast({
            'type': 'sand_fall_start', 'fall_id': fall_id,
            'x': x, 'y': y, 'z': z, 'block_id': SAND_BLOCK_ID,
        })

    def _advance_falling_sand(self, dt, now):
        landed = []
        for fall_id, item in tuple(self.falling_sand.items()):
            item['velocity'] = min(
                SAND_TERMINAL_SPEED,
                item['velocity'] + SAND_ACCELERATION * dt,
            )
            next_y = item['y'] - item['velocity'] * dt
            landing_y = self._sand_landing_y(item['x'], item['z'], item['y'], next_y)
            if landing_y is None:
                item['y'] = next_y
                continue
            destination = (item['x'], landing_y, item['z'])
            if destination in self.world.blocks:
                # A newly placed block may occupy the first candidate position.
                landing_y += 1
                destination = (item['x'], landing_y, item['z'])
            self.world.blocks[destination] = [SAND_BLOCK_ID, item['orientation']]
            landed.append((fall_id, destination))
            self.sand_column_ready[(item['x'], item['z'])] = now + SAND_COLUMN_INTERVAL

        for fall_id, destination in landed:
            self.falling_sand.pop(fall_id, None)
            self._broadcast({
                'type': 'sand_fall_land', 'fall_id': fall_id,
                'x': destination[0], 'y': destination[1], 'z': destination[2],
                'block_id': SAND_BLOCK_ID, 'orientation': 'y',
            })

    def _sand_landing_y(self, x, z, current_y, next_y):
        start = int(current_y - 1e-6)
        end = max(SAND_MIN_Y, int(next_y) - 1)
        for support_y in range(start, end - 1, -1):
            if (x, support_y, z) in self.world.blocks:
                return support_y + 1
        if next_y <= SAND_MIN_Y:
            return SAND_MIN_Y
        return None

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
    parser.add_argument('--max-players', type=int, default=DEFAULT_MAX_PLAYERS)
    args = parser.parse_args()
    server = MinecraftBuildServer(args.host, args.port, args.world, args.max_players)
    signal.signal(signal.SIGINT, lambda *_: server.shutdown())
    server.serve_forever()


if __name__ == '__main__':
    main()