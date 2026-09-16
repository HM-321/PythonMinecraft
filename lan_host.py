"""Embedded LAN server runtime used by the game client."""
from __future__ import annotations

import shutil
import socket
import threading
import time
from datetime import datetime
from pathlib import Path

from server import (
    DEFAULT_MAX_PLAYERS,
    DEFAULT_PORT,
    MinecraftBuildServer,
    ServerWorld,
    get_local_ip,
)


class EmbeddedLanHost:
    def __init__(self, world_path, port=DEFAULT_PORT, max_players=DEFAULT_MAX_PLAYERS):
        self.world_path = Path(world_path)
        self.port = int(port)
        self.max_players = int(max_players)
        self.server = MinecraftBuildServer(
            '0.0.0.0', self.port, str(self.world_path), self.max_players
        )
        self.thread = None
        self.error = None
        self._management_lock = threading.Lock()

    @property
    def address(self):
        return f'{get_local_ip()}:{self.port}'

    @property
    def player_count(self):
        with self.server.sessions_lock:
            return len(self.server.sessions)

    @property
    def running(self):
        return (
            self.thread is not None
            and self.thread.is_alive()
            and not self.server.stop_event.is_set()
        )

    def status(self):
        return {
            'address': self.address,
            'players': self.player_count,
            'max_players': self.max_players,
            'seed': self.server.world.seed,
            'generator': self.server.world.generator,
        }

    def start(self, timeout=3.0):
        self.error = None
        self.thread = threading.Thread(
            target=self._run,
            name='EmbeddedLanServer',
            daemon=True,
        )
        self.thread.start()
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.error is not None:
                raise RuntimeError(str(self.error)) from self.error
            if self.server.listener is not None:
                return
            time.sleep(0.02)
        self.stop()
        raise RuntimeError('LAN server did not start in time')

    def _run(self):
        try:
            self.server._serve_network()
        except Exception as exc:
            self.error = exc

    def save_now(self):
        with self._management_lock:
            self.server._save_world()

    def reset_world(self, use_template=False):
        """Back up and regenerate the hosted world."""
        with self._management_lock:
            self.server._save_world()
            path = self.server.world.path
            if path.exists():
                stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                backup_dir = path.parent / 'backups'
                backup_dir.mkdir(parents=True, exist_ok=True)

                backup = backup_dir / (
                    f'{path.stem}.before-lan-reset-{stamp}{path.suffix}'
                )
                shutil.copy2(path, backup)
                path.unlink()
            self.server.world = ServerWorld(path)
            if use_template:
                self.server.world.generator = 'template_v1'
                self.server.world.blocks = self.server.world._generated_template()
                self.server.world.generated_positions = set(
                    self.server.world.blocks
                )
                self.server.world.placed_blocks.clear()
                self.server.world.removed_blocks.clear()
            self.server._save_world()
            self.server._broadcast_world_reset()
            return {
                'seed': self.server.world.seed,
                'generator': self.server.world.generator,
            }

    def stop(self):
        self.server.shutdown()
        if self.thread and self.thread is not threading.current_thread():
            self.thread.join(timeout=2.0)
        self.thread = None


def port_is_available(port, host='0.0.0.0'):
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        probe.bind((host, int(port)))
        return True
    except OSError:
        return False
    finally:
        probe.close()
