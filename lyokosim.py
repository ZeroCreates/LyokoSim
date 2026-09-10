"""A small command-line Code Lyoko simulator with an Ollama game master."""

from __future__ import annotations

import argparse
import json
import os
import queue
import random
import re
import threading
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any


DEFAULT_WARRIORS = ("Aelita", "Ulrich", "Odd", "Yumi", "William")
DEFAULT_WARRIOR_CONFIG = [
    {"name": "Aelita", "role": "Tower and virtual-world specialist"},
    {"name": "Ulrich", "role": "Melee fighter and frontline defender"},
    {"name": "Odd", "role": "Ranged fighter and reconnaissance specialist"},
    {"name": "Yumi", "role": "Ranged fighter and telekinesis specialist"},
    {"name": "William", "role": "Heavy close-combat fighter"},
]
DEFAULT_SECTORS = ("Forest", "Desert", "Ice", "Mountain", "Carith")
DEFAULT_SECTOR_CONFIG = [
    {"name": "Forest", "towers": 10, "color": "#254638", "connections": ["Mountain", "Desert"]},
    {"name": "Desert", "towers": 10, "color": "#69502b", "connections": ["Forest", "Carith"]},
    {"name": "Ice", "towers": 10, "color": "#255062", "connections": ["Mountain", "Carith"]},
    {"name": "Mountain", "towers": 10, "color": "#38485b", "connections": ["Forest", "Ice"]},
    {"name": "Carith", "towers": 1, "color": "#563c54", "connections": ["Desert", "Ice"]},
]
DEFAULT_SECTOR_COLORS = {sector["name"]: sector["color"] for sector in DEFAULT_SECTOR_CONFIG}
NARRATOR_PROVIDERS = ("ollama", "openai", "none")
EPISODE_GUIDE = (
    "A usual Code Lyoko episode begins in the real world at Kadic Academy, where XANA activates "
    "a tower and creates a threat. Jeremy activates the supercomputer system, detects it in the lab, "
    "sends the warriors to Lyoko, and "
    "the team travels through the connected sectors while fighting XANA's monsters. The warriors "
    "must reach the activated tower; Aelita enters it and deactivates it, the real-world threat "
    "ends, and Jeremy uses Return to the Past to undo the damage. LyokoSim compresses that pattern: "
    "monitor presses are story beats, XANA's possessed tower is the target, movement follows the "
    "configured sector connections, and the mission ends when the configured monitor count is met."
)


class ConfigManager:
    """Creates and loads the user's editable LyokoSim JSON configuration."""

    def __init__(self, root: str | None = None) -> None:
        appdata = root or os.getenv("APPDATA") or os.path.expanduser("~/.config")
        self.directory = os.path.join(appdata, "LyokoSim")
        self.warriors_path = os.path.join(self.directory, "warriors.json")
        self.sectors_path = os.path.join(self.directory, "sectors.json")
        os.makedirs(self.directory, exist_ok=True)
        self._ensure_defaults()

    def _ensure_defaults(self) -> None:
        if not os.path.exists(self.warriors_path):
            self._write_json(self.warriors_path, DEFAULT_WARRIOR_CONFIG)
        if not os.path.exists(self.sectors_path):
            self._write_json(self.sectors_path, DEFAULT_SECTOR_CONFIG)
        else:
            self._migrate_legacy_defaults()

    def _migrate_legacy_defaults(self) -> None:
        try:
            with open(self.sectors_path, encoding="utf-8") as file:
                values = json.load(file)
        except (OSError, json.JSONDecodeError):
            return
        if isinstance(values, list) and tuple(values) == DEFAULT_SECTORS:
            self._write_json(self.sectors_path, DEFAULT_SECTOR_CONFIG)

    @staticmethod
    def _write_json(path: str, value: list[Any]) -> None:
        with open(path, "w", encoding="utf-8") as file:
            json.dump(value, file, indent=2)
            file.write("\n")

    @staticmethod
    def _read_warriors(path: str) -> tuple[dict[str, str], ...]:
        try:
            with open(path, encoding="utf-8") as file:
                values = json.load(file)
        except (OSError, json.JSONDecodeError) as error:
            raise RuntimeError(f"Could not read warriors configuration: {path}") from error
        if not isinstance(values, list) or not values:
            raise RuntimeError(f"Warriors configuration must be a non-empty JSON list: {path}")
        warriors: list[dict[str, str]] = []
        for value in values:
            if isinstance(value, str) and value.strip():
                value = {"name": value.strip(), "role": "Warrior"}
            if not isinstance(value, dict):
                raise RuntimeError("Each warrior must be a name string or an object with name and role.")
            name = value.get("name")
            role = value.get("role", "Warrior")
            if not isinstance(name, str) or not name.strip() or not isinstance(role, str) or not role.strip():
                raise RuntimeError("Each warrior needs a non-empty name and role.")
            warriors.append({"name": name.strip(), "role": role.strip()})
        names = tuple(warrior["name"] for warrior in warriors)
        if len(set(names)) != len(names):
            raise RuntimeError(f"Warriors configuration contains duplicate names: {path}")
        return tuple(warriors)

    def load(self) -> tuple[tuple[dict[str, str], ...], tuple[dict[str, Any], ...]]:
        warriors = self._read_warriors(self.warriors_path)
        try:
            with open(self.sectors_path, encoding="utf-8") as file:
                values = json.load(file)
        except (OSError, json.JSONDecodeError) as error:
            raise RuntimeError(f"Could not read sectors configuration: {self.sectors_path}") from error
        if not isinstance(values, list) or not values:
            raise RuntimeError(f"Sectors configuration must be a non-empty JSON list: {self.sectors_path}")
        sectors: list[dict[str, Any]] = []
        for value in values:
            if isinstance(value, str) and value.strip():
                value = {"name": value.strip(), "towers": 10, "color": DEFAULT_SECTOR_COLORS.get(value.strip(), "#344b3b"), "connections": []}
            if not isinstance(value, dict):
                raise RuntimeError("Each sector must be a name string or an object with name, towers, and connections.")
            name = value.get("name")
            towers = value.get("towers", 10)
            color = value.get("color", DEFAULT_SECTOR_COLORS.get(name, "#344b3b"))
            connections = value.get("connections", [])
            if not isinstance(name, str) or not name.strip() or not isinstance(towers, int) or towers < 1:
                raise RuntimeError("Each sector needs a non-empty name and a positive integer towers value.")
            if not isinstance(color, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
                raise RuntimeError(f"Color for {name} must be a hex color such as #254638.")
            if not isinstance(connections, list) or any(not isinstance(item, str) or not item.strip() for item in connections):
                raise RuntimeError(f"Connections for {name} must be a list of sector names.")
            sectors.append({"name": name.strip(), "towers": towers, "color": color, "connections": [item.strip() for item in connections]})
        names = tuple(sector["name"] for sector in sectors)
        if len(set(names)) != len(names):
            raise RuntimeError("Sectors configuration contains duplicate names.")
        return warriors, tuple(sectors)

    def changed(self, timestamps: tuple[float, float]) -> bool:
        return (os.path.getmtime(self.warriors_path), os.path.getmtime(self.sectors_path)) != timestamps

    def timestamps(self) -> tuple[float, float]:
        return os.path.getmtime(self.warriors_path), os.path.getmtime(self.sectors_path)


@dataclass
class Warrior:
    name: str
    role: str = "Warrior"
    virtualized: bool = False
    location: str | None = None
    health: int = 100


@dataclass
class LyokoState:
    tower_active: bool = False
    monitored: bool = False
    return_requested: bool = False
    tick: int = 0
    story_progress: int = 0
    story_length: int = 0
    mission_successful: bool = False
    xana_active: bool = True
    system_integrity: int = 100
    tower_compromised: bool = False
    xana_attacks: int = 0
    last_xana_event: str | None = None
    possessed_towers: set[str] = field(default_factory=set)
    active_tower: str | None = None
    tower_connections_map: dict[str, list[str]] = field(default_factory=dict)
    warriors: dict[str, Warrior] = field(default_factory=dict)

    def snapshot(self) -> dict[str, Any]:
        return {
            "tower_active": self.tower_active,
            "monitored": self.monitored,
            "return_requested": self.return_requested,
            "tick": self.tick,
            "story_progress": self.story_progress,
            "story_length": self.story_length,
            "mission_successful": self.mission_successful,
            "xana_active": self.xana_active,
            "system_integrity": self.system_integrity,
            "tower_compromised": self.tower_compromised,
            "xana_attacks": self.xana_attacks,
            "last_xana_event": self.last_xana_event,
            "possessed_towers": sorted(self.possessed_towers),
            "active_tower": self.active_tower,
            "tower_connections": self.tower_connections_map,
            "warriors": {
                name: {
                    "virtualized": warrior.virtualized,
                    "role": warrior.role,
                    "location": warrior.location,
                    "health": warrior.health,
                }
                for name, warrior in self.warriors.items()
            },
        }


class SimulationError(ValueError):
    """Raised when a command cannot be performed in the current state."""


class LyokoSimulator:
    def __init__(self, config: ConfigManager | None = None) -> None:
        self.config = config or ConfigManager()
        self.warrior_configs, self.sector_configs = self.config.load()
        self.warrior_names = tuple(warrior["name"] for warrior in self.warrior_configs)
        self.warrior_roles = {warrior["name"]: warrior["role"] for warrior in self.warrior_configs}
        self.sectors = tuple(sector["name"] for sector in self.sector_configs)
        self.sector_colors = {sector["name"]: sector["color"] for sector in self.sector_configs}
        self.state = self._new_state()
        self.state.tower_connections_map = self.tower_connections()
        self._config_timestamps = self.config.timestamps()
        self.log: list[str] = []

    def _new_state(self, return_requested: bool = False) -> LyokoState:
        state = LyokoState(
            return_requested=return_requested,
            story_length=random.randint(3, 5),
            warriors={name: Warrior(name, self.warrior_roles[name]) for name in self.warrior_names},
        )
        state.tower_connections_map = self.tower_connections()
        return state

    def reload_config(self) -> bool:
        """Reload edited files while preserving state for names that still exist."""
        if not self.config.changed(self._config_timestamps):
            return False
        warrior_configs, sector_configs = self.config.load()
        current = self.state.warriors
        updated_warriors: dict[str, Warrior] = {}
        for warrior_config in warrior_configs:
            warrior = current.get(warrior_config["name"], Warrior(warrior_config["name"]))
            warrior.role = warrior_config["role"]
            updated_warriors[warrior.name] = warrior
        self.state.warriors = updated_warriors
        self.warrior_configs = warrior_configs
        self.warrior_names = tuple(warrior["name"] for warrior in warrior_configs)
        self.warrior_roles = {warrior["name"]: warrior["role"] for warrior in warrior_configs}
        self.sector_configs = sector_configs
        self.sectors = tuple(sector["name"] for sector in sector_configs)
        self.sector_colors = {sector["name"]: sector["color"] for sector in sector_configs}
        self.state.tower_connections_map = self.tower_connections()
        self._config_timestamps = self.config.timestamps()
        self.log.append("Configuration reloaded from AppData.")
        return True

    def narrator_context(self) -> dict[str, Any]:
        """Return the complete authoritative data set for an AI narrator."""
        virtualised_warriors = [
            {
                "name": warrior.name,
                "role": warrior.role,
                "sector": warrior.location,
                "health": warrior.health,
            }
            for warrior in self.state.warriors.values()
            if warrior.virtualized
        ]
        return {
            "configuration": {
                "warriors": self.warrior_configs,
                "sectors": self.sector_configs,
                "config_directory": self.config.directory,
            },
            "episode_guide": EPISODE_GUIDE,
            "objective": {
                "target_tower": self.state.active_tower,
                "target_sector": self.state.active_tower.rsplit(" Tower ", 1)[0] if self.state.active_tower else None,
            },
            "state": self.state.snapshot(),
            "virtualised_warriors": virtualised_warriors,
            "mission_log": self.log[-20:],
        }

    def activate_system(self) -> str:
        if self.state.return_requested:
            raise SimulationError("The timeline has already been reset.")
        if self.state.mission_successful:
            raise SimulationError("The mission is complete; deactivate the tower before starting another mission.")
        if self.state.tower_active:
            return "System is already active."
        self.state.tower_active = True
        message = "System activated. Lyoko interface is online. XANA controls Lyoko towers."
        self.log.append(message)
        return message

    def activate_tower(self) -> str:
        """Compatibility alias; Jeremy activates the system, not a Lyoko tower."""
        return self.activate_system()

    def virtualize(self, names: list[str], sector: str) -> str:
        if not self.state.tower_active:
            raise SimulationError("Activate a tower before virtualising warriors.")
        if sector not in self.sectors:
            raise SimulationError(f"Unknown sector: {sector}. Choose from {', '.join(self.sectors)}.")
        if not names:
            raise SimulationError("Select at least one warrior.")
        selected = []
        for name in names:
            if name not in self.state.warriors:
                raise SimulationError(f"Unknown warrior: {name}.")
            warrior = self.state.warriors[name]
            if warrior.virtualized:
                raise SimulationError(f"{name} is already virtualised.")
            warrior.virtualized = True
            warrior.location = sector
            warrior.health = 100
            selected.append(name)
        message = f"Virtualised {', '.join(selected)} to {sector}."
        self.log.append(message)
        return message

    def monitor(self) -> str:
        if not self.state.tower_active:
            raise SimulationError("There is no active tower to monitor.")
        if self.state.mission_successful:
            raise SimulationError("The mission is complete; the AI must deactivate the tower.")
        self.state.monitored = True
        self.state.tick += 1
        self.state.story_progress = min(self.state.story_progress + 1, self.state.story_length)
        active = [
            f"{warrior.name} ({warrior.location}, {warrior.health}%)"
            for warrior in self.state.warriors.values()
            if warrior.virtualized
        ]
        message = "Monitoring tick " + str(self.state.tick) + ": " + (
            ", ".join(active) if active else "no warriors on Lyoko"
        )
        if self.state.xana_active:
            message += "\n" + self.xana_attack()
        if self.state.story_progress >= self.state.story_length and self.state.system_integrity > 0:
            self.state.mission_successful = True
            message += f"\nMission objective complete after {self.state.story_progress} monitoring cycles. Awaiting tower deactivation."
        self.log.append(message)
        return message

    def deactivate_tower(self) -> str:
        """Deactivate the active tower after the mission has succeeded."""
        if not self.state.tower_active:
            return "Tower is already offline."
        if not self.state.mission_successful:
            raise SimulationError("The mission is not successful yet; keep monitoring Lyoko.")
        self.state.tower_active = False
        self.state.active_tower = None
        self.state.possessed_towers.clear()
        message = "Mission successful. Tower deactivated and Lyoko access closed."
        self.log.append(message)
        return message

    def xana_attack(self) -> str:
        """Apply one deterministic XANA attack; narration is handled separately."""
        if not self.state.tower_active:
            raise SimulationError("XANA cannot attack while the tower is offline.")
        self.state.system_integrity = max(0, self.state.system_integrity - 10)
        self.state.xana_attacks += 1
        tower = self._possess_random_tower()
        if self.state.system_integrity <= 0:
            self.state.tower_compromised = True
            self.state.tower_active = False
            event = f"XANA activated {tower} and compromised the system tower. Tower offline."
        else:
            event = f"XANA activated {tower} and attacked the real world. System integrity: {self.state.system_integrity}%."
        self.state.last_xana_event = event
        self.log.append(event)
        return event

    def _possess_random_tower(self) -> str:
        if self.state.active_tower is not None:
            return self.state.active_tower
        towers = [
            f"{sector['name']} Tower {number}"
            for sector in self.sector_configs
            for number in range(1, sector["towers"] + 1)
        ]
        available = [tower for tower in towers if tower != self.state.active_tower]
        tower = random.choice(available or towers)
        self.state.possessed_towers = {tower}
        self.state.active_tower = tower
        return tower

    def tower_connections(self) -> dict[str, list[str]]:
        """Return links carried by even-numbered towers in each sector."""
        links: dict[str, list[str]] = {}
        for sector in self.sector_configs:
            destinations = [name for name in sector["connections"] if name in self.sectors]
            for number in range(2, sector["towers"] + 1, 2):
                links[f"{sector['name']} Tower {number}"] = destinations
        return links

    def move_warriors(self, names: list[str], sector: str) -> str:
        """Move virtualised warriors one connected sector closer to XANA's tower."""
        if not self.state.tower_active:
            raise SimulationError("The tower is offline; warriors cannot move on Lyoko.")
        if not self.state.active_tower:
            raise SimulationError("There is no active XANA tower to target yet.")
        if not names:
            raise SimulationError("Select at least one warrior to move.")
        if sector not in self.sectors:
            raise SimulationError(f"Unknown sector: {sector}. Choose from {', '.join(self.sectors)}.")
        target_sector = self.state.active_tower.rsplit(" Tower ", 1)[0]
        for name in names:
            if name not in self.state.warriors:
                raise SimulationError(f"Unknown warrior: {name}.")
            warrior = self.state.warriors[name]
            if not warrior.virtualized:
                raise SimulationError(f"{name} is not virtualised.")
            if warrior.location is None:
                raise SimulationError(f"{name} has no Lyoko location.")
            if sector not in self._connected_sectors(warrior.location):
                raise SimulationError(f"{sector} is not connected to {warrior.location}.")
            if not self._moves_toward(warrior.location, sector, target_sector):
                raise SimulationError(f"{name} must move toward target tower {self.state.active_tower}.")
        for name in names:
            self.state.warriors[name].location = sector
        message = f"Moved {', '.join(names)} toward target tower {self.state.active_tower} via {sector}."
        self.log.append(message)
        return message

    def _connected_sectors(self, sector: str) -> list[str]:
        return [item for config in self.sector_configs if config["name"] == sector for item in config["connections"] if item in self.sectors]

    def _sector_distance(self, start: str, target: str) -> int | None:
        if start == target:
            return 0
        pending = [(start, 0)]
        visited = {start}
        while pending:
            current, distance = pending.pop(0)
            for neighbor in self._connected_sectors(current):
                if neighbor == target:
                    return distance + 1
                if neighbor not in visited:
                    visited.add(neighbor)
                    pending.append((neighbor, distance + 1))
        return None

    def _moves_toward(self, current: str, destination: str, target: str) -> bool:
        if current == target:
            return destination == target
        current_distance = self._sector_distance(current, target)
        destination_distance = self._sector_distance(destination, target)
        return current_distance is not None and destination_distance is not None and destination_distance < current_distance

    def devirtualize(self, names: list[str]) -> str:
        if not names:
            raise SimulationError("Select at least one warrior.")
        selected = []
        for name in names:
            if name not in self.state.warriors:
                raise SimulationError(f"Unknown warrior: {name}.")
            warrior = self.state.warriors[name]
            if not warrior.virtualized:
                raise SimulationError(f"{name} is not virtualised.")
            warrior.virtualized = False
            warrior.location = None
            selected.append(name)
        message = f"Devirtualised {', '.join(selected)}."
        self.log.append(message)
        return message

    def return_to_past(self) -> str:
        self.state = self._new_state(return_requested=True)
        message = "Return to the past initiated. Simulation state has been reset."
        self.log.append(message)
        return message


class OllamaJeremy:
    """Uses Ollama's local chat API to narrate the operator's commands."""

    def __init__(self, model: str | None = None, host: str | None = None) -> None:
        self.model = model or os.getenv("LYOKO_OLLAMA_MODEL", "llama3.2")
        self.host = (host or os.getenv("OLLAMA_HOST", "http://localhost:11434")).rstrip("/")
        self.history: list[dict[str, str]] = []
        self._lock = threading.Lock()

    def reply(self, simulator: LyokoSimulator, command: str, outcome: str) -> str:
        system_message = (
            "You are the continuing Code Lyoko supercomputer story narrator speaking to Jeremy Belpois. "
            "Jeremy activates the system, never a Lyoko tower. XANA alone activates and possesses "
            "Lyoko towers. Jeremy controls the mission, but you may request warrior movement with one exact action "
            "token when a virtualised warrior can advance toward the active XANA tower: "
            "[MOVE Warrior Name, Other Name TO Sector]. Use names and sectors exactly as supplied. "
            "Only request an adjacent sector that reduces distance to the target tower; never move "
            "away from it, and never request movement when no active tower exists. The simulator will "
            "validate and execute the request. Never choose other commands, override Jeremy, or return JSON. "
            f"{EPISODE_GUIDE} Continue directly from the previous scene. In three concise "
            "in-world lines, report what is happening on Lyoko, include character reactions when useful, "
            "and make XANA's tower activity and real-world threat clear. Do not reset or contradict the "
            "established story. The mission has exactly the configured number of monitor presses, "
            "between 3 and 5. Treat each monitor press as one story beat. Never ask for or invent "
            "more monitor presses than story_length. When story_progress reaches story_length and "
            "mission_successful is true, narrate a clear mission victory, declare the story won, "
            "and end your reply with the exact token [DEACTIVATE_TOWER]. Otherwise do not use that token."
            "Always use the authoritative mission data provided by the simulator. Do not invent warrior names, roles, sectors, or tower names. Do not invent or contradict the simulator's state. " \
            "The simulator's state is authoritative and includes the active tower, virtualised warriors, their locations, health, and the current story progress. Use this data to inform your narration and any movement requests.This Is Provided in JSON format:\n"
            f"{json.dumps(simulator.narrator_context())}"
        )
        prompt = {
            "role": "user",
            "content": f"Jeremy's latest command: {command}\nDeterministic outcome: {outcome}",
        }
        payload = {
            "model": self.model,
            "messages": [{"role": "system", "content": system_message}, *self.history[-10:], prompt],
            "stream": False,
        }
        request_data = json.dumps(payload).encode("utf-8")
        http_request = urllib.request.Request(
            f"{self.host}/api/chat",
            data=request_data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with self._lock:
            try:
                with urllib.request.urlopen(http_request, timeout=60) as response:
                    result = json.loads(response.read().decode("utf-8"))
            except (urllib.error.URLError, TimeoutError) as error:
                raise RuntimeError(
                    f"Could not reach Ollama at {self.host}. Start Ollama and pull {self.model}."
                ) from error
            try:
                reply = result["message"]["content"]
                if not isinstance(reply, str) or not reply.strip():
                    raise ValueError("empty reply")
                reply = reply.strip()
            except (KeyError, TypeError, ValueError) as error:
                raise RuntimeError("Ollama returned an empty or invalid reply.") from error
            self.history.extend([prompt, {"role": "assistant", "content": reply}])
            self.history = self.history[-10:]
            return reply


class OpenAIJeremy:
    """Uses OpenAI's chat-completions API for mission narration."""

    def __init__(self, model: str | None = None, api_key: str | None = None) -> None:
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is not set.")
        self.history: list[dict[str, str]] = []
        self._lock = threading.Lock()

    def reply(self, simulator: LyokoSimulator, command: str, outcome: str) -> str:
        system_message = (
            "You are the Code Lyoko supercomputer speaking to Jeremy Belpois. "
            "Jeremy activates the system, never a Lyoko tower. XANA alone activates and possesses "
            "Lyoko towers. Jeremy controls the mission, but you may request warrior movement with one exact action "
            "token when a virtualised warrior can advance toward the active XANA tower: "
            "[MOVE Warrior Name, Other Name TO Sector]. Use names and sectors exactly as supplied. "
            "Only request an adjacent sector that reduces distance to the target tower; never move "
            "away from it, and never request movement when no active tower exists. The simulator validates it. "
            "Never choose other commands or return JSON. "
            f"{EPISODE_GUIDE} "
            "Continue the established story in three concise in-world lines. Explain what is happening "
            "on Lyoko, include character reactions when useful, and make XANA's tower activity and "
            "real-world threat clear. Never choose commands or contradict prior events. The mission has "
            "exactly the configured story_length of 3 to 5 monitor presses; each press is one story beat. "
            "Never request more presses than story_length. When mission_successful is true, narrate a "
            "clear mission victory and end your reply with the exact token [DEACTIVATE_TOWER]."
        )
        user_message = (
            "Complete authoritative mission data, including every virtualised warrior: "
            f"{json.dumps(simulator.narrator_context())}\n"
            f"Command executed by Jeremy: {command}\n"
            f"Deterministic outcome: {outcome}"
        )
        user_prompt = {"role": "user", "content": user_message}
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_message},
                *self.history[-10:],
                user_prompt,
            ],
            "temperature": 0.8,
        }
        request = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )
        with self._lock:
            try:
                with urllib.request.urlopen(request, timeout=60) as response:
                    result = json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as error:
                detail = ""
                try:
                    error_body = json.loads(error.read().decode("utf-8"))
                    detail = error_body.get("error", {}).get("message", "")
                except (OSError, UnicodeDecodeError, json.JSONDecodeError, AttributeError):
                    pass
                if error.code == 429:
                    message = "OpenAI rate limit or quota exceeded. Check API usage, billing, and limits"
                    if detail:
                        message += f": {detail}"
                    message += ". You can use --provider ollama while this is resolved."
                    raise RuntimeError(message) from error
                raise RuntimeError(f"OpenAI request failed (HTTP {error.code}){': ' + detail if detail else ''}.") from error
            except (urllib.error.URLError, TimeoutError) as error:
                raise RuntimeError(f"OpenAI request failed: {error}") from error
            try:
                reply = result["choices"][0]["message"]["content"]
                if not isinstance(reply, str) or not reply.strip():
                    raise ValueError("empty reply")
                reply = reply.strip()
            except (KeyError, IndexError, TypeError, ValueError) as error:
                raise RuntimeError("OpenAI returned an empty or invalid reply.") from error
            self.history.extend([user_prompt, {"role": "assistant", "content": reply}])
            self.history = self.history[-10:]
            return reply


class NoNarrator:
    """Offline provider used when no language model is configured."""

    def reply(self, simulator: LyokoSimulator, command: str, outcome: str) -> str:
        return "No AI narrator configured. Deterministic systems report the outcome above."


class TextToSpeech:
    """Speak system and narrator messages from one dedicated worker thread."""

    def __init__(self, enabled: bool = True, rate: int = 170) -> None:
        self.enabled = enabled
        self.rate = rate
        self.error: str | None = None
        self._messages: queue.Queue[str | None] = queue.Queue()
        self._worker: threading.Thread | None = None
        if self.enabled:
            self._worker = threading.Thread(target=self._run, daemon=True, name="LyokoSim-TTS")
            self._worker.start()

    def speak_async(self, text: str) -> None:
        if not self.enabled or not text.strip():
            return
        self._messages.put(text)

    def _run(self) -> None:
        try:
            import pyttsx3

            engine = pyttsx3.init()
            engine.setProperty("rate", self.rate)
            while True:
                text = self._messages.get()
                if text is None:
                    return
                engine.say(re.sub(r"\[[^\]]+\]", "", text).strip())
                engine.runAndWait()
        except Exception as error:  # TTS is an optional enhancement; text output remains authoritative.
            self.error = str(error)


def apply_narrator_actions(simulator: LyokoSimulator, reply: str) -> str:
    """Execute valid narrator movement requests and report their deterministic outcomes."""
    outcomes = []
    for match in re.finditer(r"\[MOVE (.+?) TO ([^\]]+)\]", reply):
        names = [name.strip() for name in match.group(1).split(",") if name.strip()]
        sector = match.group(2).strip()
        try:
            outcomes.append(simulator.move_warriors(names, sector))
        except SimulationError as error:
            outcomes.append(f"Movement request rejected: {error}")
    if outcomes:
        return reply + "\n" + "\n".join(outcomes)
    return reply


def create_narrator(provider: str, model: str | None = None, host: str | None = None):
    if provider == "ollama":
        return OllamaJeremy(model, host)
    if provider == "openai":
        return OpenAIJeremy(model)
    if provider == "none":
        return NoNarrator()
    raise ValueError(f"Unknown narrator provider: {provider}")


def print_status(simulator: LyokoSimulator) -> None:
    print(json.dumps(simulator.state.snapshot(), indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="Code Lyoko simulator with XANA and selectable narration.")
    parser.add_argument("--provider", choices=NARRATOR_PROVIDERS, default=os.getenv("LYOKO_PROVIDER", "ollama"))
    parser.add_argument("--model", help="Ollama model name; defaults to LYOKO_OLLAMA_MODEL or llama3.2")
    parser.add_argument("--host", help="Ollama URL; defaults to OLLAMA_HOST or localhost:11434")
    parser.add_argument("--no-tts", action="store_true", help="Disable spoken narrator replies")
    args = parser.parse_args()
    simulator = LyokoSimulator()
    speaker = TextToSpeech(enabled=not args.no_tts)
    try:
        jeremy = create_narrator(args.provider, args.model, args.host)
    except RuntimeError as error:
        print(f"Narrator disabled: {error}")
        jeremy = NoNarrator()
    print("LyokoSim online. You are Jeremy. Type 'help' for commands, 'quit' to exit.")
    while True:
        try:
            command = input("lyoko> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if command in {"quit", "exit"}:
            break
        if command == "help":
            print("activate_system | monitor | xana | virtualize <names> <sector> | devirtualize <names>")
            print("past | status | quit")
            continue
        try:
            outcome = None
            simulator.reload_config()
            if command == "status":
                print_status(simulator)
            elif command in {"activate", "activate_system"}:
                outcome = simulator.activate_system()
            elif command == "monitor":
                outcome = simulator.monitor()
            elif command == "xana":
                outcome = simulator.xana_attack()
            elif command == "past":
                outcome = simulator.return_to_past()
            elif command.startswith("virtualize ") or command.startswith("devirtualize "):
                parts = command.split()
                names = parts[1:-1] if parts[0] == "virtualize" else parts[1:]
                if parts[0] == "virtualize":
                    outcome = simulator.virtualize(names, parts[-1])
                else:
                    outcome = simulator.devirtualize(names)
            else:
                print("Unknown command. Type 'help'.")
            if outcome:
                print(outcome)
                speaker.speak_async(outcome)
                try:
                    reply = apply_narrator_actions(simulator, jeremy.reply(simulator, command, outcome))
                    print(f"{args.provider}: {reply}")
                    speaker.speak_async(reply)
                finally:
                    if simulator.state.mission_successful and simulator.state.tower_active:
                        print(simulator.deactivate_tower())
        except (SimulationError, RuntimeError) as error:
            print(f"Error: {error}")


if __name__ == "__main__":
    main()