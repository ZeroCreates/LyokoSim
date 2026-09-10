"""Desktop control room UI for LyokoSim."""

from __future__ import annotations

import argparse
import os
import queue
import threading
import tkinter as tk
from tkinter import messagebox, ttk

from lyokosim import LyokoSimulator, SimulationError, TextToSpeech, apply_narrator_actions, create_narrator


class LyokoControlRoom(tk.Tk):
    COLORS = {
        "bg": "#0b1118",
        "panel": "#121c27",
        "panel_light": "#1b2a37",
        "line": "#314555",
        "text": "#d9e7ed",
        "muted": "#88a2ae",
        "cyan": "#5fe0df",
        "orange": "#ffb45c",
        "green": "#8bd17c",
        "red": "#ff7373",
    }
    DEFAULT_SECTOR_SHAPES = {
        "Forest": (80, 130, 285, 310),
        "Mountain": (315, 70, 520, 250),
        "Ice": (550, 125, 755, 305),
        "Desert": (155, 350, 380, 525),
        "Carith": (450, 350, 680, 530),
    }

    def __init__(self, model: str | None = None, host: str | None = None, provider: str = "ollama") -> None:
        super().__init__()
        self.title("LyokoSim // Jeremy Control Room")
        self.geometry("1220x780")
        self.minsize(1050, 680)
        self.configure(bg=self.COLORS["bg"])
        self.simulator = LyokoSimulator()
        self.provider = provider
        self.speaker = TextToSpeech()
        try:
            self.jeremy = create_narrator(provider, model, host)
        except RuntimeError as error:
            self.jeremy = create_narrator("none")
            self.startup_error = str(error)
        else:
            self.startup_error = None
        self.reply_queue: queue.Queue[tuple[str, str]] = queue.Queue()
        self.selected_sector = tk.StringVar(value=self.simulator.sectors[0])
        self.selected_warriors: dict[str, tk.BooleanVar] = {}
        self.windows: dict[str, tk.Toplevel] = {}
        self.known_virtualized: set[str] = set()
        self.warrior_card_vars: dict[str, dict[str, tk.StringVar]] = {}
        self.virtualized_list: tk.Listbox | None = None
        self.sector_menu: ttk.OptionMenu | None = None
        self.map_canvas: tk.Canvas | None = None
        self.warrior_frame: ttk.Frame | None = None
        self.sector_menu_frame: ttk.Frame | None = None
        self.log_text: tk.Text | None = None
        self.dialogue_log_path = os.path.join(self.simulator.config.directory, "dialogue.log")
        self.dialogue_history: list[str] = []
        self.status_text = tk.StringVar(value="SYSTEMS STANDBY")
        self.integrity_text = tk.StringVar(value="SYSTEM INTEGRITY 100%")
        self._build_styles()
        self._build_layout()
        self._rebuild_config_controls()
        self._draw_map()
        self.after(100, self._drain_replies)
        self.after(1000, self._refresh_config)
        self.after(250, self._sync_warrior_windows)

    def _build_styles(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Panel.TFrame", background=self.COLORS["panel"])
        style.configure("Menu.TFrame", background="#07151c")
        style.configure("Panel.TLabel", background=self.COLORS["panel"], foreground=self.COLORS["text"])
        style.configure("Muted.TLabel", background=self.COLORS["panel"], foreground=self.COLORS["muted"])
        style.configure("Title.TLabel", background=self.COLORS["panel"], foreground=self.COLORS["cyan"], font=("Consolas", 18, "bold"))
        style.configure("Section.TLabel", background=self.COLORS["panel"], foreground=self.COLORS["cyan"], font=("Segoe UI", 10, "bold"))
        style.configure("Menu.TButton", background="#102b35", foreground=self.COLORS["cyan"], padding=(12, 11), font=("Consolas", 10, "bold"))
        style.configure("Action.TButton", background=self.COLORS["panel_light"], foreground=self.COLORS["text"], padding=(12, 8), font=("Consolas", 10, "bold"))
        style.configure("Danger.TButton", background="#3a1d2a", foreground=self.COLORS["red"], padding=(12, 9), font=("Consolas", 10, "bold"))
        style.configure("TCheckbutton", background=self.COLORS["panel"], foreground=self.COLORS["text"], font=("Consolas", 10))
        style.configure("TMenubutton", background=self.COLORS["panel_light"], foreground=self.COLORS["cyan"], font=("Consolas", 10))
        style.map("Action.TButton", background=[("active", "#2a4552")])
        style.map("Menu.TButton", background=[("active", "#1b5360")])
        style.map("Danger.TButton", background=[("active", "#5d2636")])

    def _build_layout(self) -> None:
        self.geometry("520x570")
        self.minsize(460, 420)
        header = ttk.Frame(self, style="Menu.TFrame", padding=(28, 24))
        header.pack(fill="x")
        ttk.Label(header, text="LYOKOSIM", style="Title.TLabel").pack(anchor="w")
        ttk.Label(header, text="JEREMY // SUPERCOMPUTER INTERFACE", style="Muted.TLabel").pack(anchor="w", pady=(5, 0))
        ttk.Label(header, textvariable=self.status_text, style="Section.TLabel").pack(anchor="w", pady=(18, 0))
        ttk.Label(header, textvariable=self.integrity_text, style="Muted.TLabel").pack(anchor="w", pady=(3, 0))
        menu = ttk.Frame(self, style="Menu.TFrame", padding=(28, 6, 28, 24))
        menu.pack(fill="both", expand=True)
        ttk.Label(menu, text="OPEN INTERFACE MODULE", style="Section.TLabel").pack(anchor="w", pady=(8, 10))
        for title, key, command in (
            ("MISSION CONTROL", "control", self._open_control_window),
            ("LIVE LYOKO MAP", "map", self._open_map_window),
            ("VIRTUALISATION DECK", "virtualize", self._open_virtualize_window),
            ("VIRTUALISED WARRIORS", "warriors", self._open_virtualized_window),
            ("SUPERCOMPUTER DIALOGUE", "dialogue", self._open_dialogue_window),
        ):
            ttk.Button(menu, text=f"{title}  //  OPEN", command=command, style="Menu.TButton").pack(fill="x", pady=4)
        ttk.Separator(menu).pack(fill="x", pady=14)
        ttk.Button(menu, text="EXIT LYOKOSIM", command=self.destroy, style="Danger.TButton").pack(fill="x", pady=4)
        self._open_control_window()
        self._log("SYSTEM", f"Control room online. Configuration: {self.simulator.config.directory}")
        if self.startup_error:
            self._log("SYSTEM", f"Narrator fallback: {self.startup_error}")

    def _new_window(self, key: str, title: str, geometry: str) -> tk.Toplevel | None:
        existing = self.windows.get(key)
        if existing is not None and existing.winfo_exists():
            existing.deiconify()
            existing.lift()
            return None
        window = tk.Toplevel(self)
        window.title(f"LyokoSim // {title}")
        window.geometry(geometry)
        window.configure(bg=self.COLORS["bg"])
        window.protocol("WM_DELETE_WINDOW", lambda: self._close_window(key))
        self.windows[key] = window
        return window

    def _close_window(self, key: str) -> None:
        window = self.windows.pop(key, None)
        if window is not None and window.winfo_exists():
            window.destroy()
        if key == "map":
            self.map_canvas = None
        elif key == "virtualize":
            self.warrior_frame = None
            self.sector_menu_frame = None
            self.sector_menu = None
        elif key == "dialogue":
            self.log_text = None
        elif key == "warriors":
            self.virtualized_list = None
        elif key.startswith("warrior:"):
            self.warrior_card_vars.pop(key.split(":", 1)[1], None)

    def _open_control_window(self) -> None:
        window = self._new_window("control", "Mission Control", "390x430")
        if window is None:
            return
        content = ttk.Frame(window, style="Panel.TFrame", padding=22)
        content.pack(fill="both", expand=True)
        ttk.Label(content, text="MISSION CONTROL", style="Title.TLabel").pack(anchor="w")
        ttk.Label(content, text="COMMAND DECK // EARTH SIDE", style="Muted.TLabel").pack(anchor="w", pady=(4, 20))
        for text, command in (("ACTIVATE SYSTEM", self._activate), ("MONITOR WARRIORS", self._monitor), ("TRIGGER XANA ATTACK", self._xana_attack), ("RETURN TO THE PAST", self._return_to_past)):
            ttk.Button(content, text=text, command=command, style="Action.TButton").pack(fill="x", pady=5)
        ttk.Separator(content).pack(fill="x", pady=16)
        ttk.Label(content, text="SYSTEM STATUS", style="Section.TLabel").pack(anchor="w")
        ttk.Label(content, textvariable=self.status_text, style="Muted.TLabel").pack(anchor="w", pady=(6, 2))
        ttk.Label(content, textvariable=self.integrity_text, style="Muted.TLabel").pack(anchor="w")

    def _open_map_window(self) -> None:
        window = self._new_window("map", "Live Lyoko Map", "900x650")
        if window is None:
            return
        frame = ttk.Frame(window, style="Panel.TFrame", padding=14)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="LYOKO // SECTOR NETWORK", style="Title.TLabel").pack(anchor="w", pady=(0, 8))
        self.map_canvas = tk.Canvas(frame, bg="#07151c", highlightthickness=1, highlightbackground=self.COLORS["cyan"])
        self.map_canvas.pack(fill="both", expand=True)
        self.map_canvas.bind("<Configure>", lambda _event: self._draw_map())
        self._draw_map()

    def _open_virtualize_window(self) -> None:
        window = self._new_window("virtualize", "Virtualisation Deck", "430x600")
        if window is None:
            return
        content = ttk.Frame(window, style="Panel.TFrame", padding=22)
        content.pack(fill="both", expand=True)
        ttk.Label(content, text="VIRTUALISATION DECK", style="Title.TLabel").pack(anchor="w")
        ttk.Label(content, text="SELECT WARRIORS // DESTINATION SECTOR", style="Muted.TLabel").pack(anchor="w", pady=(4, 16))
        self.warrior_frame = ttk.Frame(content, style="Panel.TFrame")
        self.warrior_frame.pack(fill="x")
        ttk.Label(content, text="TARGET SECTOR", style="Section.TLabel").pack(anchor="w", pady=(22, 5))
        self.sector_menu_frame = ttk.Frame(content, style="Panel.TFrame")
        self.sector_menu_frame.pack(fill="x")
        ttk.Button(content, text="VIRTUALISE SELECTED", command=self._virtualize, style="Action.TButton").pack(fill="x", pady=(14, 5))
        ttk.Button(content, text="DEVIRTUALISE SELECTED", command=self._devirtualize, style="Action.TButton").pack(fill="x", pady=5)
        self._rebuild_config_controls()

    def _open_virtualized_window(self) -> None:
        window = self._new_window("warriors", "Virtualised Warriors", "420x500")
        if window is None:
            return
        frame = ttk.Frame(window, style="Panel.TFrame", padding=20)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="VIRTUALISED WARRIORS", style="Title.TLabel").pack(anchor="w")
        ttk.Label(frame, text="ENTITY REGISTRY // OPEN A LIVE CARD", style="Muted.TLabel").pack(anchor="w", pady=(4, 14))
        self.virtualized_list = tk.Listbox(
            frame,
            bg="#061118",
            fg=self.COLORS["cyan"],
            selectbackground="#1b5360",
            selectforeground=self.COLORS["text"],
            relief="flat",
            highlightthickness=1,
            highlightbackground=self.COLORS["line"],
            font=("Consolas", 11),
            activestyle="none",
        )
        self.virtualized_list.pack(fill="both", expand=True)
        self.virtualized_list.bind("<Double-Button-1>", lambda _event: self._open_selected_warrior_card())
        ttk.Button(frame, text="OPEN SELECTED ENTITY CARD", command=self._open_selected_warrior_card, style="Action.TButton").pack(fill="x", pady=(12, 4))
        ttk.Label(frame, text="Cards update with movement, health, and mission state.", style="Muted.TLabel").pack(anchor="w", pady=(8, 0))
        self._refresh_virtualized_list()

    def _open_selected_warrior_card(self) -> None:
        if self.virtualized_list is None:
            return
        selection = self.virtualized_list.curselection()
        if selection:
            self._open_warrior_card(self.virtualized_list.get(selection[0]))

    def _open_warrior_card(self, name: str) -> None:
        warrior = self.simulator.state.warriors.get(name)
        if warrior is None or not warrior.virtualized:
            return
        key = f"warrior:{name}"
        window = self._new_window(key, f"Entity // {name}", "330x330")
        if window is None:
            return
        frame = ttk.Frame(window, style="Panel.TFrame", padding=20)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text=name.upper(), style="Title.TLabel").pack(anchor="w")
        ttk.Label(frame, text="LYOKO ENTITY CARD", style="Muted.TLabel").pack(anchor="w", pady=(3, 18))
        values = {
            "role": tk.StringVar(),
            "sector": tk.StringVar(),
            "health": tk.StringVar(),
            "status": tk.StringVar(),
        }
        self.warrior_card_vars[name] = values
        for label, key_name in (("ROLE", "role"), ("SECTOR", "sector"), ("HEALTH", "health"), ("STATUS", "status")):
            row = ttk.Frame(frame, style="Panel.TFrame")
            row.pack(fill="x", pady=5)
            ttk.Label(row, text=label, style="Section.TLabel", width=10).pack(side="left")
            ttk.Label(row, textvariable=values[key_name], style="Panel.TLabel").pack(side="left", fill="x", expand=True)
        ttk.Button(frame, text="CLOSE ENTITY CARD", command=lambda: self._close_window(key), style="Action.TButton").pack(fill="x", pady=(20, 0))
        self._refresh_warrior_card(name)

    def _refresh_warrior_card(self, name: str) -> None:
        values = self.warrior_card_vars.get(name)
        warrior = self.simulator.state.warriors.get(name)
        if values is None or warrior is None or not warrior.virtualized:
            return
        values["role"].set(warrior.role)
        values["sector"].set(warrior.location or "UNKNOWN")
        values["health"].set(f"{warrior.health}%" + (" // PROTECTED" if self.simulator._is_protected_warrior(warrior) else ""))
        values["status"].set("VIRTUALISED // ACTIVE")

    def _refresh_virtualized_list(self) -> None:
        if self.virtualized_list is None:
            return
        selected = self.virtualized_list.curselection()
        selected_name = self.virtualized_list.get(selected[0]) if selected else None
        self.virtualized_list.delete(0, "end")
        names = [name for name, warrior in self.simulator.state.warriors.items() if warrior.virtualized]
        for name in names:
            self.virtualized_list.insert("end", name)
        if selected_name in names:
            self.virtualized_list.selection_set(names.index(selected_name))

    def _sync_warrior_windows(self) -> None:
        current = {name for name, warrior in self.simulator.state.warriors.items() if warrior.virtualized}
        for name in current - self.known_virtualized:
            self._open_warrior_card(name)
        for name in self.known_virtualized - current:
            self._close_window(f"warrior:{name}")
        self.known_virtualized = current
        self._refresh_virtualized_list()
        for name in current:
            self._refresh_warrior_card(name)
        self.after(250, self._sync_warrior_windows)

    def _open_dialogue_window(self) -> None:
        window = self._new_window("dialogue", "Supercomputer Dialogue", "680x560")
        if window is None:
            return
        frame = ttk.Frame(window, style="Panel.TFrame", padding=14)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="SUPERCOMPUTER // COMMUNICATIONS LOG", style="Title.TLabel").pack(anchor="w", pady=(0, 8))
        self.log_text = tk.Text(frame, bg="#061118", fg=self.COLORS["text"], insertbackground=self.COLORS["text"], relief="flat", padx=14, pady=12, wrap="word", font=("Consolas", 10))
        self.log_text.pack(fill="both", expand=True)
        self.log_text.configure(state="disabled")
        if not self.dialogue_history and os.path.exists(self.dialogue_log_path):
            try:
                with open(self.dialogue_log_path, encoding="utf-8") as file:
                    self.dialogue_history = file.read().splitlines()
            except OSError:
                pass
        if self.dialogue_history:
            self.log_text.configure(state="normal")
            self.log_text.insert("end", "\n".join(self.dialogue_history) + "\n")
            self.log_text.see("end")
            self.log_text.configure(state="disabled")
        ttk.Label(frame, text=f"ARCHIVE: {self.dialogue_log_path}", style="Muted.TLabel").pack(anchor="w", pady=(8, 0))

    def _draw_map(self) -> None:
        if self.map_canvas is None:
            return
        self.map_canvas.delete("all")
        width = max(self.map_canvas.winfo_width(), 780)
        height = max(self.map_canvas.winfo_height(), 560)
        scale_x, scale_y = width / 820, height / 570

        def point(x: float, y: float) -> tuple[float, float]:
            return x * scale_x, y * scale_y

        self.map_canvas.create_text(*point(30, 28), text="SECTOR NETWORK // SCALE 1:1", anchor="w", fill=self.COLORS["muted"], font=("Consolas", 9))
        for sector, (x1, y1, x2, y2) in self.sector_shapes.items():
            ax, ay = point(x1, y1)
            bx, by = point(x2, y2)
            selected = sector == self.selected_sector.get()
            self.map_canvas.create_rectangle(ax, ay, bx, by, fill=self.sector_colors[sector], outline=self.COLORS["orange"] if selected else self.COLORS["line"], width=3 if selected else 1, tags=("sector_" + sector,))
            self.map_canvas.create_text((ax + bx) / 2, ay + 22 * scale_y, text=sector.upper(), fill=self.COLORS["text"], font=("Segoe UI", 11, "bold"))
            self.map_canvas.create_oval((ax + bx) / 2 - 4, (ay + by) / 2 - 4, (ax + bx) / 2 + 4, (ay + by) / 2 + 4, fill=self.COLORS["cyan"], outline="")
            self.map_canvas.tag_bind("sector_" + sector, "<Button-1>", lambda _event, value=sector: self._select_sector(value))

        # Network links make the five regions read as one connected map.
        centers = {name: point((bounds[0] + bounds[2]) / 2, (bounds[1] + bounds[3]) / 2) for name, bounds in self.sector_shapes.items()}
        drawn_links: set[tuple[str, str]] = set()
        for sector in self.simulator.sector_configs:
            for destination in sector["connections"]:
                link = tuple(sorted((sector["name"], destination)))
                if destination in centers and link not in drawn_links:
                    self.map_canvas.create_line(*centers[sector["name"]], *centers[destination], fill="#52717e", dash=(4, 5), width=2)
                    drawn_links.add(link)

        for sector in self.simulator.sector_configs:
            bounds = self.sector_shapes[sector["name"]]
            x1, y1, x2, y2 = bounds
            for number in range(1, sector["towers"] + 1):
                tower_name = f"{sector['name']} Tower {number}"
                tower_x, tower_y = point(x1 + 28 + ((number - 1) % 5) * ((x2 - x1 - 48) / 4), y2 - 24 - ((number - 1) // 5) * 18)
                possessed = tower_name in self.simulator.state.possessed_towers
                self.map_canvas.create_oval(tower_x - 5, tower_y - 5, tower_x + 5, tower_y + 5, fill=self.COLORS["red"] if possessed else self.COLORS["cyan"], outline=self.COLORS["text"] if number % 2 == 0 else "")
                self.map_canvas.create_text(tower_x, tower_y - 10, text=str(number), fill=self.COLORS["text"], font=("Consolas", 7))

        tower_x, tower_y = point(415, 295)
        self.map_canvas.create_oval(tower_x - 16, tower_y - 16, tower_x + 16, tower_y + 16, fill=self.COLORS["green"] if self.simulator.state.tower_active else self.COLORS["red"], outline=self.COLORS["text"], width=2)
        self.map_canvas.create_text(tower_x, tower_y + 29, text="SYSTEM STATUS", fill=self.COLORS["text"], font=("Consolas", 9, "bold"))
        xana_x, xana_y = point(415, 28)
        xana_color = self.COLORS["red"] if self.simulator.state.xana_active else self.COLORS["muted"]
        self.map_canvas.create_text(xana_x, xana_y, text=f"XANA // {'ACTIVE' if self.simulator.state.xana_active else 'OFFLINE'}", fill=xana_color, font=("Consolas", 10, "bold"))
        for index, warrior in enumerate(self.simulator.state.warriors.values()):
            if warrior.virtualized and warrior.location in self.sector_shapes:
                x1, y1, x2, y2 = self.sector_shapes[warrior.location]
                marker_x, marker_y = point(x1 + 34 + (index % 3) * 34, y1 + 62 + (index // 3) * 30)
                self.map_canvas.create_oval(marker_x - 10, marker_y - 10, marker_x + 10, marker_y + 10, fill=self.COLORS["orange"], outline=self.COLORS["text"])
                self.map_canvas.create_text(marker_x, marker_y, text=warrior.name[0], fill="#17212a", font=("Segoe UI", 9, "bold"))
                self.map_canvas.create_text(marker_x, marker_y + 18, text=warrior.name, fill=self.COLORS["text"], font=("Consolas", 8))

    def _select_sector(self, sector: str) -> None:
        self.selected_sector.set(sector)
        self._draw_map()

    def _rebuild_config_controls(self) -> None:
        self.sector_shapes = {}
        for index, sector in enumerate(self.simulator.sectors):
            if sector in self.DEFAULT_SECTOR_SHAPES:
                self.sector_shapes[sector] = self.DEFAULT_SECTOR_SHAPES[sector]
                continue
            column = index % 3
            row = index // 3
            self.sector_shapes[sector] = (70 + column * 255, 95 + row * 245, 260 + column * 255, 270 + row * 245)
        self.sector_colors = self.simulator.sector_colors.copy()
        self.selected_warriors = {
            name: self.selected_warriors.get(name, tk.BooleanVar(value=name in {"Aelita", "Odd"}))
            for name in self.simulator.warrior_names
        }
        if self.warrior_frame is None or self.sector_menu_frame is None:
            return
        for child in self.warrior_frame.winfo_children():
            child.destroy()
        for name in self.simulator.warrior_names:
            role = self.simulator.warrior_roles.get(name, "Warrior")
            ttk.Checkbutton(self.warrior_frame, text=f"{name} // {role}", variable=self.selected_warriors[name]).pack(anchor="w")
        if self.selected_sector.get() not in self.simulator.sectors:
            self.selected_sector.set(self.simulator.sectors[0])
        if self.sector_menu is not None:
            self.sector_menu.destroy()
        self.sector_menu = ttk.OptionMenu(self.sector_menu_frame, self.selected_sector, self.selected_sector.get(), *self.simulator.sectors, command=lambda _value: self._draw_map())
        self.sector_menu.pack(fill="x")

    def _refresh_config(self) -> None:
        try:
            changed = self.simulator.reload_config()
        except RuntimeError as error:
            self._log("CONFIG ERROR", str(error))
        else:
            if changed:
                self._rebuild_config_controls()
                self._draw_map()
                self._log("SYSTEM", "Warrior and sector configuration reloaded.")
        self.after(1000, self._refresh_config)

    def _execute(self, command: str, operation) -> None:
        try:
            outcome = operation()
        except SimulationError as error:
            self._log("ERROR", str(error))
            return
        self.status_text.set("SYSTEMS ACTIVE")
        self.integrity_text.set(f"SYSTEM INTEGRITY {self.simulator.state.system_integrity}%")
        self._log("JEREMY", command)
        self._log("SYSTEM", outcome)
        self.speaker.speak_async(outcome)
        self._report_tts_error()
        self._draw_map()
        threading.Thread(target=self._get_reply, args=(command, outcome), daemon=True).start()

    def _get_reply(self, command: str, outcome: str) -> None:
        try:
            reply = self.jeremy.reply(self.simulator, command, outcome)
            display_reply = apply_narrator_actions(self.simulator, reply)
            self.reply_queue.put((reply, display_reply))
        except RuntimeError as error:
            message = f"Ollama unavailable: {error}"
            self.reply_queue.put((message, message))

    def _drain_replies(self) -> None:
        while not self.reply_queue.empty():
            spoken_reply, display_reply = self.reply_queue.get_nowait()
            self._log(self.provider.upper(), display_reply)
            self.speaker.speak_async(display_reply)
            self._report_tts_error()
            self._draw_map()
            if self.simulator.state.mission_successful and self.simulator.state.tower_active:
                try:
                    outcome = self.simulator.deactivate_tower()
                except SimulationError as error:
                    self._log("ERROR", str(error))
                else:
                    self._log("SYSTEM", outcome)
                    self.status_text.set("MISSION COMPLETE")
                    self._draw_map()
                self._report_tts_error()
        self.after(100, self._drain_replies)

    def _report_tts_error(self) -> None:
        if self.speaker.error:
            message = f"TTS ERROR: {self.speaker.error}"
            if not self.dialogue_history or message not in self.dialogue_history[-1]:
                self._log("SYSTEM", message)

    def _activate(self) -> None:
        self._execute("Activate the system", self.simulator.activate_system)

    def _monitor(self) -> None:
        self._execute("Monitor all warriors", self.simulator.monitor)

    def _xana_attack(self) -> None:
        self._execute("XANA attack", self.simulator.xana_attack)

    def _virtualize(self) -> None:
        names = [name for name, selected in self.selected_warriors.items() if selected.get()]
        self._execute(f"Virtualise {', '.join(names)} to {self.selected_sector.get()}", lambda: self.simulator.virtualize(names, self.selected_sector.get()))

    def _devirtualize(self) -> None:
        names = [name for name, selected in self.selected_warriors.items() if selected.get()]
        self._execute(f"Devirtualise {', '.join(names)}", lambda: self.simulator.devirtualize(names))

    def _return_to_past(self) -> None:
        if messagebox.askyesno("Return to the past", "Reset the current mission timeline?"):
            self._execute("Return to the past", self.simulator.return_to_past)

    def _log(self, speaker: str, message: str) -> None:
        entry = f"[{speaker}] {message}"
        self.dialogue_history.append(entry)
        try:
            with open(self.dialogue_log_path, "a", encoding="utf-8") as file:
                file.write(entry + "\n")
        except OSError:
            pass
        if self.log_text is None:
            return
        try:
            self.log_text.configure(state="normal")
            self.log_text.insert("end", entry + "\n\n")
            self.log_text.see("end")
            self.log_text.configure(state="disabled")
        except tk.TclError:
            self.log_text = None


def main() -> None:
    parser = argparse.ArgumentParser(description="LyokoSim graphical control room")
    parser.add_argument("--model")
    parser.add_argument("--host")
    parser.add_argument("--provider", choices=("ollama", "openai", "none"), default="ollama")
    args = parser.parse_args()
    app = LyokoControlRoom(args.model, args.host, args.provider)
    app.mainloop()


if __name__ == "__main__":
    main()