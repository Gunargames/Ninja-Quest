import sys
import math
import random
import os
import pygame

# Simple top-down infinite-world prototype for "Ninja Quest"

# Configuration
TILE = 64  # Increased tile size for larger sprites
SCREEN_W = 800
SCREEN_H = 600
FPS = 60
RENDER_RADIUS_TILES = 20
PLAYER_SIZE = 48  # Player sprite size


class Player:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.speed = 250.0  # pixels per second - increased for smoother movement
        self.gold = 100
        self.has_boat = False
        self.has_sword = False
        self.facing_left = False  # Track if facing left
        self.in_shop_room = False  # Track if player is inside shop room
        self.show_inventory = False  # Track if inventory is shown
        self.shop_ui_open = False  # Shop UI inside room opens only with B
        # Room-local position used when inside the shop room (screen-space)
        self.room_x = None
        self.room_y = None
        # Health and combat
        self.max_health = 100
        self.health = 100
        self.attack_cooldown = 0.0  # Time until next attack is allowed
        # Attack animation timer (switch sprite while > 0)
        self.attack_anim_timer = 0.0
        # Inventory system
        self.inventory = {
            'boat': {'name': 'Boat', 'cost': 50, 'owned': False},
            'sword': {'name': 'Sword', 'cost': 30, 'owned': False}
        }

    @property
    def pos(self):
        return (self.x, self.y)


class Enemy:
    """A simple enemy that wanders and can be a generic or a wolf.

    Supported types: 'generic' (default) and 'wolf'. Wolf uses images if provided.
    """
    def __init__(self, x, y, etype='generic', img=None, attack_img=None):
        self.x = x
        self.y = y
        self.type = etype
        self.img = img
        self.attack_img = attack_img
        # Attributes by type
        if self.type == 'wolf':
            self.speed = 160.0
            self.max_health = 40
            self.health = 40
            self.damage = 15
            self.attack_rate = 1.2
        else:
            self.speed = 120.0
            self.max_health = 30
            self.health = 30
            self.damage = 10
            self.attack_rate = 1.5

        self.attack_cooldown = 0.0
        self.attack_anim_timer = 0.0
        self.wander_dir_x = random.choice([-1, 1])
        self.wander_dir_y = random.choice([-1, 1])
        self.wander_timer = random.uniform(1.0, 3.0)

    def update(self, dt, player, world):
        """Update enemy: wander and decay timers."""
        self.wander_timer -= dt
        if self.wander_timer < 0:
            # Pick a new wander direction
            self.wander_dir_x = random.choice([-1, 0, 1])
            self.wander_dir_y = random.choice([-1, 0, 1])
            self.wander_timer = random.uniform(1.0, 3.0)

        # Move (simple wander)
        nx = self.x + self.wander_dir_x * self.speed * dt
        ny = self.y + self.wander_dir_y * self.speed * dt
        # Keep enemy on land
        tx, ty = world_tile_at_pixel(world, nx, ny)
        if not world.is_water_base(tx, ty):
            self.x = nx
            self.y = ny

        # Cooldown update
        if self.attack_cooldown > 0:
            self.attack_cooldown -= dt
        if self.attack_anim_timer > 0:
            self.attack_anim_timer -= dt


class Shop:
	"""A shop building in the world."""
	def __init__(self, tx, ty):
		self.tx = tx  # Tile x coordinate (top-left of shop)
		self.ty = ty  # Tile y coordinate (top-left of shop)
		self.width = 4  # Shop is 4 tiles wide
		self.height = 3  # Shop is 3 tiles tall
		self.entrance_y = ty + self.height  # Front entrance is at bottom
	
	def contains_tile(self, tx, ty):
		"""Check if a tile coordinate is inside the shop."""
		return (self.tx <= tx < self.tx + self.width and
				self.ty <= ty < self.ty + self.height)
	
	def is_entrance(self, tx, ty):
		"""Check if a tile is at the shop entrance (front face)."""
		# Entrance is the front row of the shop
		return (self.tx <= tx < self.tx + self.width and
				ty == self.entrance_y)


class World:
    def __init__(self):
        # world is infinite; we generate deterministically from coordinates
        self.tile_cache = {}  # cache loaded tile images
        self.load_tiles()
        self.animation_frame = 0
        self.animation_timer = 0
        
        # Create a shop building at a fixed location on the main island
        self.shop = Shop(tx=-2, ty=-4)
        # Define the interior room rectangle (screen coordinates) for the shop room
        # This is a smaller room where the player can walk; bottom edge exits the room
        self.room_rect = pygame.Rect(160, 120, 480, 320)
        # Sea gem state (pixel coords) for the quest
        self.sea_gem_px = None
        self.sea_gem_py = None
        self.sea_gem_active = False

    def load_tiles(self):
        """Load tile images from Images/tilemap folder."""
        tile_names = [
            ('grass', 'grass.png'),
            ('water', 'water.png'),
            ('water_animated', 'water_animated.png'),
            ('grass_edge', 'grass_edge.png'),
            ('grass_edge_reverse', 'grass_edge_reverse.png'),
            ('grass_edge_left', 'grass_edge_left.png'),
            ('grass_edge_right', 'grass_edge_right.png'),
            ('grass_corner_tl', 'grass_corner_tl.png'),
            ('grass_corner_tr', 'grass_corner_tr.png'),
            ('grass_corner_bl', 'grass_corner_bl.png'),
            ('grass_corner_br', 'grass_corner_br.png')
        ]
        images_dir = os.path.join(os.path.dirname(__file__), 'Images', 'tilemap')
        
        for key, filename in tile_names:
            path = os.path.join(images_dir, filename)
            try:
                img = pygame.image.load(path).convert_alpha()
                img = pygame.transform.scale(img, (TILE, TILE))
                self.tile_cache[key] = img
                print(f"[OK] Loaded tile: {key} ({filename})")
            except Exception as e:
                print(f"[FAIL] Could not load {filename}: {e}")
                self.tile_cache[key] = None

    def update_animation(self, dt):
        """Update water animation frame."""
        self.animation_timer += dt
        if self.animation_timer > 0.3:  # Change frame every 0.3 seconds
            self.animation_timer = 0
            self.animation_frame = (self.animation_frame + 1) % 4  # 4 animation frames

    def find_water_tile_at_distance(self, origin_tx, origin_ty, dist_tiles, min_tiles=0):
        """Try to find a water tile approximately `dist_tiles` away from origin.

        We attempt multiple random directions and return the first water tile found.
        Returns (tx, ty) or None if not found.
        """
        attempts = 1200
        for _ in range(attempts):
            ang = random.random() * math.tau
            tx = int(round(origin_tx + math.cos(ang) * dist_tiles))
            ty = int(round(origin_ty + math.sin(ang) * dist_tiles))
            # small jitter around the target in case exact ring tile is land
            jitter_x = random.randint(-6, 6)
            jitter_y = random.randint(-6, 6)
            tx += jitter_x
            ty += jitter_y
            if not self.is_water(tx, ty):
                continue
            # ensure tile is at least min_tiles away
            if min_tiles > 0:
                d = math.hypot(tx - origin_tx, ty - origin_ty)
                if d < min_tiles:
                    continue
            return tx, ty
        return None

    def is_water_base(self, tx, ty):
        """Return True if tile is water based on island generation.
        
        Creates two islands: main island at (0,0) and larger island at top-right (20, -15).
        Islands have smooth edges without thin single-width strips.
        """
        # Main island at origin (0, 0) - smaller
        distance_main = math.sqrt(tx*tx + ty*ty)
        
        if distance_main < 12:
            return False  # Main island core
        
        if distance_main < 20:
            # Shore transition with noise
            rs = random.Random((tx * 49297) ^ (ty * 9301))
            noise = rs.random()
            threshold = 20 + (noise * 3)
            if distance_main < threshold:
                return False  # Still on main island shore
        
        # Larger island at top-right (20, -15) - bigger
        island2_cx, island2_cy = 20, -15
        distance_island2 = math.sqrt((tx - island2_cx)**2 + (ty - island2_cy)**2)
        
        if distance_island2 < 18:
            return False  # Larger island core
        
        if distance_island2 < 28:
            # Shore transition with noise
            rs2 = random.Random((tx * 31337) ^ (ty * 18433))
            noise2 = rs2.random()
            threshold2 = 28 + (noise2 * 4)
            if distance_island2 < threshold2:
                return False  # Still on larger island shore
        
        # Everything else is water
        return True

    def is_water(self, tx, ty):
        """Return True if tile at tile-coords (tx,ty) is water (river/lake)."""
        return self.is_water_base(tx, ty)

    def is_shore(self, tx, ty):
        """Return True if this is a shore tile (grass adjacent to water)."""
        if self.is_water(tx, ty):
            return False
        # Check if adjacent to water (any direction)
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            if self.is_water(tx + dx, ty + dy):
                return True
        return False

    def is_shore_bottom(self, tx, ty):
        """Return True if water is directly below this tile."""
        if self.is_water(tx, ty):
            return False
        return self.is_water(tx, ty + 1)

    def is_shore_top(self, tx, ty):
        """Return True if water is directly above this tile."""
        if self.is_water(tx, ty):
            return False
        return self.is_water(tx, ty - 1)

    def is_shore_left(self, tx, ty):
        """Return True if water is directly to the left of this tile."""
        if self.is_water(tx, ty):
            return False
        return self.is_water(tx - 1, ty)

    def is_shore_right(self, tx, ty):
        """Return True if water is directly to the right of this tile."""
        if self.is_water(tx, ty):
            return False
        return self.is_water(tx + 1, ty)

    def is_shop_tile(self, tx, ty):
        """Check if a tile is part of the shop building (blocking collision)."""
        return self.shop.contains_tile(tx, ty)

    def get_corner_tile(self, tx, ty):
        """Determine if this tile is a corner and return the corner tile key."""
        if self.is_water(tx, ty):
            return None
        
        water_above = self.is_water(tx, ty - 1)
        water_below = self.is_water(tx, ty + 1)
        water_left = self.is_water(tx - 1, ty)
        water_right = self.is_water(tx + 1, ty)
        
        # Top-left corner (water above and left)
        if water_above and water_left:
            return 'grass_corner_tl'
        # Top-right corner (water above and right)
        if water_above and water_right:
            return 'grass_corner_tr'
        # Bottom-left corner (water below and left)
        if water_below and water_left:
            return 'grass_corner_bl'
        # Bottom-right corner (water below and right)
        if water_below and water_right:
            return 'grass_corner_br'
        
        return None

    def get_corner_tile(self, tx, ty):
        """Determine if this tile is a grass corner and return the corner tile key."""
        if self.is_water(tx, ty):
            return None
        
        water_above = self.is_water(tx, ty - 1)
        water_below = self.is_water(tx, ty + 1)
        water_left = self.is_water(tx - 1, ty)
        water_right = self.is_water(tx + 1, ty)
        
        # Top-left corner (water above AND to the left)
        if water_above and water_left:
            return 'grass_corner_tl'
        # Top-right corner (water above AND to the right)
        if water_above and water_right:
            return 'grass_corner_tr'
        # Bottom-left corner (water below AND to the left)
        if water_below and water_left:
            return 'grass_corner_bl'
        # Bottom-right corner (water below AND to the right)
        if water_below and water_right:
            return 'grass_corner_br'
        
        return None

    def get_tile_image(self, tx, ty):
        """Return the appropriate tile image for the given coordinates."""
        if self.is_water(tx, ty):
            # Return animated water if available, else static
            if 'water_animated' in self.tile_cache and self.tile_cache['water_animated']:
                return self.tile_cache['water_animated']
            elif 'water' in self.tile_cache and self.tile_cache['water']:
                return self.tile_cache['water']
        else:
            # Check for corners first
            corner = self.get_corner_tile(tx, ty)
            if corner and corner in self.tile_cache and self.tile_cache[corner]:
                return self.tile_cache[corner]
            
            # Then check edges
            if self.is_shore_bottom(tx, ty):
                if 'grass_edge' in self.tile_cache and self.tile_cache['grass_edge']:
                    return self.tile_cache['grass_edge']
            elif self.is_shore_top(tx, ty):
                if 'grass_edge_reverse' in self.tile_cache and self.tile_cache['grass_edge_reverse']:
                    return self.tile_cache['grass_edge_reverse']
            elif self.is_shore_left(tx, ty):
                if 'grass_edge_left' in self.tile_cache and self.tile_cache['grass_edge_left']:
                    return self.tile_cache['grass_edge_left']
            elif self.is_shore_right(tx, ty):
                if 'grass_edge_right' in self.tile_cache and self.tile_cache['grass_edge_right']:
                    return self.tile_cache['grass_edge_right']
            
            # Default to grass
            if 'grass' in self.tile_cache and self.tile_cache['grass']:
                return self.tile_cache['grass']
        
        return None
def world_tile_at_pixel(world, px, py):
	tx = math.floor(px / TILE)
	ty = math.floor(py / TILE)
	return tx, ty


def can_move_to(world, player, nx, ny):
	# check tile collision at player's center
	tx, ty = world_tile_at_pixel(world, nx, ny)
	# Only check if base water (fast check, no thin-land logic)
	if world.is_water_base(tx, ty) and not player.has_boat:
		return False
	# Check if trying to enter shop (allow entrance and inside)
	if world.is_shop_tile(tx, ty) and not world.shop.is_entrance(tx, ty):
		return False
	return True


def check_shop_entry(world, player):
    """Check if player is at shop entrance and enter if so."""
    tx, ty = world_tile_at_pixel(world, player.x, player.y)
    if world.shop.is_entrance(tx, ty):
        # Entering the shop room
        player.in_shop_room = True
        # Initialize room-local position (relative to room top-left) near the top-left inside the room rectangle
        player.room_x = PLAYER_SIZE // 2 + 8
        player.room_y = PLAYER_SIZE // 2 + 8


def exit_shop(world, player):
    """Exit the shop room back to world."""
    player.in_shop_room = False
    player.shop_ui_open = False
    # Spawn player at shop entrance
    # Center X on the shop and place player 2 tiles below the entrance to avoid immediate re-entry
    player.x = (world.shop.tx + world.shop.width // 2) * TILE + TILE // 2
    player.y = (world.shop.entrance_y + 2) * TILE + TILE // 2
    # Clear room-local coordinates
    player.room_x = None
    player.room_y = None


def find_spawn_point(world):
	"""Find a land tile to spawn the player on."""
	for attempt in range(1000):
		tx = random.randint(-10, 10)
		ty = random.randint(-10, 10)
		if not world.is_water(tx, ty):
			return (tx * TILE + TILE // 2, ty * TILE + TILE // 2)
	# Fallback
	return (0.0, 0.0)


def draw_world(surface, world, camera_x, camera_y):
    start_tx = int(math.floor((camera_x - SCREEN_W // 2) / TILE)) - 1
    start_ty = int(math.floor((camera_y - SCREEN_H // 2) / TILE)) - 1
    end_tx = int(math.floor((camera_x + SCREEN_W // 2) / TILE)) + 1
    end_ty = int(math.floor((camera_y + SCREEN_H // 2) / TILE)) + 1

    for ty in range(start_ty, end_ty + 1):
        for tx in range(start_tx, end_tx + 1):
            world_x = tx * TILE
            world_y = ty * TILE
            screen_x = world_x - (camera_x - SCREEN_W // 2)
            screen_y = world_y - (camera_y - SCREEN_H // 2)

            tile_img = world.get_tile_image(tx, ty)
            if tile_img:
                surface.blit(tile_img, (int(screen_x), int(screen_y)))
            else:
                # Fallback color if image not loaded
                if world.is_water(tx, ty):
                    color = (35, 120, 220)
                else:
                    base = 50 + ((tx * 31) ^ ty) % 60
                    color = (34, min(200, base + 30), 34)
                pygame.draw.rect(surface, color, (int(screen_x), int(screen_y), TILE, TILE))
    
    # Draw shop building
    shop_color = (139, 69, 19)  # Brown
    entrance_color = (184, 134, 11)  # Dark goldenrod
    # If the world has a shop image, draw it once; otherwise draw tile rectangles for each tile
    if getattr(world, 'shop_img', None):
        build_x = world.shop.tx * TILE - (camera_x - SCREEN_W // 2)
        build_y = world.shop.ty * TILE - (camera_y - SCREEN_H // 2)
        surface.blit(world.shop_img, (int(build_x), int(build_y)))
    else:
        for sy in range(world.shop.ty, world.shop.ty + world.shop.height):
            for sx in range(world.shop.tx, world.shop.tx + world.shop.width):
                world_x = sx * TILE
                world_y = sy * TILE
                screen_x = world_x - (camera_x - SCREEN_W // 2)
                screen_y = world_y - (camera_y - SCREEN_H // 2)
                # Use different color for entrance
                if world.shop.is_entrance(sx, sy):
                    pygame.draw.rect(surface, entrance_color, (int(screen_x), int(screen_y), TILE, TILE))
                else:
                    pygame.draw.rect(surface, shop_color, (int(screen_x), int(screen_y), TILE, TILE))
                # Draw border
                pygame.draw.rect(surface, (0, 0, 0), (int(screen_x), int(screen_y), TILE, TILE), 2)
def draw_grid(surface):
	# a subtle grid to help see tile boundaries
	color = (0, 0, 0, 20)
	for x in range(0, SCREEN_W, TILE):
		pygame.draw.line(surface, (0,0,0), (x,0), (x,SCREEN_H), 1)
	for y in range(0, SCREEN_H, TILE):
		pygame.draw.line(surface, (0,0,0), (0,y), (SCREEN_W,y), 1)


def main():
    pygame.init()

    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    pygame.display.set_caption("Ninja Quest (prototype)")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont(None, 24)


    world = World()
    spawn_x, spawn_y = find_spawn_point(world)
    player = Player(spawn_x, spawn_y)
    show_debug = False
    # Main menu state
    in_main_menu = True
    menu_state = 'main'  # 'main' or 'slots'
    menu_options = ["Start Game", "Quit"]
    menu_index = 0
    menu_rects = []
    # World slots (click a slot to start a world)
    world_slots = [{'name': f'Slot {i+1}', 'created': False} for i in range(3)]
    slot_rects = []
    current_slot = None
    enemies = []  # List of Enemy objects in the world

    # Load slot data if it exists
    import json
    slots_file = os.path.join(os.path.dirname(__file__), 'slots.json')
    if os.path.exists(slots_file):
        try:
            with open(slots_file, 'r') as f:
                loaded = json.load(f)
                for i, slot in enumerate(loaded):
                    if i < len(world_slots):
                        world_slots[i].update(slot)
        except Exception as e:
            print(f"[WARN] Could not load slots: {e}")

    def save_slots():
        """Save world_slots to disk."""
        try:
            with open(slots_file, 'w') as f:
                json.dump(world_slots, f, indent=2)
                print("[OK] Slots saved")
        except Exception as e:
            print(f"[WARN] Could not save slots: {e}")

    # Spawn the sea gem at startup ~200 tiles away from the initial spawn
    try:
        sp_tx, sp_ty = world_tile_at_pixel(world, spawn_x, spawn_y)
        res = world.find_water_tile_at_distance(sp_tx, sp_ty, 200, min_tiles=50)
        if res:
            gtx, gty = res
            world.sea_gem_px = gtx * TILE + TILE // 2
            world.sea_gem_py = gty * TILE + TILE // 2
            world.sea_gem_active = True
            print(f"[QUEST] Sea Gem spawned at tile ({gtx},{gty}) on start")
    except Exception:
        pass

    # Load player images
    player_img = None
    player_img_sword = None
    player_img_boat = None
    player_img_swimming = None
    gem_img = None
    player_img_path = os.path.join(os.path.dirname(__file__), 'Images', 'player.png')
    player_sword_path = os.path.join(os.path.dirname(__file__), 'Images', 'player_sword.png')
    player_boat_path = os.path.join(os.path.dirname(__file__), 'Images', 'player_boat.png')
    player_swimming_path = os.path.join(os.path.dirname(__file__), 'Images', 'player_swimming.png')
    try:
        player_img = pygame.image.load(player_img_path).convert_alpha()
        player_img = pygame.transform.scale(player_img, (PLAYER_SIZE, PLAYER_SIZE))
    except:
        pass
    try:
        player_img_sword = pygame.image.load(player_sword_path).convert_alpha()
        player_img_sword = pygame.transform.scale(player_img_sword, (PLAYER_SIZE, PLAYER_SIZE))
    except:
        player_img_sword = player_img  # Fallback to regular image
    try:
        player_img_boat = pygame.image.load(player_boat_path).convert_alpha()
        player_img_boat = pygame.transform.scale(player_img_boat, (PLAYER_SIZE, PLAYER_SIZE))
    except:
        pass
    try:
        player_img_swimming = pygame.image.load(player_swimming_path).convert_alpha()
        player_img_swimming = pygame.transform.scale(player_img_swimming, (PLAYER_SIZE, PLAYER_SIZE))
    except:
        pass

    # Load gem image if present
    gem_path = os.path.join(os.path.dirname(__file__), 'Images', 'gem.png')
    try:
        if os.path.exists(gem_path):
            gem_img = pygame.image.load(gem_path).convert_alpha()
            gem_img = pygame.transform.scale(gem_img, (TILE // 2, TILE // 2))
    except Exception:
        gem_img = None

    # Load animal (wolf) images if present
    wolf_img = None
    wolf_attack_img = None
    wolf_path = os.path.join(os.path.dirname(__file__), 'Images', 'Animals', 'Wolf.png')
    wolf_attack_path = os.path.join(os.path.dirname(__file__), 'Images', 'Animals', 'Wolf attack.png')
    try:
        if os.path.exists(wolf_path):
            wolf_img = pygame.image.load(wolf_path).convert_alpha()
            wolf_img = pygame.transform.scale(wolf_img, (PLAYER_SIZE, PLAYER_SIZE))
    except Exception:
        wolf_img = None
    try:
        if os.path.exists(wolf_attack_path):
            wolf_attack_img = pygame.image.load(wolf_attack_path).convert_alpha()
            wolf_attack_img = pygame.transform.scale(wolf_attack_img, (PLAYER_SIZE, PLAYER_SIZE))
    except Exception:
        wolf_attack_img = None

    # Load shop room background (room PNG that user will provide).
    # Prefer user images under `Images/Town Stuff/`, fallback to `Images/room.png`.
    # make sure shop gets loaded from Images/town Stuff/shop_img.png
    
    room_img = None
    shop_img = None
    town_dir = os.path.join(os.path.dirname(__file__), 'Images', 'Town Stuff')
    room_path1 = os.path.join(town_dir, 'room_img.png')
    shop_path1 = os.path.join(town_dir, 'shop_img.png')
    room_path2 = os.path.join(os.path.dirname(__file__), 'Images', 'room.png')
    try:
        if os.path.exists(room_path1):
            room_img = pygame.image.load(room_path1).convert()
        elif os.path.exists(room_path2):
            room_img = pygame.image.load(room_path2).convert()
        if room_img:
            # scale room image to the defined room rectangle size
            room_img = pygame.transform.scale(room_img, (world.room_rect.width, world.room_rect.height))
    except Exception:
        room_img = None
    # Load shop image for the world (blit over tiles). Prefer town dir.
    try:
        if os.path.exists(shop_path1):
            shop_img = pygame.image.load(shop_path1).convert_alpha()
            shop_img = pygame.transform.scale(shop_img, (world.shop.width * TILE, world.shop.height * TILE))
    except Exception:
        shop_img = None

    # attach shop image to world so draw_world can access it
    world.shop_img = shop_img

    show_quests = False

    quests = [
        {"id": "buy_boat", "title": "Buy a boat", "desc": "Buy a boat from the shop (cost 50 gold).", "done": False},
        {"id": "buy_sword", "title": "Buy a sword", "desc": "Buy a sword from the shop (cost 30 gold).", "done": False}
    ]
    # Add sea gem quest (player must take a boat and find it in the sea)
    quests.append({"id": "find_sea_gem", "title": "Find the Sea Gem", "desc": "Take a boat and find the hidden Sea Gem far out at sea.", "done": False})

    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0

        # Update animations
        world.update_animation(dt)
        
        # Update player cooldowns and attack animation timer
        if player.attack_cooldown > 0:
            player.attack_cooldown -= dt
        if player.attack_anim_timer > 0:
            player.attack_anim_timer -= dt

        # Update enemies and check collisions with player
        for enemy in list(enemies):
            enemy.update(dt, player, world)
            # Check if enemy touches player and deal damage
            dist_to_player = math.hypot(player.x - enemy.x, player.y - enemy.y)
            if dist_to_player < PLAYER_SIZE + 16 and enemy.attack_cooldown <= 0:
                # Use per-enemy attack rate and damage
                enemy.attack_cooldown = getattr(enemy, 'attack_rate', 1.5)
                damage = getattr(enemy, 'damage', 10)
                player.health = max(0, player.health - damage)
                # Trigger enemy attack animation briefly
                enemy.attack_anim_timer = 0.5
                print(f"[COMBAT] Enemy attacks! Player HP: {player.health}")
                if player.health <= 0:
                    print("[GAME OVER] Player defeated!")
                    # Respawn or go back to menu
                    player.health = player.max_health
                    in_main_menu = True
                    menu_state = 'main'
                    enemies.clear()
                    save_slots()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.MOUSEBUTTONDOWN:
                mx, my = event.pos
                if in_main_menu:
                    # if on main menu screen
                    if menu_state == 'main' and menu_rects:
                        for idx, r in enumerate(menu_rects):
                            if r.collidepoint((mx, my)):
                                if idx == 0:
                                    # Start -> go to slots screen
                                    menu_state = 'slots'
                                else:
                                    running = False
                                break
                    elif menu_state == 'slots' and slot_rects:
                        for si, r in enumerate(slot_rects):
                            if r.collidepoint((mx, my)):
                                # select this slot: create world and start
                                current_slot = si
                                world = World()
                                spawn_x, spawn_y = find_spawn_point(world)
                                player.x = spawn_x
                                player.y = spawn_y
                                # spawn gem for this world
                                try:
                                    sp_tx, sp_ty = world_tile_at_pixel(world, spawn_x, spawn_y)
                                    res = world.find_water_tile_at_distance(sp_tx, sp_ty, 200, min_tiles=50)
                                    if res:
                                        gtx, gty = res
                                        world.sea_gem_px = gtx * TILE + TILE // 2
                                        world.sea_gem_py = gty * TILE + TILE // 2
                                        world.sea_gem_active = True
                                except Exception:
                                    pass
                                world_slots[si]['created'] = True
                                # Spawn some initial enemies in the world
                                enemies.clear()
                                for _ in range(3):
                                    ex = random.randint(-20, 20) * TILE + TILE // 2
                                    ey = random.randint(-20, 20) * TILE + TILE // 2
                                    # Prefer spawning wolves if images are available
                                    if wolf_img and random.random() < 0.6:
                                        enemies.append(Enemy(ex, ey, etype='wolf', img=wolf_img, attack_img=wolf_attack_img))
                                    else:
                                        enemies.append(Enemy(ex, ey))
                                save_slots()
                                in_main_menu = False
                                menu_state = None
                                break
                continue
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_F3:
                    show_debug = not show_debug
                    continue
                # Menu keyboard navigation (kept for accessibility but menu uses clicks)
                if in_main_menu and menu_state == 'main':
                    if event.key == pygame.K_UP or event.key == pygame.K_w:
                        menu_index = (menu_index - 1) % len(menu_options)
                        continue
                    if event.key == pygame.K_DOWN or event.key == pygame.K_s:
                        menu_index = (menu_index + 1) % len(menu_options)
                        continue
                if event.key == pygame.K_ESCAPE:
                    if in_main_menu:
                        running = False
                        continue
                if event.key == pygame.K_ESCAPE:
                    if player.in_shop_room:
                        exit_shop(world, player)
                    else:
                        running = False
                elif event.key == pygame.K_e:
                    player.show_inventory = not player.show_inventory
                elif event.key == pygame.K_q and not player.in_shop_room:
                    show_quests = not show_quests
                elif event.key == pygame.K_b and player.in_shop_room:
                    # Toggle shop UI while inside the shop room
                    player.shop_ui_open = not player.shop_ui_open
                elif event.key == pygame.K_1 and player.in_shop_room:
                    # Buy boat
                    if player.gold >= player.inventory['boat']['cost']:
                        player.gold -= player.inventory['boat']['cost']
                        player.inventory['boat']['owned'] = True
                        player.has_boat = True
                        if quests[0]["id"] == "buy_boat":
                            quests[0]["done"] = True
                elif event.key == pygame.K_2 and player.in_shop_room:
                    # Buy sword
                    if player.gold >= player.inventory['sword']['cost']:
                        player.gold -= player.inventory['sword']['cost']
                        player.inventory['sword']['owned'] = True
                        player.has_sword = True
                        if quests[1]["id"] == "buy_sword":
                            quests[1]["done"] = True
                elif event.key == pygame.K_1 and not player.in_shop_room and not in_main_menu:
                    # Attack (stab) with sword if has sword
                    if player.has_sword and player.attack_cooldown <= 0:
                        player.attack_cooldown = 0.5  # 500ms cooldown
                        # Trigger attack animation (1 second)
                        player.attack_anim_timer = 1.0
                        # Check for nearby enemies to damage
                        for enemy in list(enemies):
                            dist = math.hypot(player.x - enemy.x, player.y - enemy.y)
                            if dist < 80:  # Attack range
                                damage = 25
                                enemy.health -= damage
                                print(f"[COMBAT] Hit enemy for {damage} damage! Enemy HP: {enemy.health}")
                                if enemy.health <= 0:
                                    enemies.remove(enemy)
                                    player.gold += 10
                                    print("[COMBAT] Enemy defeated! +10 gold")

        # movement
        keys = pygame.key.get_pressed()
        dx = dy = 0.0
        if keys[pygame.K_w] or keys[pygame.K_UP]:
            dy -= 1
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:
            dy += 1
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:
            dx -= 1
            player.facing_left = True
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
            dx += 1
            player.facing_left = False

        # normalize
        if dx != 0 or dy != 0:
            length = math.hypot(dx, dy)
            dx /= length
            dy /= length

        if player.in_shop_room:
            # In shop room: use room-local coordinates (relative to room top-left)
            base_x = player.room_x if player.room_x is not None else (PLAYER_SIZE // 2 + 8)
            base_y = player.room_y if player.room_y is not None else (PLAYER_SIZE // 2 + 8)
            nx = base_x + dx * player.speed * dt
            ny = base_y + dy * player.speed * dt
            # If player attempts to move beyond the bottom wall (room-local coords), exit the room.
            if ny + (PLAYER_SIZE // 2) >= world.room_rect.height:
                # player touched bottom wall -> exit shop
                exit_shop(world, player)
            else:
                left_rel = PLAYER_SIZE // 2
                right_rel = world.room_rect.width - (PLAYER_SIZE // 2)
                top_rel = PLAYER_SIZE // 2
                # clamp to room interior (relative coords)
                nx = max(left_rel, min(nx, right_rel))
                ny = max(top_rel, min(ny, world.room_rect.height - (PLAYER_SIZE // 2)))
                player.room_x = nx
                player.room_y = ny
        else:
            nx = player.x + dx * player.speed * dt
            ny = player.y + dy * player.speed * dt
            # In world: collision check
            if can_move_to(world, player, nx, ny):
                player.x = nx
                player.y = ny
            
            # Check if player is at shop entrance and enter
            check_shop_entry(world, player)

        # camera centers on player (unless in shop room)
        if player.in_shop_room:
            cam_x = SCREEN_W // 2
            cam_y = SCREEN_H // 2
        else:
            cam_x = player.x
            cam_y = player.y

        # draw
        # If main menu active: draw menu and skip game rendering
        if in_main_menu:
            # Black background and pixel-style title
            screen.fill((0, 0, 0))
            title_font = pygame.font.SysFont('Courier', 72, bold=True)
            title_surf = title_font.render("NINJA QUEST", True, (240, 240, 255))
            screen.blit(title_surf, (SCREEN_W//2 - title_surf.get_width()//2, 80))
            # Menu
            mfont = pygame.font.SysFont('Courier', 36)
            menu_rects.clear()
            if menu_state == 'main':
                for i, opt in enumerate(menu_options):
                    color = (255, 220, 100) if i == menu_index else (200, 200, 200)
                    txt = mfont.render(opt, True, color)
                    tx = SCREEN_W//2 - txt.get_width()//2
                    ty = 220 + i * 72
                    rect = pygame.Rect(tx - 8, ty - 4, txt.get_width() + 16, txt.get_height() + 8)
                    pygame.draw.rect(screen, (20,20,20), rect)
                    screen.blit(txt, (tx, ty))
                    menu_rects.append(rect)
                screen.blit(font.render("Click Start. F3 for debug.", True, (180,180,180)), (SCREEN_W//2 - 160, 420))
            elif menu_state == 'slots':
                # Draw slot list
                slot_rects.clear()
                sfont = pygame.font.SysFont('Courier', 28)
                screen.blit(font.render("Select a World Slot:", True, (200,200,200)), (SCREEN_W//2 - 140, 170))
                for i, slot in enumerate(world_slots):
                    label = slot['name'] + (" - New" if not slot['created'] else " - Exists")
                    txt = sfont.render(label, True, (220,220,220))
                    tx = SCREEN_W//2 - 200
                    ty = 220 + i * 64
                    rect = pygame.Rect(tx, ty, 400, 48)
                    pygame.draw.rect(screen, (18,18,18), rect)
                    pygame.draw.rect(screen, (80,80,80), rect, 2)
                    screen.blit(txt, (tx + 12, ty + 8))
                    slot_rects.append(rect)
                screen.blit(font.render("Click a slot to create/start.", True, (180,180,180)), (SCREEN_W//2 - 160, 420))

            pygame.display.flip()
            continue

        # If inside the shop room, render the smaller room (room_rect) with the room background.
        if player.in_shop_room:
            # fill screen with dark background
            screen.fill((10, 10, 10))
            if room_img:
                # room_img was pre-scaled to room_rect size
                screen.blit(room_img, world.room_rect.topleft)
            else:
                # draw a black room area and a light border to represent walls
                pygame.draw.rect(screen, (0, 0, 0), world.room_rect)
                pygame.draw.rect(screen, (80, 80, 80), world.room_rect, 4)
        else:
            screen.fill((0, 0, 0))
            draw_world(screen, world, cam_x, cam_y)

        # draw player
        player_screen_x = SCREEN_W // 2
        player_screen_y = SCREEN_H // 2
        
        # Determine player state
        is_in_water = False
        if not player.in_shop_room:
            player_tx, player_ty = world_tile_at_pixel(world, player.x, player.y)
            is_in_water = world.is_water(player_tx, player_ty)

        # Sea gem spawn: when player is in water and has a boat, spawn gem ~200 tiles away
        if not player.in_shop_room and is_in_water and player.has_boat and not world.sea_gem_active:
            # Only spawn if quest not already completed
            found_q = next((q for q in quests if q.get('id') == 'find_sea_gem'), None)
            if found_q is not None and not found_q.get('done', False):
                res = world.find_water_tile_at_distance(player_tx, player_ty, 200, min_tiles=50)
                if res:
                    gtx, gty = res
                    world.sea_gem_px = gtx * TILE + TILE // 2
                    world.sea_gem_py = gty * TILE + TILE // 2
                    world.sea_gem_active = True
                    print(f"[QUEST] Sea Gem spawned at tile ({gtx},{gty})")

        # Sea gem pickup detection (when in world)
        if not player.in_shop_room and world.sea_gem_active and world.sea_gem_px is not None:
            dist_to_gem = math.hypot(player.x - world.sea_gem_px, player.y - world.sea_gem_py)
            if dist_to_gem < PLAYER_SIZE:
                # Pickup
                world.sea_gem_active = False
                world.sea_gem_px = None
                world.sea_gem_py = None
                # mark quest done and reward
                q = next((qq for qq in quests if qq.get('id') == 'find_sea_gem'), None)
                if q:
                    q['done'] = True
                player.gold += 200
                print("[QUEST] Sea Gem found! Reward: 200 gold")
        
        # Select appropriate player image (attack animation has priority)
        if player.attack_anim_timer > 0 and player_img_sword:
            # Show attack/sword pose during attack
            current_player_img = player_img_sword
        else:
            if is_in_water:
                # In water: show boat if has boat, else swimming
                if player.has_boat and player_img_boat:
                    current_player_img = player_img_boat
                elif player_img_swimming:
                    current_player_img = player_img_swimming
                else:
                    current_player_img = player_img  # Fallback
            else:
                # On land or in shop: normally show base player image; sword only shown as attack pose
                current_player_img = player_img
        
        # Flip sprite if facing left
        if current_player_img:
            display_img = pygame.transform.flip(current_player_img, not player.facing_left, False)
            # When inside shop room, draw player relative to the fixed room rectangle so the room doesn't move.
            if player.in_shop_room and player.room_x is not None and player.room_y is not None:
                p_screen_x = world.room_rect.left + player.room_x
                p_screen_y = world.room_rect.top + player.room_y
                screen.blit(display_img, (p_screen_x - PLAYER_SIZE // 2, p_screen_y - PLAYER_SIZE // 2))
            else:
                screen.blit(display_img, (player_screen_x - PLAYER_SIZE // 2, player_screen_y - PLAYER_SIZE // 2))
        else:
            # Fallback: draw colored rect
            if is_in_water:
                color = (0, 100, 200) if player.has_boat else (100, 150, 255)
            else:
                color = (150, 30, 150) if player.has_sword else (200, 30, 30)
            if player.in_shop_room and player.room_x is not None and player.room_y is not None:
                p_screen_x = world.room_rect.left + player.room_x
                p_screen_y = world.room_rect.top + player.room_y
                pygame.draw.rect(screen, color, (p_screen_x - PLAYER_SIZE // 2, p_screen_y - PLAYER_SIZE // 2, PLAYER_SIZE, PLAYER_SIZE))
            else:
                pygame.draw.rect(screen, color, (player_screen_x - PLAYER_SIZE // 2, player_screen_y - PLAYER_SIZE // 2, PLAYER_SIZE, PLAYER_SIZE))

        # Draw enemies (with their images if available)
        for enemy in enemies:
            ex_screen = enemy.x - (cam_x - SCREEN_W // 2)
            ey_screen = enemy.y - (cam_y - SCREEN_H // 2)
            # choose attack image if enemy is in attack animation
            eimg = None
            if getattr(enemy, 'attack_anim_timer', 0) > 0 and getattr(enemy, 'attack_img', None):
                eimg = enemy.attack_img
            elif getattr(enemy, 'img', None):
                eimg = enemy.img

            if eimg:
                screen.blit(eimg, (int(ex_screen - PLAYER_SIZE // 2), int(ey_screen - PLAYER_SIZE // 2)))
            else:
                # fallback draw
                pygame.draw.rect(screen, (120, 40, 40), (int(ex_screen - PLAYER_SIZE // 2), int(ey_screen - PLAYER_SIZE // 2), PLAYER_SIZE, PLAYER_SIZE))

        # HUD
        hud_bg = pygame.Surface((400, 110))
        hud_bg.set_alpha(220)
        hud_bg.fill((20, 20, 20))
        screen.blit(hud_bg, (10, 10))
        screen.blit(font.render(f"Gold: {player.gold}", True, (255, 215, 0)), (18, 16))
        screen.blit(font.render(f"Boat: {'Yes' if player.has_boat else 'No'}", True, (200, 200, 200)), (18, 40))
        screen.blit(font.render(f"Sword: {'Yes' if player.has_sword else 'No'}", True, (200, 100, 100)), (18, 64))
        screen.blit(font.render(f"HP: {player.health}/{player.max_health}", True, (100, 200, 100) if player.health > 30 else (255, 100, 100)), (18, 88))

        # Shop UI (open only when toggled with B)
        if player.in_shop_room and player.shop_ui_open:
            shop_rect = pygame.Rect(120, 150, 560, 350)
            pygame.draw.rect(screen, (30, 30, 40), shop_rect)
            pygame.draw.rect(screen, (200, 200, 200), shop_rect, 2)
            screen.blit(font.render("Shop - Press B to browse or 1/2 to buy", True, (255, 255, 255)), (shop_rect.x + 16, shop_rect.y + 12))

            # item: Boat
            y = shop_rect.y + 60
            boat_status = "OWNED" if player.inventory['boat']['owned'] else f"{player.inventory['boat']['cost']} gold"
            screen.blit(font.render(f"1) {player.inventory['boat']['name']} - {boat_status}", True, (200, 200, 200)), (shop_rect.x + 16, y))
            if not player.inventory['boat']['owned']:
                screen.blit(font.render("Press 1 to buy", True, (180, 180, 180)), (shop_rect.x + 380, y))

            # item: Sword
            y = shop_rect.y + 100
            sword_status = "OWNED" if player.inventory['sword']['owned'] else f"{player.inventory['sword']['cost']} gold"
            screen.blit(font.render(f"2) {player.inventory['sword']['name']} - {sword_status}", True, (200, 200, 200)), (shop_rect.x + 16, y))
            if not player.inventory['sword']['owned']:
                screen.blit(font.render("Press 2 to buy", True, (180, 180, 180)), (shop_rect.x + 380, y))
            
            screen.blit(font.render("Press Esc to exit shop", True, (180, 180, 180)), (shop_rect.x + 16, shop_rect.y + 280))

        # Inventory UI (when E is pressed)
        if player.show_inventory:
            inv_rect = pygame.Rect(50, 100, 300, 400)
            pygame.draw.rect(screen, (20, 20, 30), inv_rect)
            pygame.draw.rect(screen, (150, 150, 200), inv_rect, 2)
            screen.blit(font.render("Inventory", True, (200, 200, 255)), (inv_rect.x + 16, inv_rect.y + 12))
            
            y = inv_rect.y + 50
            screen.blit(font.render(f"Gold: {player.gold}", True, (255, 215, 0)), (inv_rect.x + 16, y))
            
            y += 40
            screen.blit(font.render("Items:", True, (200, 200, 200)), (inv_rect.x + 16, y))
            
            y += 30
            for item_key, item in player.inventory.items():
                if item['owned']:
                    screen.blit(font.render(f"- {item['name']}", True, (100, 200, 100)), (inv_rect.x + 30, y))
                    y += 25
            
            screen.blit(font.render("Press E to close", True, (180, 180, 180)), (inv_rect.x + 16, inv_rect.y + 360))

        if show_quests and not player.in_shop_room:
            qrect = pygame.Rect(20, 120, 320, 260)
            pygame.draw.rect(screen, (24, 28, 36), qrect)
            pygame.draw.rect(screen, (200, 200, 200), qrect, 2)
            screen.blit(font.render("Quests", True, (255, 255, 255)), (qrect.x + 12, qrect.y + 8))
            yy = qrect.y + 36
            for q in quests:
                status = "Done" if q["done"] else "Open"
                screen.blit(font.render(f"- {q['title']} [{status}]", True, (220, 220, 220)), (qrect.x + 12, yy))
                yy += 28

        # Debug overlay (top-right) - toggled with F3
        if show_debug:
            fps = int(clock.get_fps())
            tiles_loaded = sum(1 for v in world.tile_cache.values() if v is not None)
            px = player.x
            py = player.y
            tx, ty = world_tile_at_pixel(world, player.x, player.y)
            dbg_lines = [f"FPS: {fps}", f"Pos: {px:.1f},{py:.1f}", f"Tile: {tx},{ty}", f"Tiles loaded: {tiles_loaded}"]
            # Sea gem debug info
            if getattr(world, 'sea_gem_active', False) and getattr(world, 'sea_gem_px', None) is not None:
                gpx = world.sea_gem_px
                gpy = world.sea_gem_py
                gtx = int(math.floor(gpx / TILE))
                gty = int(math.floor(gpy / TILE))
                dist_tiles = int(round(math.hypot(px - gpx, py - gpy) / TILE))
                dbg_lines.append(f"SeaGem: Active @ {gtx},{gty} ({dist_tiles} tiles)")
            else:
                dbg_lines.append("SeaGem: none")
            dbg_w = 220
            dbg_h = 20 + 18 * len(dbg_lines)
            dbg_rect = pygame.Rect(SCREEN_W - dbg_w - 10, 10, dbg_w, dbg_h)
            s = pygame.Surface((dbg_rect.width, dbg_rect.height))
            s.set_alpha(200)
            s.fill((8, 8, 12))
            screen.blit(s, dbg_rect.topleft)
            for i, line in enumerate(dbg_lines):
                screen.blit(font.render(line, True, (200, 200, 200)), (dbg_rect.x + 8, dbg_rect.y + 8 + i * 18))

        # Draw sea gem (if active)
        if not player.in_shop_room and getattr(world, 'sea_gem_px', None) is not None:
            # compute screen coords
            gx = world.sea_gem_px - (cam_x - SCREEN_W // 2)
            gy = world.sea_gem_py - (cam_y - SCREEN_H // 2)
            # If a gem image was provided, draw it centered; otherwise fallback to a pulsing circle
            if gem_img:
                gw, gh = gem_img.get_size()
                screen.blit(gem_img, (int(gx - gw/2), int(gy - gh/2)))
            else:
                pulse = 4 + (world.animation_frame % 2) * 2
                pygame.draw.circle(screen, (255, 215, 0), (int(gx), int(gy)), 8 + pulse)
                pygame.draw.circle(screen, (255, 255, 255), (int(gx), int(gy)), 4)

        pygame.display.flip()

    pygame.quit()
    sys.exit()


if __name__ == '__main__':
    main()
