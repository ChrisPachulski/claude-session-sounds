# Claude Session Sounds

Random notification sounds and named terminal tabs for [Claude Code](https://docs.anthropic.com/en/docs/claude-code) sessions.

Each time you start Claude, a random sound is assigned. The sound plays after every Claude response, and your terminal tab shows the sound name so you can tell sessions apart at a glance.

## What you get

- **17 notification sounds** -- retro game SFX, movie themes, ambient clips
- **Named terminal tabs** -- each session gets a unique name (e.g., "Gotcha", "The Shire", "Pentakill")
- **Works everywhere** -- Windows, macOS, Linux. VS Code integrated terminal, iTerm2, Terminal.app, etc.

## Install

```bash
python install_claude_sounds.py
```

The installer:
1. Copies sound files to `~/.claude/sounds/`
2. Adds hooks to `~/.claude/settings.json` (merged with your existing config)
3. Adds a `claude` shell wrapper to your profile (PowerShell, bash, or zsh)
4. Configures VS Code terminal tab titles (if VS Code is installed)

Then open a new terminal and type `claude`.

## Adding your own sounds

Drop `.wav` files into `~/.claude/sounds/`. The filename becomes the display name:

```
cool_cat.wav      ->  "Cool Cat"
mario_powerup.wav ->  "Mario Powerup"
my_sound.wav      ->  "My Sound"
```

Requirements for sound files:
- WAV format (44100 Hz, mono, 16-bit PCM recommended)
- Under 5 seconds
- Peak volume under 50%

## How it works

```
Terminal opens -> shell wrapper picks a random sound
                  -> sets terminal tab name via --name flag
                  -> starts background title keeper (ANSI escape loop)
                  -> launches claude

Claude responds -> Stop hook plays the assigned sound
                   -> async, non-blocking

Session ends   -> assignment file cleaned up
                   -> sound returned to the pool
```

## Core sounds

| Sound | Source |
|-------|--------|
| Power-Up | Super Mario mushroom |
| Scorpion | Mortal Kombat |
| Gotcha | Pokemon |
| Tetris | Tetris theme |
| R2-D2 | Star Wars |
| Minecraft | Minecraft level up |
| Pentakill | League of Legends |
| Lightsaber | Star Wars |
| New Era | Civilization |
| Mission | Mission Impossible |
| 007 | James Bond |
| The Shire | Lord of the Rings |
| Mohican | Last of the Mohicans |
| Cool Cat | Cool Cat soundtrack |
| Feels So Good | Chuck Mangione |
| About Time | About Time soundtrack |
| Creek | Ambient creek |

## Uninstall

Remove the hooks from `~/.claude/settings.json` (the `SessionStart`, `Stop`, and `SessionEnd` entries that reference `sound_manager.py`), delete `~/.claude/sounds/`, and remove the `claude` function from your shell profile.
