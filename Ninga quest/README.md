# Ninja Quest (prototype)

This is a minimal Pygame prototype for a top-down "Ninja Quest" game with an infinite procedural world, rivers, a simple shop, and quests.

How to run

1. Create and activate a Python environment (recommended).
2. Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

3. Run the prototype:

```powershell
python main.py
```

Controls

- W/A/S/D or Arrow keys: Move
- S: Toggle shop
- Q: Toggle quest list
- 1: Buy boat (when shop open)
- Esc: Quit

Notes

- Player cannot cross water tiles unless they own a boat.
- The world is generated deterministically from tile coordinates; it appears infinite as you move.
- This is a starting prototype — we can expand with enemies, bridges, improved river generation, graphics, sounds, and saving.
