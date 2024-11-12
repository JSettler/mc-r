# License: AGPLv3  (GNU Affero GPL, for maximum protection of software freedom)
# MopeClassic-Remake/Revival/Reloaded/Return (MC-R)

import pygame
import random
import math
import json
import os
import sys
import numpy as np



class Game:
    def __init__(self):
        pygame.init()
        
        # Constants
        self.MINIMUM_BOTS = 35   # with 20, the performance is excellent; at 40, collisions don't work 100% anymore
        
        # Try to load saved game first
        self.should_load = False
        if os.path.exists('mcr_savegame.json'):
            temp_screen = pygame.display.set_mode((400, 200))
            font = pygame.font.Font(None, 36)
            asking = True
            while asking:
                temp_screen.fill((20, 20, 20))
                text = font.render("Load saved game? (Y/N)", True, (255, 255, 255))
                temp_screen.blit(text, (100, 80))
                pygame.display.flip()
                
                for event in pygame.event.get():
                    if event.type == pygame.KEYDOWN:
                        if event.key == pygame.K_y:
                            self.should_load = True
                            asking = False
                        elif event.key == pygame.K_n:
                            asking = False
                    elif event.type == pygame.QUIT:
                        pygame.quit()
                        sys.exit()

        self.screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        self.width = self.screen.get_width()
        self.height = self.screen.get_height()
        self.clock = pygame.time.Clock()
        self.running = True
        self.map_size = (self.width * 6, self.height * 6)
        self.camera_offset = [0, 0]
        
        # Create player first (will be positioned properly later)
        self.player = Player(0, 0)
        
        self.foods = []
        self.obstacles = []
        self.creatures = []
        self.bot_colors = {}
        self.next_bot_id = 1
        
        self.start_time = pygame.time.get_ticks()
        self.food_eaten_count = 0

        if self.should_load:
            self.load_game()
        else:
            self.generate_obstacles(50)
            # Update player position after obstacles are generated
            safe_x, safe_y = self.find_safe_spawn_position(40)
            self.player.x = safe_x
            self.player.y = safe_y
            self.generate_foods(200)  # Increased from 100 to 200
            self.generate_creatures(self.MINIMUM_BOTS)



    def save_game(self):
        save_data = {
            'player': {
                'x': self.player.x,
                'y': self.player.y,
                'level': self.player.level,
                'nutrition': self.player.nutrition,
                'hp': self.player.hp,
                'radius': self.player.radius
            },
            'creatures': [{
                'x': c.x,
                'y': c.y,
                'level': c.level,
                'nutrition': c.nutrition,
                'hp': c.hp,
                'bot_id': c.bot_id,
                'color': c.color
            } for c in self.creatures],
            'foods': [{
                'x': f.x,
                'y': f.y,
                'nutrition': f.nutrition,
                'size': f.size,
                'points': f.points
            } for f in self.foods],
            'obstacles': [{
                'x': o.x,
                'y': o.y,
                'size': o.size
            } for o in self.obstacles],
            'bot_colors': self.bot_colors,
            'next_bot_id': self.next_bot_id
        }
        
        with open('mcr_savegame.json', 'w') as f:
            json.dump(save_data, f)



    def load_game(self):
        if not os.path.exists('mcr_savegame.json'):
            return False
            
        try:
            with open('mcr_savegame.json', 'r') as f:
                save_data = json.load(f)
            
            # Load player
            self.player.x = save_data['player']['x']
            self.player.y = save_data['player']['y']
            self.player.level = save_data['player']['level']
            self.player.nutrition = save_data['player']['nutrition']
            self.player.hp = save_data['player']['hp']
            self.player.radius = save_data['player']['radius']
            
            # Load creatures
            self.creatures = []
            for c_data in save_data['creatures']:
                creature = Creature(c_data['x'], c_data['y'], 
                                 c_data['level'], c_data['bot_id'], 
                                 tuple(c_data['color']))
                creature.nutrition = c_data['nutrition']
                creature.hp = c_data['hp']
                self.creatures.append(creature)
            
            # Load foods
            self.foods = []
            for f_data in save_data['foods']:
                food = Food(f_data['x'], f_data['y'], f_data['nutrition'])
                food.size = f_data['size']
                food.points = [tuple(p) for p in f_data['points']]
                self.foods.append(food)
            
            # Load obstacles
            self.obstacles = []
            for o_data in save_data['obstacles']:
                self.obstacles.append(Obstacle(o_data['x'], o_data['y'], 
                                            o_data['size']))
            
            # Load other game state
            self.bot_colors = {int(k): tuple(v) for k, v in save_data['bot_colors'].items()}
            self.next_bot_id = save_data['next_bot_id']
            
            return True
        except Exception as e:
            print(f"Error loading game: {e}")
            return False


    def check_obstacle_placement(self, x, y, size, shape, existing_obstacles):
        """Check if a new obstacle can be placed here"""
        MIN_GAP = 10  # Minimum gap between obstacles
        
        for obstacle in existing_obstacles:
            # Calculate the minimum required distance between obstacles
            if shape == 'circle' and obstacle.shape == 'circle':
                min_distance = size + obstacle.size + MIN_GAP
                actual_distance = math.sqrt((x - obstacle.x)**2 + (y - obstacle.y)**2)
                if actual_distance < min_distance:
                    return False
                    
            elif shape == 'rectangle' and obstacle.shape == 'rectangle':
                # For rectangles, check if they're too close on any axis
                new_width = size * 2
                new_height = size * 1.5
                
                dx = abs(x - obstacle.x) - (new_width/2 + obstacle.width/2)
                dy = abs(y - obstacle.y) - (new_height/2 + obstacle.height/2)
                
                if dx < MIN_GAP and dy < MIN_GAP:
                    return False
                    
            else:
                # Mixed shapes (circle-rectangle)
                if shape == 'circle':
                    circle_x, circle_y, circle_r = x, y, size
                    rect_x = obstacle.x
                    rect_y = obstacle.y
                    rect_width = obstacle.width
                    rect_height = obstacle.height
                else:
                    circle_x, circle_y, circle_r = obstacle.x, obstacle.y, obstacle.size
                    rect_x = x
                    rect_y = y
                    rect_width = size * 2
                    rect_height = size * 1.5
                
                # Find closest point on rectangle to circle
                closest_x = max(rect_x - rect_width/2, 
                              min(circle_x, rect_x + rect_width/2))
                closest_y = max(rect_y - rect_height/2, 
                              min(circle_y, rect_y + rect_height/2))
                
                # Check distance between closest point and circle center
                distance = math.sqrt((circle_x - closest_x)**2 + 
                                   (circle_y - closest_y)**2)
                if distance < (circle_r + MIN_GAP):
                    return False
        
        return True


    def generate_obstacles(self, count):
        map_area = self.map_size[0] * self.map_size[1]
        target_coverage = 0.06  # 6% coverage
        current_coverage = 0
        max_attempts = 1000
        
        # Generate regular obstacles
        for _ in range(count):
            attempts = 0
            while attempts < max_attempts:
                size = random.randint(20, 100)
                shape = random.choice(['circle', 'rectangle'])
                x = random.randint(size, self.map_size[0] - size)
                y = random.randint(size, self.map_size[1] - size)
                
                if self.check_obstacle_placement(x, y, size, shape, self.obstacles):
                    obstacle = Obstacle(x, y, size, shape)
                    self.obstacles.append(obstacle)
                    if shape == 'circle':
                        current_coverage += math.pi * size * size
                    else:
                        current_coverage += size * 2 * size * 1.5
                    break
                attempts += 1
        
        # Generate large obstacles until we reach target coverage
        attempts = 0
        while current_coverage / map_area < target_coverage and attempts < max_attempts:
            size = random.randint(150, 200)
            shape = random.choice(['circle', 'rectangle'])
            x = random.randint(size, self.map_size[0] - size)
            y = random.randint(size, self.map_size[1] - size)
            
            if self.check_obstacle_placement(x, y, size, shape, self.obstacles):
                obstacle = Obstacle(x, y, size, shape)
                self.obstacles.append(obstacle)
                if shape == 'circle':
                    current_coverage += math.pi * size * size
                else:
                    current_coverage += size * 2 * size * 1.5
            
            attempts += 1
            


    def generate_foods(self, count):
            for _ in range(count):
                while True:
                    x = random.randint(0, self.map_size[0])
                    y = random.randint(0, self.map_size[1])
                    # Check if position overlaps with any obstacle
                    valid_position = True
                    for obstacle in self.obstacles:
                        if check_collision(x, y, 15, obstacle.x, obstacle.y, obstacle.size):
                            valid_position = False
                            break
                    if valid_position:
                        break
                
                # 70% chance for tiny food (5-10 NU), 30% chance for larger food
                if random.random() < 0.7:
                    nutrition = random.randint(5, 10)
                else:
                    nutrition = random.randint(11, 20)
                self.foods.append(Food(x, y, nutrition))
            

    def find_safe_spawn_position(self, min_distance_from_obstacles):
        """Find a spawn position that's away from all obstacles"""
        max_attempts = 1000
        attempts = 0
        
        while attempts < max_attempts:
            x = random.randint(0, self.map_size[0])
            y = random.randint(0, self.map_size[1])
            
            # Check distance from all obstacles
            safe_position = True
            for obstacle in self.obstacles:
                # Add buffer distance to obstacle size
                if check_collision(x, y, min_distance_from_obstacles, 
                                 obstacle.x, obstacle.y, 
                                 obstacle.size + min_distance_from_obstacles,
                                 obstacle.shape):
                    safe_position = False
                    break
                    
            if safe_position:
                return x, y
                
            attempts += 1
        
        # If no position found after max attempts, find the position furthest from all obstacles
        best_x, best_y = self.map_size[0]//2, self.map_size[1]//2
        best_min_distance = 0
        
        for _ in range(100):
            x = random.randint(0, self.map_size[0])
            y = random.randint(0, self.map_size[1])
            
            min_distance = float('inf')
            for obstacle in self.obstacles:
                dist = math.sqrt((x - obstacle.x)**2 + (y - obstacle.y)**2) - obstacle.size
                min_distance = min(min_distance, dist)
            
            if min_distance > best_min_distance:
                best_min_distance = min_distance
                best_x, best_y = x, y
        
        return best_x, best_y



    def generate_creatures(self, count):
        attempts = 0
        max_attempts = 100
        spawned = 0
        min_distance_to_player = 800
        min_distance_to_obstacles = 40

        while spawned < count and attempts < max_attempts:
            # Find safe position away from obstacles
            safe_x, safe_y = self.find_safe_spawn_position(min_distance_to_obstacles)
            
            # Check distance to player
            distance_to_player = math.sqrt((safe_x - self.player.x)**2 + 
                                         (safe_y - self.player.y)**2)
            
            if distance_to_player < min_distance_to_player:
                attempts += 1
                continue
            
            # Position is safe, spawn creature
            bot_id = self.next_bot_id
            self.next_bot_id += 1
            color = (random.randint(50, 255), random.randint(50, 255), random.randint(50, 255))
            self.bot_colors[bot_id] = color
            self.creatures.append(Creature(safe_x, safe_y, 1, bot_id, color))
            spawned += 1
            
            attempts += 1



    def spawn_food(self):
        if random.random() < 0.4:  # Increased from 0.1 to 0.4 (40% chance per frame)
            while True:
                x = random.randint(0, self.map_size[0])
                y = random.randint(0, self.map_size[1])
                valid_position = True
                for obstacle in self.obstacles:
                    if check_collision(x, y, 15, obstacle.x, obstacle.y, obstacle.size):
                        valid_position = False
                        break
                if valid_position:
                    break
            
            # Different spawn rates for different food sizes
            r = random.random()
            if r < 0.7:
                nutrition = random.randint(5, 10)
            elif r < 0.9:
                nutrition = random.randint(11, 15)
            else:
                nutrition = random.randint(16, 20)
            self.foods.append(Food(x, y, nutrition))



    def draw_world_border(self):
        border_rect = pygame.Rect(-self.camera_offset[0], -self.camera_offset[1], 
                                self.map_size[0], self.map_size[1])
        pygame.draw.rect(self.screen, (50, 50, 50), border_rect, 2)


            
    def update_camera(self):
        self.camera_offset[0] = self.player.x - self.width // 2
        self.camera_offset[1] = self.player.y - self.height // 2
        

    def draw_radar(self):
        radar_size = 200
        radar_surface = pygame.Surface((radar_size, radar_size))
        radar_surface.fill((0, 0, 0))
        pygame.draw.rect(radar_surface, (50, 50, 50), (0, 0, radar_size, radar_size), 1)
        
        scale_x = radar_size / self.map_size[0]
        scale_y = radar_size / self.map_size[1]
        
        # Draw obstacles with proper scaling
        for obstacle in self.obstacles:
            pos_x = int(obstacle.x * scale_x)
            pos_y = int(obstacle.y * scale_y)
            scaled_size = int(obstacle.size * scale_x)  # Scale the size too
            pygame.draw.circle(radar_surface, (100, 100, 100), (pos_x, pos_y), scaled_size)
            
        # Draw player
        player_radar_x = int(self.player.x * scale_x)
        player_radar_y = int(self.player.y * scale_y)
        pygame.draw.circle(radar_surface, (0, 255, 0), (player_radar_x, player_radar_y), 3)
        
        # Draw other creatures
        for creature in self.creatures:
            creature_x = int(creature.x * scale_x)
            creature_y = int(creature.y * scale_y)
            pygame.draw.circle(radar_surface, creature.color, (creature_x, creature_y), 2)
        
        self.screen.blit(radar_surface, (self.width - radar_size - 10, 10))
        


    def draw_highscore_table(self):
        all_creatures = self.creatures + [self.player]
        sorted_creatures = sorted(all_creatures, 
                                key=lambda x: (x.level, x.nutrition), 
                                reverse=True)[:10]
        
        start_y = 220
        name_x = self.width - 200  # Fixed x position for names
        bar_x = self.width - 100   # Fixed x position for all bars
        bar_width = 50  # Fixed width for all bars
        bar_height = 5
        
        for i, creature in enumerate(sorted_creatures):
            font = pygame.font.Font(None, 24)
            if isinstance(creature, Player):
                text = f"player {creature.level}"
                color = (0, 255, 0)
            else:
                text = f"bot{creature.bot_id} {creature.level}"
                color = creature.color
            
            # Draw name and level at fixed position
            text_surface = font.render(text, True, color)
            self.screen.blit(text_surface, 
                           (name_x, start_y + i * 25))
            
            # Draw progress bar at fixed position
            required_nutrition = calculate_required_nutrition(creature.level)
            progress = min(1.0, creature.nutrition / required_nutrition)  # Clamp to 1.0
            
            bar_y = start_y + i * 25 + 10
            
            # Background bar (grey)
            pygame.draw.rect(self.screen, (50, 50, 50),
                           (bar_x, bar_y, bar_width, bar_height))
            # Progress bar (colored)
            filled_width = int(bar_width * progress)
            pygame.draw.rect(self.screen, color,
                           (bar_x, bar_y, filled_width, bar_height))



    def run(self):
        while self.running:
            current_time = pygame.time.get_ticks()
            
            for event in pygame.event.get():
                if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                    self.save_game()  # Auto-save on exit
                    self.running = False
            
            # Maintain bot count
            missing_bots = self.MINIMUM_BOTS - len(self.creatures)
            if missing_bots > 0:
                self.generate_creatures(missing_bots)
            
            # Spawn new food
            self.spawn_food()
            
            keys = pygame.key.get_pressed()
            self.player.move(keys, self.map_size, self.obstacles)
            if handle_collisions(self):  # Check if game over occurred
                return  # Exit the game loop if game is over
            
            self.update_camera()
            
            self.screen.fill((20, 20, 20))
            
            self.draw_world_border()
            
            for obstacle in self.obstacles:
                obstacle.draw(self.screen, self.camera_offset)
            
            for food in self.foods:
                food.draw(self.screen, self.camera_offset)
                
            for creature in self.creatures:
                # Updated method call with all required parameters
                creature.move_towards_food(self.map_size, self.obstacles, self.foods, 
                                        self.creatures, self.player)
                creature.draw(self.screen, self.camera_offset)
                
            self.player.draw(self.screen, self.camera_offset)
            self.draw_radar()
            self.draw_highscore_table()
            
            pygame.display.flip()
            self.clock.tick(60)
            
        pygame.quit()



    def show_game_over_screen(self, killer_level):
        # Prepare statistics
        play_time = (pygame.time.get_ticks() - self.start_time) / 1000  # Convert to seconds
        food_eaten = self.food_eaten_count
        max_level = self.player.level
        
        # Create semi-transparent overlay
        overlay = pygame.Surface((self.width, self.height))
        overlay.fill((0, 0, 0))
        overlay.set_alpha(128)
        self.screen.blit(overlay, (0, 0))
        
        # Prepare text
        font_large = pygame.font.Font(None, 74)
        font_small = pygame.font.Font(None, 36)
        
        texts = [
            (font_large.render("GAME OVER", True, (255, 0, 0)), 0),
            (font_small.render(f"Survived for: {int(play_time)} seconds", True, (255, 255, 255)), 100),
            (font_small.render(f"Maximum level reached: {max_level}", True, (255, 255, 255)), 150),
            (font_small.render(f"Food items eaten: {food_eaten}", True, (255, 255, 255)), 200),
            (font_small.render(f"Eaten by a level {killer_level} creature", True, (255, 255, 255)), 250),
            (font_small.render("Press SPACE to exit", True, (255, 255, 255)), 350)
        ]
        
        # Show game over screen until space is pressed
        waiting = True
        while waiting:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    waiting = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_SPACE:
                        waiting = False
            
            # Draw all texts centered on screen
            for text, y_offset in texts:
                text_rect = text.get_rect(center=(self.width // 2, self.height // 2 - 100 + y_offset))
                self.screen.blit(text, text_rect)
            
            pygame.display.flip()
            self.clock.tick(60)
        
        self.running = False



class Player:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.level = 1
        self.nutrition = 0
        self.hp = 100
        self.speed = 10
        self.base_radius = 15
        self.radius = self.base_radius + 1
        self.dead_zone = 20
        

    def level_up(self):
        self.level += 1
        self.radius = self.base_radius + self.level  # Slower growth rate



    def move(self, keys, map_size, obstacles):
        mouse_x, mouse_y = pygame.mouse.get_pos()
        center_x = pygame.display.get_surface().get_width() // 2
        center_y = pygame.display.get_surface().get_height() // 2
        
        dx = mouse_x - center_x
        dy = mouse_y - center_y
        distance = math.sqrt(dx**2 + dy**2)
        
        if distance > self.dead_zone:
            angle = math.atan2(dy, dx)
            new_x = self.x + math.cos(angle) * self.speed
            new_y = self.y + math.sin(angle) * self.speed
            
            # Use the new sliding movement
            self.x, self.y = move_with_sliding(self, new_x, new_y, obstacles)
            
            # Keep within map bounds
            self.x = max(self.radius, min(map_size[0] - self.radius, self.x))
            self.y = max(self.radius, min(map_size[1] - self.radius, self.y))

        

    def draw(self, screen, camera_offset):
        pos_x = int(self.x - camera_offset[0])
        pos_y = int(self.y - camera_offset[1])
        pygame.draw.circle(screen, (0, 255, 0), (pos_x, pos_y), self.radius)
        
        font = pygame.font.Font(None, 24)
        level_text = font.render(str(self.level), True, (255, 255, 255))
        text_rect = level_text.get_rect(center=(pos_x, pos_y))
        screen.blit(level_text, text_rect)



class Food:
    def __init__(self, x, y, nutrition):
        self.x = x
        self.y = y
        self.nutrition = nutrition
        self.size = 10 + nutrition
        self.points = self.generate_polygon()
        self.color = (100 + nutrition * 5, 50, 50)
        
    def generate_polygon(self):
        points = []
        num_points = random.randint(3, 6)
        for i in range(num_points):
            angle = 2 * math.pi * i / num_points
            r = random.uniform(0.8, 1.2) * self.size
            x = self.x + r * math.cos(angle)
            y = self.y + r * math.sin(angle)
            points.append((x, y))
        return points
        
    def draw(self, screen, camera_offset):
        adjusted_points = [(x - camera_offset[0], y - camera_offset[1]) for x, y in self.points]
        pygame.draw.polygon(screen, self.color, adjusted_points)


class Obstacle:
    def __init__(self, x, y, size, shape='circle'):
        self.x = x
        self.y = y
        self.size = size
        self.shape = shape
        if shape == 'rectangle':
            self.width = size * 2
            self.height = size * 1.5
        else:
            self.width = self.height = size
        
        # Generate random grey or brown color
        color_type = random.choice(['grey', 'brown'])
        if color_type == 'grey':
            base = random.randint(80, 120)
            self.color = (base, base, base)
        else:
            self.color = (
                random.randint(100, 139),  # R
                random.randint(60, 99),    # G
                random.randint(20, 59)     # B
            )
    
    def draw(self, screen, camera_offset):
        pos_x = int(self.x - camera_offset[0])
        pos_y = int(self.y - camera_offset[1])
        if self.shape == 'circle':
            pygame.draw.circle(screen, self.color, (pos_x, pos_y), self.size)
        else:
            rect = pygame.Rect(
                pos_x - self.width//2,
                pos_y - self.height//2,
                self.width,
                self.height
            )
            pygame.draw.rect(screen, self.color, rect)



class Creature:
    def __init__(self, x, y, level, bot_id, color):
        self.x = x
        self.y = y
        self.level = level
        self.nutrition = 0
        self.hp = 100
        self.speed = 9  # 90% of player speed
        self.base_radius = 15
        self.radius = self.base_radius + level
        self.direction = random.uniform(0, 2 * math.pi)
        self.direction_timer = 0
        self.direction_change_interval = 60
        self.bot_id = bot_id
        self.color = color
        self.target_food = None

        

    def find_nearest_food(self, foods):
        current_max_nutrition = calculate_required_nutrition(self.level) / 1.5
        valid_foods = [f for f in foods if f.nutrition <= current_max_nutrition]
        
        if not valid_foods:
            return None
            
        nearest_food = min(valid_foods, 
                          key=lambda f: math.sqrt((f.x - self.x)**2 + (f.y - self.y)**2))
        
        # Only target food within a reasonable range
        distance = math.sqrt((nearest_food.x - self.x)**2 + (nearest_food.y - self.y)**2)
        if distance < 300:  # Visible range
            return nearest_food
        return None


    def find_nearest_target(self, foods, creatures, player):
        current_max_nutrition = calculate_required_nutrition(self.level) / 1.5
        
        # First, look for smaller creatures (including player)
        potential_prey = []
        if player.level < self.level:
            potential_prey.append(player)
        for creature in creatures:
            if creature != self and creature.level < self.level:
                potential_prey.append(creature)
        
        if potential_prey:
            nearest_prey = min(potential_prey, 
                              key=lambda p: math.sqrt((p.x - self.x)**2 + (p.y - self.y)**2))
            distance = math.sqrt((nearest_prey.x - self.x)**2 + (nearest_prey.y - self.y)**2)
            if distance < 300:  # Detection range
                return nearest_prey, True  # True indicates it's a creature
        
        # If no prey found, look for food
        valid_foods = [f for f in foods if f.nutrition <= current_max_nutrition]
        if valid_foods:
            nearest_food = min(valid_foods, 
                              key=lambda f: math.sqrt((f.x - self.x)**2 + (f.y - self.y)**2))
            return nearest_food, False  # False indicates it's food
        
        return None, False


    def should_flee(self, threat, distance_threshold=200):
        if threat.level > self.level:
            distance = math.sqrt((threat.x - self.x)**2 + (threat.y - self.y)**2)
            return distance < distance_threshold
        return False


    def move_random(self, map_size, obstacles):
        self.direction_timer += 1
        if self.direction_timer >= self.direction_change_interval:
            self.direction = random.uniform(0, 2 * math.pi)
            self.direction_timer = 0
        
        new_x = self.x + math.cos(self.direction) * self.speed
        new_y = self.y + math.sin(self.direction) * self.speed
        
        # Check collision with obstacles
        can_move = True
        for obstacle in obstacles:
            if check_collision(new_x, new_y, self.radius, obstacle.x, obstacle.y, obstacle.size):
                can_move = False
                self.direction = random.uniform(0, 2 * math.pi)
                break
        
        if can_move:
            self.x = new_x
            self.y = new_y
            
        self.x = max(self.radius, min(map_size[0] - self.radius, self.x))
        self.y = max(self.radius, min(map_size[1] - self.radius, self.y))



    def move_towards_food(self, map_size, obstacles, foods, creatures, player):
        # Check for threats first
        threats = [c for c in creatures if c.level > self.level]
        if player.level > self.level:
            threats.append(player)
        
        # Calculate movement vector
        target_x, target_y = None, None
        
        # Flee from nearest threat if necessary
        for threat in threats:
            if self.should_flee(threat):
                dx = self.x - threat.x
                dy = self.y - threat.y
                dist = math.sqrt(dx*dx + dy*dy)
                if dist > 0:
                    target_x = self.x + (dx/dist) * self.speed
                    target_y = self.y + (dy/dist) * self.speed
                    break
        
        # If not fleeing, move towards target
        if target_x is None:
            target, is_creature = self.find_nearest_target(foods, creatures, player)
            if target:
                dx = target.x - self.x
                dy = target.y - self.y
                dist = math.sqrt(dx*dx + dy*dy)
                if dist > 0:
                    target_x = self.x + (dx/dist) * self.speed
                    target_y = self.y + (dy/dist) * self.speed
            else:
                # Random movement if no target
                angle = random.uniform(0, 2 * math.pi)
                target_x = self.x + math.cos(angle) * self.speed
                target_y = self.y + math.sin(angle) * self.speed
        
        if target_x is not None and target_y is not None:
            # Use exactly the same movement and collision handling as player
            new_x, new_y = move_with_sliding(self, target_x, target_y, obstacles)
            
            # Apply border constraints
            self.x = max(self.radius, min(map_size[0] - self.radius, new_x))
            self.y = max(self.radius, min(map_size[1] - self.radius, new_y))

        

    def draw(self, screen, camera_offset):
        pos_x = int(self.x - camera_offset[0])
        pos_y = int(self.y - camera_offset[1])
        pygame.draw.circle(screen, self.color, (pos_x, pos_y), self.radius)
        
        font = pygame.font.Font(None, 24)
        level_text = font.render(str(self.level), True, (255, 255, 255))
        text_rect = level_text.get_rect(center=(pos_x, pos_y))
        screen.blit(level_text, text_rect)



def calculate_required_nutrition(current_level):
    if current_level == 1:
        return 20
    return int(calculate_required_nutrition(current_level - 1) * 1.5)


def slide_along_obstacle(x, y, new_x, new_y, obstacle):
    if obstacle.shape == 'circle':
        # Vector from obstacle center to new position
        dx = new_x - obstacle.x
        dy = new_y - obstacle.y
        # Normalize vector
        length = math.sqrt(dx*dx + dy*dy)
        if length == 0:
            return x, y
        dx /= length
        dy /= length
        # Position on obstacle surface
        return (obstacle.x + dx * (obstacle.size + 20), 
                obstacle.y + dy * (obstacle.size + 20))
    else:  # rectangle
        # Implement rectangle sliding here
        # This is a simplified version
        if abs(new_x - obstacle.x) > abs(new_y - obstacle.y):
            return x, new_y
        else:
            return new_x, y



def check_collision(x1, y1, r1, x2, y2, r2, shape='circle'):
    if shape == 'circle':
        distance = math.sqrt((x2 - x1)**2 + (y2 - y1)**2)
        return distance < (r1 + r2)
    else:  # rectangle
        # Simple rectangular boundary check
        rect_left = x2 - r2
        rect_right = x2 + r2
        rect_top = y2 - r2
        rect_bottom = y2 + r2
        
        return (x1 + r1 > rect_left and
                x1 - r1 < rect_right and
                y1 + r1 > rect_top and
                y1 - r1 < rect_bottom)



def get_slide_vector(x1, y1, x2, y2, obstacle):
    """Calculate sliding vector along obstacle"""
    if obstacle.shape == 'circle':
        # Vector from obstacle center to entity
        dx = x1 - obstacle.x
        dy = y1 - obstacle.y
        # Normalize vector
        dist = math.sqrt(dx*dx + dy*dy)
        if dist == 0:
            return 0, 0
        dx /= dist
        dy /= dist
        
        # Project movement vector onto tangent
        move_dx = x2 - x1
        move_dy = y2 - y1
        dot_product = dx*move_dx + dy*move_dy
        
        # Calculate tangent vector
        tx = move_dx - dot_product * dx
        ty = move_dy - dot_product * dy
        
        # Normalize tangent vector
        t_len = math.sqrt(tx*tx + ty*ty)
        if t_len > 0:
            tx /= t_len
            ty /= t_len
            
        return tx, ty
    else:  # rectangle
        # Determine which edge we're closest to
        dx = x2 - x1
        dy = y2 - y1
        
        if abs(x1 - obstacle.x) > abs(y1 - obstacle.y):
            return math.copysign(1, dx), 0  # Slide horizontally
        else:
            return 0, math.copysign(1, dy)  # Slide vertically


def move_with_sliding(entity, new_x, new_y, obstacles):
    """Updated movement handling with proper rectangle collision"""
    final_x, final_y = new_x, new_y
    
    for obstacle in obstacles:
        if check_collision(new_x, new_y, entity.radius, 
                         obstacle.x, obstacle.y, obstacle.size, 
                         obstacle.shape):
            if obstacle.shape == 'circle':
                # Use existing circular obstacle sliding
                slide_x, slide_y = get_slide_vector(
                    entity.x, entity.y, new_x, new_y, obstacle
                )
                
                speed = math.sqrt((new_x - entity.x)**2 + (new_y - entity.y)**2)
                slide_amount = speed * 0.8
                final_x = entity.x + slide_x * slide_amount
                final_y = entity.y + slide_y * slide_amount
                
                if check_collision(final_x, final_y, entity.radius,
                                 obstacle.x, obstacle.y, obstacle.size,
                                 'circle'):
                    return entity.x, entity.y
            else:
                # Use border-style sliding for rectangles
                final_x, final_y = handle_rectangle_collision(
                    entity, new_x, new_y, obstacle
                )
            
            break
    
    return final_x, final_y



def handle_rectangle_collision(entity, new_x, new_y, obstacle):
    """Hybrid handling: smooth sliding for east/west, simple blocking for north/south"""
    final_x = new_x
    final_y = new_y
    
    # Rectangle boundaries
    rect_left = obstacle.x - obstacle.width/2
    rect_right = obstacle.x + obstacle.width/2
    rect_top = obstacle.y - obstacle.height/2
    rect_bottom = obstacle.y + obstacle.height/2
    
    # First handle east/west edges with smooth sliding
    if new_y + entity.radius > rect_top and new_y - entity.radius < rect_bottom:
        if entity.x < rect_left:
            final_x = rect_left - entity.radius
        elif entity.x > rect_right:
            final_x = rect_right + entity.radius
    
    # Then handle north/south edges with simple blocking
    if final_x + entity.radius > rect_left and final_x - entity.radius < rect_right:
        if new_y + entity.radius > rect_top and new_y - entity.radius < rect_bottom:
            final_y = entity.y  # Just stay at current y position
            
    return final_x, final_y



def handle_collisions(game):
    # Bot-Food collisions
    for creature in game.creatures:
        for food in game.foods[:]:
            if check_collision(creature.x, creature.y, creature.radius, 
                             food.x, food.y, food.size):
                current_max_nutrition = calculate_required_nutrition(creature.level) / 1.5
                if food.nutrition <= current_max_nutrition:
                    creature.nutrition += food.nutrition
                    creature.hp = min(100, creature.hp + food.nutrition * 2)
                    game.foods.remove(food)
                    creature.target_food = None  # Reset target after eating
                    
                    # Check for level up
                    required_nutrition = calculate_required_nutrition(creature.level)
                    if creature.nutrition >= required_nutrition:
                        creature.level += 1
                        creature.nutrition = 0
                        creature.radius = creature.base_radius + creature.level

    # Player-Food collisions
    for food in game.foods[:]:
        if check_collision(game.player.x, game.player.y, game.player.radius, 
                         food.x, food.y, food.size):
            current_max_nutrition = calculate_required_nutrition(game.player.level) / 1.5
            if food.nutrition <= current_max_nutrition:
                game.player.nutrition += food.nutrition
                game.player.hp = min(100, game.player.hp + food.nutrition * 2)
                game.foods.remove(food)
                game.food_eaten_count += 1
                
                # Check for player level up
                required_nutrition = calculate_required_nutrition(game.player.level)
                if game.player.nutrition >= required_nutrition:
                    game.player.level += 1
                    game.player.nutrition = 0
                    game.player.radius = game.player.base_radius + game.player.level
                
    # Player-Creature collisions
    for creature in game.creatures[:]:
        if check_collision(game.player.x, game.player.y, game.player.radius,
                         creature.x, creature.y, creature.radius):
            if game.player.level > creature.level:
                creature.hp -= 20
                if creature.hp <= 0:
                    game.player.nutrition += calculate_required_nutrition(creature.level)
                    game.creatures.remove(creature)
            elif game.player.level < creature.level:
                game.player.hp -= 20
                if game.player.hp <= 0:
                    game.show_game_over_screen(creature.level)
                    return True
                
    # Creature-Creature collisions
    for i, creature1 in enumerate(game.creatures):
        for creature2 in game.creatures[i+1:]:
            if check_collision(creature1.x, creature1.y, creature1.radius,
                             creature2.x, creature2.y, creature2.radius):
                if creature1.level > creature2.level:
                    creature2.hp -= 20
                    if creature2.hp <= 0:
                        creature1.nutrition += calculate_required_nutrition(creature2.level)
                        game.creatures.remove(creature2)
                elif creature1.level < creature2.level:
                    creature1.hp -= 20
                    if creature1.hp <= 0:
                        creature2.nutrition += calculate_required_nutrition(creature1.level)
                        game.creatures.remove(creature1)
                        break
    
    return False



if __name__ == "__main__":
    game = Game()
    game.run()


