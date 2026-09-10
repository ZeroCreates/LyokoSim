# LyokoSim

**LyokoSim** is a Python-based **Code Lyoko-inspired virtual-world simulator** with an AI-powered narrator and a desktop control-room interface.

The project simulates a Jeremy-style control room where you can activate the supercomputer, send warriors into Lyoko, monitor missions, respond to XANA attacks, move warriors between connected sectors, track warrior health, and complete missions.

The project consists of two primary Python files:

* `lyokosim.py` — Core simulator, game logic, AI narration, configuration, and command-line interface.
* `lyoko_ui.py` — Graphical Tkinter control room interface for operating the simulator.

---

## Features

### 🖥️ Jeremy Control Room

`lyoko_ui.py` provides a desktop control room styled around the Lyoko supercomputer.

The interface includes:

* Mission Control
* Live Lyoko Map
* Virtualisation Deck
* Virtualised Warrior Registry
* Individual Warrior Entity Cards
* Supercomputer Dialogue Log
* System integrity display
* Mission status display
* XANA status
* Warrior health tracking
* Text-to-speech narration
* Login / registration system

The graphical interface automatically opens the Mission Control window after successful authentication.

---

## 🤖 AI Narration

LyokoSim supports three narrator providers:

```text
ollama
openai
none
```

The AI does **not** directly control the simulator.

Instead, the simulator remains authoritative and provides the narrator with the current state. The AI generates story narration and can request validated actions such as:

```text
[MOVE Warrior TO Sector]
[HEALTH Warrior TO 75]
[DEVIRTUALISE Warrior]
[DEACTIVATE_TOWER]
```

Those requests are validated by the simulator before they are applied.

This prevents the narrator from inventing warriors, locations, health values, mission states, or other simulator data.

---

## 🧠 Ollama Support

Ollama can be used as a local AI narrator.

By default, LyokoSim uses:

```text
Model: llama3.2
Host: http://localhost:11434
```

These can be changed with environment variables:

```text
LYOKO_OLLAMA_MODEL
OLLAMA_HOST
```

The application communicates with Ollama's `/api/chat` endpoint.

### Example

```bash
python lyokosim.py --provider ollama
```

With a specific model:

```bash
python lyokosim.py --provider ollama --model llama3.2
```

With a custom Ollama server:

```bash
python lyokosim.py --provider ollama --host http://192.168.1.100:11434
```

Make sure Ollama is running and the selected model has been downloaded.

---

## ☁️ OpenAI Support

LyokoSim can alternatively use OpenAI for narration.

The API key is read from:

```text
OPENAI_API_KEY
```

The default model is:

```text
gpt-4o-mini
```

and can be changed with:

```text
OPENAI_MODEL
```

The OpenAI provider communicates with the Chat Completions API.

### Windows

Set your API key:

```powershell
$env:OPENAI_API_KEY="your-api-key"
```

Then start LyokoSim:

```powershell
python lyokosim.py --provider openai
```

---

## 📴 No AI Mode

LyokoSim can run without an AI narrator:

```bash
python lyokosim.py --provider none
```

In this mode, the deterministic simulator still operates normally, but no AI-generated narration is produced.

This is useful for testing the simulator without an AI service.

---

# Installation

## Requirements

LyokoSim is primarily written using Python's standard library.

The project uses modules including:

* `argparse`
* `hashlib`
* `hmac`
* `json`
* `os`
* `queue`
* `random`
* `re`
* `secrets`
* `threading`
* `urllib`
* `dataclasses`
* `tkinter`

Text-to-speech additionally uses:

```text
pyttsx3
```

The application attempts to use `pythoncom` when available for Windows COM initialization, but treats it as optional.

### Install Python

Use a modern Python 3 installation.

Verify it with:

```bash
python --version
```

or:

```bash
py --version
```

---

## Installing Text-to-Speech

Install `pyttsx3`:

```bash
pip install pyttsx3
```

On Windows, if your Python installation requires the COM dependency explicitly:

```bash
pip install pywin32
```

If TTS fails, LyokoSim continues to operate and records the TTS error rather than treating speech as authoritative.

---

# Running LyokoSim

## Command-Line Version

Run:

```bash
python lyokosim.py
```

By default this uses the Ollama narrator.

Disable TTS:

```bash
python lyokosim.py --no-tts
```

Use OpenAI:

```bash
python lyokosim.py --provider openai
```

Use no AI:

```bash
python lyokosim.py --provider none
```

---

# Graphical Control Room

The graphical interface is provided by:

```text
lyoko_ui.py
```

Start it with:

```bash
python lyoko_ui.py
```

You can also specify the narrator provider:

```bash
python lyoko_ui.py --provider ollama
```

or:

```bash
python lyoko_ui.py --provider openai
```

or:

```bash
python lyoko_ui.py --provider none
```

The UI accepts:

```text
--model
--host
--provider
```

The provider choices are:

```text
ollama
openai
none
```

---

# 🔐 Local Account System

On first launch, LyokoSim asks you to create a local Jeremy account.

The account requires:

* Username
* Password

Passwords are **not stored as plaintext**.

The account system generates a random salt and hashes the password using PBKDF2-HMAC-SHA256 with 200,000 iterations.

After registration, subsequent launches display the login screen.

---

# ⚙️ Configuration

LyokoSim automatically creates its configuration directory.

On Windows this is normally:

```text
%APPDATA%\LyokoSim\
```

On systems without `APPDATA`, it falls back to:

```text
~/.config/LyokoSim/
```

The simulator creates:

```text
LyokoSim/
├── account.json
├── warriors.json
├── sectors.json
└── dialogue.log
```

The configuration system automatically creates default configuration files when they do not exist.

---

# 👥 Warrior Configuration

Warriors are configured through:

```text
warriors.json
```

Each warrior can contain:

```json
{
  "name": "Aelita",
  "role": "Tower and virtual-world specialist",
  "weapon": "Energy fields"
}
```

The simulator requires each warrior to have:

* A unique name
* A role
* A weapon

### Default Warriors

The default configuration contains:

| Warrior | Role                                         | Weapon             |
| ------- | -------------------------------------------- | ------------------ |
| Aelita  | Tower and virtual-world specialist           | Energy fields      |
| Ulrich  | Melee fighter and frontline defender         | 2 Katanas          |
| Odd     | Ranged fighter and reconnaissance specialist | Laser arrows       |
| Yumi    | Ranged fighter and telekinesis specialist    | 2 Telekinetic fans |
| William | Heavy close-combat fighter                   | Great Sword        |

### Custom Warriors

You can replace the default characters with completely custom warriors.

For example:

```json
[
  {
    "name": "Nexus",
    "role": "Tower deactivation specialist",
    "weapon": "Energy Blade"
  },
  {
    "name": "Lyra",
    "role": "Ranged combat specialist",
    "weapon": "Plasma Bow"
  }
]
```

The AI narrator is instructed to use the configured names, roles, and weapons rather than assuming that a character's name determines their abilities.

---

# 🌐 Sector Configuration

Sectors are configured through:

```text
sectors.json
```

Each sector contains:

```json
{
  "name": "Forest",
  "towers": 10,
  "color": "#254638",
  "connections": [
    "Mountain",
    "Desert",
    "Ice",
    "Carith"
  ]
}
```

The configuration supports:

* Sector names
* Number of towers
* Sector display colors
* Connections between sectors

### Default Sectors

```text
Forest
Desert
Ice
Mountain
Carith
```

The default configuration gives Forest, Desert, Ice, and Mountain 10 towers each, while Carith has 1 tower.

---

# 🔄 Live Configuration Reloading

You do not necessarily need to restart the application after editing the configuration.

LyokoSim checks the modification timestamps of:

```text
warriors.json
sectors.json
```

and reloads them when changes are detected.

Existing warrior state is preserved for warriors that still exist in the new configuration.

---

# 🎮 Simulator Commands

The command-line simulator provides:

```text
activate
activate_system
monitor
xana
virtualize
devirtualize
past
status
help
quit
```

The built-in help displays:

```text
activate_system | monitor | xana | virtualize <names> <sector> | devirtualize <names>
past | status | quit
```

---

## Activate the System

```text
activate
```

or:

```text
activate_system
```

This activates the Lyoko system and allows the mission to begin.

---

## Virtualise Warriors

Example:

```text
virtualize Aelita Ulrich Odd Forest
```

The selected warriors are sent to the specified sector at 100% health.

Warriors must be selected from the configured warrior list and cannot already be virtualised.

---

## Monitor Lyoko

```text
monitor
```

Monitoring advances the mission's story progression by one cycle.

Each monitor cycle can also trigger a XANA attack when XANA is active.

---

## Trigger XANA

```text
xana
```

A XANA attack:

* Reduces system integrity
* Increases the XANA attack counter
* Damages non-protected virtualised warriors
* Possesses a tower
* Creates a real-world threat

Non-protected virtualised warriors normally lose 10 health per attack, while the system integrity damage depends on the attack call.

---

## Devirtualise Warriors

```text
devirtualize Aelita
```

or:

```text
devirtualize Aelita Ulrich
```

A devirtualised warrior is removed from Lyoko and no longer has a sector location.

Devirtualised warriors are also tracked as part of the mission state.

---

## Return to the Past

```text
past
```

This resets the current simulation state and starts a new timeline state marked as having requested a return to the past.

---

## View Status

```text
status
```

This outputs the current simulator state as formatted JSON.

---

# ⚔️ Mission System

LyokoSim uses a simplified Code Lyoko-style mission structure.

A mission consists of:

1. Activate the system.
2. XANA activates/possesses a tower.
3. Virtualise warriors.
4. Monitor Lyoko.
5. Respond to XANA attacks.
6. Move warriors toward the target.
7. Devirtualise warriors when necessary.
8. Complete the required story progression.
9. Deactivate the tower.
10. Return to the past if desired.

The built-in episode guide defines a mission length of **10 monitoring cycles**.

---

# 🗼 Mission Completion

A mission is considered successful when:

* Story progress reaches 10.
* System integrity is greater than 0.
* At least one warrior has been devirtualised.

Once the mission succeeds, the active tower can be deactivated.

The simulator then:

* Turns the tower offline.
* Removes the active tower.
* Clears possessed towers.
* Records the successful mission.

---

# 🛡️ Tower Specialist Protection

A warrior whose configured role contains:

```text
tower
```

and one of:

```text
specialist
deactivator
deactivate
```

is treated as a protected tower specialist.

This protection is based on the **role**, not the warrior's name.

The protected warrior must remain at:

```text
100% health
```

and cannot die through normal mission damage.

This means custom characters can fill the same gameplay function without needing to be named Aelita.

---

# 🗺️ Warrior Movement

The simulator models sector connections as a graph.

Warriors can move between connected sectors while progressing toward XANA's active tower.

The AI narrator receives validated movement options from the simulator and is instructed not to invent routes.

The simulator uses shortest-path calculations to determine whether a requested movement brings a warrior closer to the target.

---

# ❤️ Health System

Warrior health ranges from:

```text
0–100
```

Health updates are validated before being applied.

A warrior must currently be virtualised before its health can be changed.

The tower specialist/deactivator is protected and must remain at 100%.

When a non-protected warrior reaches 0 health, the simulator can automatically devirtualise them.

---

# 🖥️ Graphical Interface Modules

The control room contains several independent windows.

## Mission Control

Provides:

```text
ACTIVATE SYSTEM
MONITOR WARRIORS
TRIGGER XANA ATTACK
RETURN TO THE PAST
```

and displays system status and integrity.

---

## Live Lyoko Map

The map displays:

* Sectors
* Sector connections
* Towers
* Possessed towers
* System status
* XANA status
* Virtualised warriors
* Warrior locations

The default UI recognizes:

```text
Forest
Mountain
Ice
Desert
Carith
```

and dynamically rebuilds the map based on the configured sectors.

---

## Virtualisation Deck

The Virtualisation Deck lets you:

1. Select warriors.
2. Select a destination sector.
3. Virtualise the selected warriors.
4. Devirtualise selected warriors.

---

## Virtualised Warriors

The Virtualised Warriors window provides a live registry of currently virtualised warriors.

Double-clicking a warrior opens an entity card.

Entity cards display:

```text
ROLE
WEAPON
SECTOR
HEALTH
STATUS
```

---

## Supercomputer Dialogue

The dialogue window displays the simulator's communications history.

Dialogue is also written to:

```text
dialogue.log
```

The UI reloads the existing dialogue log when the dialogue window is opened.

---

# 🔊 Text-to-Speech

LyokoSim includes asynchronous text-to-speech.

Speech runs on a dedicated worker thread so narration does not block the simulator interface.

The TTS engine uses `pyttsx3`.

Speech also strips simulator action tokens before speaking them.

---

# 📁 Project Structure

A basic project installation can look like:

```text
LyokoSim/
│
├── lyokosim.py
├── lyoko_ui.py
└── README.md
```

Runtime configuration is stored separately in the user's LyokoSim configuration directory.

---

# 🧩 Architecture

The project is split into two major layers.

```text
                  ┌─────────────────────┐
                  │     lyoko_ui.py     │
                  │  Jeremy Control Room │
                  └──────────┬──────────┘
                             │
                             ▼
                  ┌─────────────────────┐
                  │     lyokosim.py     │
                  │  Simulation Engine  │
                  └──────────┬──────────┘
                             │
             ┌───────────────┼────────────────┐
             ▼               ▼                ▼
        Configuration     Mission State    AI Narrator
        warriors.json     Warriors         Ollama
        sectors.json      Towers            OpenAI
                           XANA             None
```

`lyoko_ui.py` imports the simulator classes directly from `lyokosim.py`, including:

```python
AccountManager
ConfigManager
LyokoSimulator
SimulationError
TextToSpeech
apply_narrator_actions
create_narrator
```

---

# 🧪 Testing Without AI

For testing the simulator itself, use:

```bash
python lyokosim.py --provider none --no-tts
```

This removes external AI and speech dependencies from the test environment while leaving the deterministic simulator available.

---

# 🛠️ Troubleshooting

## Ollama cannot be reached

If you see an error indicating that Ollama cannot be reached:

1. Start Ollama.
2. Confirm the model exists.
3. Check the configured host.
4. Try:

```bash
python lyokosim.py --provider none
```

to confirm the simulator itself works.

The default Ollama endpoint is:

```text
http://localhost:11434
```

---

## OpenAI narrator does not start

Make sure:

```text
OPENAI_API_KEY
```

is configured.

If it is missing, the OpenAI narrator raises an error stating that the API key is not set.

You can temporarily use:

```bash
python lyokosim.py --provider ollama
```

instead.

---

## TTS does not work

Install:

```bash
pip install pyttsx3
```

You can also disable TTS from the command line:

```bash
python lyokosim.py --no-tts
```

The simulator's text output remains authoritative even if TTS fails.

---

## Configuration errors

If `warriors.json` or `sectors.json` contains invalid data, LyokoSim reports a configuration error.

Common problems include:

* Empty warrior list
* Duplicate warrior names
* Missing warrior names
* Missing roles
* Missing weapons
* Empty sector list
* Duplicate sector names
* Invalid tower counts
* Invalid hex colors
* Invalid sector connections

The configuration loader validates these fields before accepting the configuration.

---

# ⚠️ Important Design Principle

The simulator is the source of truth.

The AI narrator is intentionally prevented from directly changing the world.

This means:

```text
AI says something
       ↓
Simulator validates it
       ↓
Valid action → applied
Invalid action → rejected
       ↓
Updated simulator state
       ↓
AI receives authoritative state
```

This architecture keeps the generated story synchronized with the actual game state and prevents the narrator from accidentally inventing impossible events.

---

# 📜 License

No license information is currently defined in the supplied project files.

If this project is intended for public distribution, add a license such as MIT, GPL-3.0, or another license appropriate for the project.

---

# ❤️ Credits

**LyokoSim**

A fan-made Code Lyoko-inspired simulator focused on interactive missions, AI narration, and a Jeremy-style supercomputer control room.

The project is not affiliated with the original creators or rights holders of **Code Lyoko**.

---

## Quick Start

The shortest path to running the project is:

```bash
pip install pyttsx3
python lyoko_ui.py
```

Create your local account when prompted.

Then:

```text
MISSION CONTROL
       ↓
ACTIVATE SYSTEM
       ↓
VIRTUALISATION DECK
       ↓
SELECT WARRIORS
       ↓
SELECT SECTOR
       ↓
VIRTUALISE SELECTED
       ↓
MONITOR WARRIORS
       ↓
RESPOND TO XANA
       ↓
REACH THE TARGET
       ↓
MISSION COMPLETE
```

**Welcome to Lyoko.**

`SCANNING...`

`XANA STATUS: ACTIVE`

`JEREMY CONTROL ROOM: ONLINE`
