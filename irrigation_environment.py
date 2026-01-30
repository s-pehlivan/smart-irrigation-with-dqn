import numpy as np
import gymnasium as gym
from gymnasium import spaces
from collections import deque

# Sabitler
MOVE_SOUTH = 0
MOVE_NORTH = 1
MOVE_EAST = 2
MOVE_WEST = 3
WATER_LOW = 4
WATER_HIGH = 5

# Hava Durumu Sabitleri
WEATHER_NORMAL = 0
WEATHER_HOT = 1
WEATHER_RAINY = 2

class IrrigationEnv(gym.Env):
    metadata = {"render_modes": ["rgb_array", "human"], "render_fps": 4}

    def __init__(self, render_mode=None):
        self.render_mode = render_mode
        self.num_rows = 10
        self.num_cols = 10
        self.cell_size = 64
        self.max_steps = 1000 
        self.current_step = 0
        
        # 10x10 Grid (100) + 2 Konum + 3 Hava Durumu + 2 HEDEF YÖNÜ = 107
        obs_dim = 2 + (self.num_rows * self.num_cols) + 3 + 2
        self.observation_space = spaces.Box(low=-1, high=1, shape=(obs_dim,), dtype=np.float32)

        self.action_space = spaces.Discrete(6)
        
        self.moisture_grid = np.zeros((self.num_rows, self.num_cols), dtype=np.float32)
        self.agent_pos = (0,0)
        self.consecutive_stays = 0
        self.current_weather = WEATHER_NORMAL
        
        # --- YENİ ÖZELLİK: Ziyaret Geçmişi (Loop Önleme) ---
        # Son 10 konumu tutarak kısa döngüleri tespit edeceğiz
        self.recent_positions = deque(maxlen=10)

    def _get_nearest_dry_coords(self):
        dry_indices = np.argwhere(self.moisture_grid < 40)
        if len(dry_indices) == 0:
            return None
        
        agent_arr = np.array(self.agent_pos)
        distances = np.sum(np.abs(dry_indices - agent_arr), axis=1)
        nearest_idx = np.argmin(distances)
        return dry_indices[nearest_idx]

    def get_observation(self):
        norm_row = self.agent_pos[0] / (self.num_rows - 1)
        norm_col = self.agent_pos[1] / (self.num_cols - 1)
        norm_grid = self.moisture_grid.flatten() / 100.0
        
        weather_vec = np.zeros(3, dtype=np.float32)
        weather_vec[self.current_weather] = 1.0

        target_coords = self._get_nearest_dry_coords()
        if target_coords is None:
            delta_row, delta_col = 0.0, 0.0
        else:
            delta_row = (target_coords[0] - self.agent_pos[0]) / self.num_rows
            delta_col = (target_coords[1] - self.agent_pos[1]) / self.num_cols
        
        obs = np.concatenate(([norm_row, norm_col], norm_grid, weather_vec, [delta_row, delta_col])).astype(np.float32)
        return obs
    
    def _get_action_mask(self):
        mask = np.ones(6, dtype=np.int8)
        r, c = self.agent_pos

        if self.consecutive_stays >= 1: 
            mask[WATER_LOW] = 0
            mask[WATER_HIGH] = 0
        
        if r == 0: mask[MOVE_NORTH] = 0
        if r == self.num_rows - 1: mask[MOVE_SOUTH] = 0
        if c == 0: mask[MOVE_WEST] = 0
        if c == self.num_cols - 1: mask[MOVE_EAST] = 0
            
        return mask

    def _get_distance_to_nearest_dry(self, pos):
        dry_indices = np.argwhere(self.moisture_grid < 40)
        if len(dry_indices) == 0:
            return 0
        agent_arr = np.array(pos)
        distances = np.sum(np.abs(dry_indices - agent_arr), axis=1)
        return np.min(distances)
  
    def step(self, action):
        self.current_step += 1
        
        # --- DOĞAL DİNAMİKLER ---
        if np.random.random() < 0.02:
            self.current_weather = np.random.choice([WEATHER_NORMAL, WEATHER_HOT, WEATHER_RAINY])

        if self.current_weather == WEATHER_HOT:
            evaporation = np.random.uniform(0.2, 0.5, size=(self.num_rows, self.num_cols))
            self.moisture_grid -= evaporation
        elif self.current_weather == WEATHER_RAINY:
            rain = np.random.uniform(0.1, 0.3, size=(self.num_rows, self.num_cols))
            self.moisture_grid += rain
        else:
            evaporation = np.random.uniform(0.05, 0.15, size=(self.num_rows, self.num_cols))
            self.moisture_grid -= evaporation

        # --- DURUM ANALİZİ ---
        prev_dist = self._get_distance_to_nearest_dry(self.agent_pos)

        # --- AKSİYON ---
        reward = -0.01 
        
        row, col = self.agent_pos
        new_row, new_col = row, col
        moved = False

        if action in [MOVE_SOUTH, MOVE_NORTH, MOVE_EAST, MOVE_WEST]:
            if action == MOVE_SOUTH: new_row = min(row + 1, self.num_rows -1)
            elif action == MOVE_NORTH: new_row = max(row -1, 0)
            elif action == MOVE_EAST: new_col = min(col + 1, self.num_cols -1)
            elif action == MOVE_WEST: new_col = max(col -1, 0)

            if (new_row, new_col) != (row, col):    
                row, col = new_row, new_col
                moved = True
            else:
                reward -= 0.5 # Duvara çarpma

        elif action in [WATER_LOW, WATER_HIGH]:
            current_moisture = self.moisture_grid[row, col]
            water_amount = 25 if action == WATER_LOW else 50
            
            self.moisture_grid[row, col] += water_amount
            
            if current_moisture < 40:
                reward += 5.0 
                if current_moisture < 20: 
                    reward += 2.0 
            elif current_moisture > 70:
                reward -= 1.0 
            else:
                reward -= 0.2

        self.agent_pos = (row, col)

        # --- YENİ: LOOP CEZASI VE TAKİP ---
        # Eğer ajan yeni bir yere gittiyse geçmişe bak
        if moved:
            # Eğer gittiği yer son 10 adımda varsa, tekrar etme cezası ver
            # (Ne kadar yakın zamanda gittiyse o kadar büyük ceza)
            if (row, col) in self.recent_positions:
                # index 0 en eski, -1 en yeni.
                # count metodu ile kaç kere gittiğini bulabiliriz
                visit_count = self.recent_positions.count((row, col))
                reward -= (visit_count * 0.5) # Tekrar etme cezası
            
            self.recent_positions.append((row, col))

        # --- YENİ: ISLAK/KURU HÜCREDE BULUNMA ÖDÜL/CEZASI ---
        current_cell_moisture = self.moisture_grid[row, col]
        
        if current_cell_moisture > 70: # Mavi (Islak) Hücre
            # Ajan burayı terk etmeli, burada durdukça ceza yesin
            reward -= 0.2
        elif current_cell_moisture < 40: # Kahverengi (Kuru) Hücre
            # Ajan buraya geldiği için (sulamasa bile) küçük bir "doğru yerdesin" ödülü
            reward += 0.2

        if self.agent_pos == (new_row, new_col) and not moved:
            self.consecutive_stays += 1
        else:
            self.consecutive_stays = 0 

        self.moisture_grid = np.clip(self.moisture_grid, 0, 100)

        # --- NAVİGASYON ÖDÜLÜ ---
        if moved:
            curr_dist = self._get_distance_to_nearest_dry(self.agent_pos)
            diff = prev_dist - curr_dist
            reward += diff * 1.0 

        # --- KRİTİK CEZA ---
        critical_count = np.sum(self.moisture_grid < 30)
        reward -= (critical_count * 0.01) 

        # --- BİTİŞ KONTROLLERİ ---
        total_plants = self.num_rows * self.num_cols
        dead_plants = np.sum((self.moisture_grid < 5) | (self.moisture_grid > 98))
        
        terminated = False
        
        if dead_plants > (total_plants * 0.4): 
            reward -= 50
            terminated = True
        
        if self.current_step >= self.max_steps:
            terminated = True
     
        obs = self.get_observation()
        
        ideal_plants = np.sum((self.moisture_grid >= 40) & (self.moisture_grid <= 70))
        success_ratio = ideal_plants / total_plants

        info = {
            "success_ratio": success_ratio,
            "action_mask": self._get_action_mask(),
            "weather": self.current_weather,
            "critical_count": critical_count
        }
        return obs, reward, terminated, False, info

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self.moisture_grid = self.np_random.uniform(low=40, high=80, size=(self.num_rows, self.num_cols))
        
        num_dry_spots = self.np_random.integers(5, 15)
        for _ in range(num_dry_spots):
            r, c = self.np_random.integers(0, self.num_rows), self.np_random.integers(0, self.num_cols)
            self.moisture_grid[r, c] = self.np_random.uniform(10, 30)

        self.agent_pos = (self.np_random.integers(0, self.num_rows), self.np_random.integers(0, self.num_cols))
        self.current_step = 0        
        self.consecutive_stays = 0
        self.current_weather = self.np_random.choice([WEATHER_NORMAL, WEATHER_HOT, WEATHER_RAINY])
        self.recent_positions.clear() # Geçmişi temizle
        
        obs = self.get_observation()        
        return obs, {"action_mask": self._get_action_mask()}
   
    def render(self):
        grid_img = np.zeros((self.num_rows * self.cell_size, self.num_cols * self.cell_size, 3), dtype=np.uint8)
        
        bg_tint = [0, 0, 0]
        if self.current_weather == WEATHER_HOT: bg_tint = [20, 0, 0]
        elif self.current_weather == WEATHER_RAINY: bg_tint = [0, 0, 20]
            
        for r in range(self.num_rows):
            for c in range(self.num_cols):
                y_start = r * self.cell_size
                y_end = (r + 1) * self.cell_size
                x_start = c * self.cell_size
                x_end = (c + 1) * self.cell_size
                
                m = self.moisture_grid[r, c]
                
                if m < 30: base_color = [139, 69, 19] 
                elif m < 40: base_color = [218, 165, 32] 
                elif m <= 70: base_color = [50, 205, 50] 
                elif m <= 80: base_color = [64, 224, 208] 
                else: base_color = [0, 0, 255] 
                
                color = np.clip(np.array(base_color) + np.array(bg_tint), 0, 255).astype(np.uint8)
                grid_img[y_start:y_end, x_start:x_end] = color 
                
                if (r, c) == self.agent_pos:
                    pad = int(self.cell_size * 0.25)
                    grid_img[y_start+pad:y_end-pad, x_start+pad:x_end-pad] = [255, 50, 50] 
        
        for r in range(self.num_rows + 1):
            y = min(r * self.cell_size, grid_img.shape[0] - 1)
            grid_img[y-1:y+1, :] = [36, 36, 36]
        for c in range(self.num_cols + 1):
            x = min(c * self.cell_size, grid_img.shape[1] - 1)
            grid_img[:, x-1:x+1] = [36, 36, 36]

        return grid_img