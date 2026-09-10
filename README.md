# LyokoSim

A Python command-line Code Lyoko simulator. You play Jeremy and control every operation. The deterministic simulator owns mission state and validation; XANA attacks the active system, while Ollama or OpenAI responds as the supercomputer with communications and mission outcome narration after each command.

On first launch, LyokoSim creates editable configuration files in `%APPDATA%\LyokoSim`:

- `warriors.json` starts with show-inspired roles for `Aelita`, `Ulrich`, `Odd`, `Yumi`, and `William`.
- `sectors.json` starts with ten towers in `Forest`, `Desert`, `Ice`, and `Mountain`, and one tower in `Carith`.

Sector entries use this format:

```json
{
	"name": "Forest",
	"towers": 10,
	"color": "#254638",
	"connections": ["Mountain", "Desert"]
}
```

`color` must be a six-digit hex color. The simulator validates it, and the UI renders the exact configured color for each sector. Even-numbered towers carry the configured connections. XANA can randomly possess any tower; the system reports its full sector and tower number, and possessed towers are shown red on the map.

Edit either file as a JSON list of unique names. The command-line simulator reloads changes before commands, and the graphical UI detects changes automatically while it is running.

Warrior entries can include an editable role used by the AI narrator:

```json
{
	"name": "Aelita",
	"role": "Tower and virtual-world specialist"
}
```

## Requirements

- Python 3.10 or newer
- Ollama running locally, or an OpenAI API key
- An Ollama model, for example `llama3.2`, when using Ollama

```powershell
ollama pull llama3.2
```

## Run

```powershell
python lyokosim.py
```

Use OpenAI instead:

```powershell
$env:OPENAI_API_KEY = "your-api-key"
python lyokosim.py --provider openai --model gpt-4o-mini
```

Use no AI service for fully offline testing:

```powershell
python lyokosim.py --provider none
```

If OpenAI reports HTTP 429, the API key has hit a rate limit or has no remaining quota. Check the OpenAI usage and billing limits, or switch to `--provider ollama` or `--provider none`.

## Graphical control room

Launch the interactive map UI with:

```powershell
python lyoko_ui.py --provider ollama
```

The launcher opens separate Code Lyoko-style interface modules: **MISSION CONTROL**, **LIVE LYOKO MAP**, **VIRTUALISATION DECK**, **VIRTUALISED WARRIORS**, and **SUPERCOMPUTER DIALOGUE**. Open or close them independently from the main menu; they share the same live simulation. Virtualising a warrior opens a live entity card showing their role, sector, health, and status. Close cards and reopen them from the **VIRTUALISED WARRIORS** registry at any time. Use **ACTIVATE SYSTEM** to bring the supercomputer online; only XANA activates Lyoko towers. The map shows the active XANA tower and virtualised warriors. A mission lasts exactly 10 monitor presses. XANA attacks reduce virtualised warrior health; the AI may request `[DEVIRTUALISE Warrior Name]` when a warrior reaches 0 health. Tower specialists/deactivators are protected from death. The dialogue window archives communications to `dialogue.log` in the LyokoSim configuration directory. The AI supplies communications and outcome narration, and may request movement with `[MOVE Warrior Name TO Sector]`. The simulator only accepts moves through configured connections that bring warriors closer to XANA's active tower.

The UI also accepts `--provider openai` and uses `OPENAI_API_KEY`, or `--provider none` for offline play. XANA can attack manually with **TRIGGER XANA ATTACK**, and also attacks during monitoring. Attacks reduce warrior health and system integrity; at zero integrity, the tower goes offline.

Inside the command-line simulator:

```text
activate_system
virtualize Aelita Ulrich Forest
monitor
xana
devirtualize Aelita Ulrich
past
```

Manual commands are also available with `help`. AI providers cannot activate, monitor, attack, or reset the simulation, but they can request validated movement after XANA reveals a target tower. Set `LYOKO_OLLAMA_MODEL` or pass `--model` for Ollama. Set `OLLAMA_HOST` or pass `--host` when Ollama is not at `http://localhost:11434`. OpenAI uses `OPENAI_API_KEY` and `OPENAI_MODEL`.

## Test

```powershell
python -m unittest -v
```