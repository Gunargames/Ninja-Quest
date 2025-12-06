# Asset Guide for Ninja Quest

## Tile Images

Place the following PNG images in the `Images/` folder. Each should be **64x64 pixels** (or larger—they will be scaled).

### Required Tile Images

1. **grass.png** — Regular grass/ground tile
2. **water.png** — Static water tile (rivers/lakes)
3. **water_animated.png** — Animated water tile (used for procedural rivers; cycles through 4 frames)
4. **grass_edge.png** — Shore/edge tile (placed on tiles adjacent to water)

## Player Image

1. **player.png** — Player sprite, **48x48 pixels** (or larger—will be scaled to 48x48)

## Folder Structure

```
Ninga quest/
├── Images/
│   ├── grass.png
│   ├── water.png
│   ├── water_animated.png
│   ├── grass_edge.png
│   └── player.png
├── Audio/
├── main.py
├── requirements.txt
└── README.md
```

## Notes

- PNG format recommended for transparency support.
- All tile images will be scaled to **64x64 pixels**.
- Player image will be scaled to **48x48 pixels**.
- If images are missing, the game will fall back to colored rectangles.
- Water animation cycles every ~0.3 seconds.
