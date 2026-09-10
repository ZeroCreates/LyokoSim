"""Desktop control room UI for LyokoSim."""

from __future__ import annotations

import argparse
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
        self.sector_menu: ttk.OptionMenu | None = None
        self.status_text = tk.StringVar(value="SYSTEMS STANDBY")
        self.integrity_text = tk.StringVar(value="SYSTEM INTEGRITY 100%")
        self._build_styles()
        self._build_layout()
        self._rebuild_config_controls()
        self._draw_map()
        self.after(100, self._drain_replies)
        self.after(1000, self._refresh_config)

    def _build_styles(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Panel.TFrame", background=self.COLORS["panel"])
        style.configure("Panel.TLabel", background=self.COLORS["panel"], foreground=self.COLORS["text"])
        style.configure("Muted.TLabel", background=self.COLORS["panel"], foreground=self.COLORS["muted"])
        style.configure("Title.TLabel", background=self.COLORS["bg"], foreground=self.COLORS["cyan"], font=("Segoe UI", 18, "bold"))
        style.configure("Section.TLabel", background=self.COLORS["panel"], foreground=self.COLORS["cyan"], font=("Segoe UI", 10, "bold"))
        style.configure("Action.TButton", background=self.COLORS["panel_light"], foreground=self.COLORS["text"], padding=(12, 8), font=("Segoe UI", 10, "bold"))
        style.map("Action.TButton", background=[("active", "#2a4552")])

    def _build_layout(self) -> None:
        header = ttk.Frame(self, style="Panel.TFrame", padding=(24, 16))
        header.pack(fill="x")
        ttk.Label(header, text="LYOKOSIM", style="Title.TLabel").pack(side="left")
        ttk.Label(header, text="  //  JEREMY CONTROL ROOM", style="Muted.TLabel").pack(side="left", pady=(5, 0))
        ttk.Label(header, textvariable=self.status_text, style="Section.TLabel").pack(side="right", pady=(5, 0))
        ttk.Label(header, textvariable=self.integrity_text, style="Muted.TLabel").pack(side="right", padx=(0, 24), pady=(5, 0))

        body = ttk.Frame(self, style="Panel.TFrame", padding=(18, 0, 18, 18))
        body.pack(fill="both", expand=True)
        left = ttk.Frame(body, style="Panel.TFrame")
        left.pack(side="left", fill="both", expand=True, padx=(0, 12))
        right = ttk.Frame(body, style="Panel.TFrame", width=330)
        right.pack(side="right", fill="y")
        right.pack_propagate(False)

        ttk.Label(left, text="VIRTUAL WORLD // LIVE MAP", style="Section.TLabel").pack(anchor="w", pady=(12, 8))
        self.map_canvas = tk.Canvas(left, bg="#0d1720", highlightthickness=1, highlightbackground=self.COLORS["line"])
        self.map_canvas.pack(fill="both", expand=True)
        self.map_canvas.bind("<Configure>", lambda _event: self._draw_map())

        ttk.Label(right, text="MISSION CONTROL", style="Section.TLabel").pack(anchor="w", pady=(12, 8))
        controls = ttk.Frame(right, style="Panel.TFrame")
        controls.pack(fill="x")
        ttk.Button(controls, text="ACTIVATE SYSTEM", command=self._activate, style="Action.TButton").pack(fill="x", pady=3)
        ttk.Button(controls, text="MONITOR WARRIORS", command=self._monitor, style="Action.TButton").pack(fill="x", pady=3)
        ttk.Button(controls, text="TRIGGER XANA ATTACK", command=self._xana_attack, style="Action.TButton").pack(fill="x", pady=3)
        ttk.Button(controls, text="RETURN TO THE PAST", command=self._return_to_past, style="Action.TButton").pack(fill="x", pady=3)

        ttk.Label(right, text="WARRIORS TO VIRTUALISE / DEVIRTUALISE", style="Muted.TLabel", wraplength=300).pack(anchor="w", pady=(18, 6))
        self.warrior_frame = ttk.Frame(right, style="Panel.TFrame")
        self.warrior_frame.pack(fill="x")
        ttk.Label(right, text="TARGET SECTOR", style="Muted.TLabel").pack(anchor="w", pady=(14, 4))
        self.sector_menu_frame = ttk.Frame(right, style="Panel.TFrame")
        self.sector_menu_frame.pack(fill="x")
        ttk.Button(right, text="VIRTUALISE SELECTED", command=self._virtualize, style="Action.TButton").pack(fill="x", pady=(9, 3))
        ttk.Button(right, text="DEVIRTUALISE SELECTED", command=self._devirtualize, style="Action.TButton").pack(fill="x", pady=3)

        ttk.Label(right, text="SUPERCOMPUTER COMMUNICATIONS", style="Section.TLabel").pack(anchor="w", pady=(20, 6))
        self.log_text = tk.Text(right, height=12, bg="#0d1720", fg=self.COLORS["text"], insertbackground=self.COLORS["text"], relief="flat", padx=10, pady=8, wrap="word", font=("Consolas", 9))
        self.log_text.pack(fill="both", expand=True)
        self.log_text.configure(state="disabled")
        self._log("SYSTEM", f"Control room online. Configuration: {self.simulator.config.directory}")
        if self.startup_error:
            self._log("SYSTEM", f"Narrator fallback: {self.startup_error}")

    def _draw_map(self) -> None:
        if not hasattr(self, "map_canvas"):
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
            self.speaker.speak_async(spoken_reply)
            if self.simulator.state.mission_successful and self.simulator.state.tower_active:
                try:
                    outcome = self.simulator.deactivate_tower()
                except SimulationError as error:
                    self._log("ERROR", str(error))
                else:
                    self._log("SYSTEM", outcome)
                    self.status_text.set("MISSION COMPLETE")
                    self._draw_map()
        self.after(100, self._drain_replies)

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
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"[{speaker}] {message}\n\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")


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