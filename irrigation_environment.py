import numpy as np
import gymnasium as gym
from gymnasium import spaces
import time

MOVE_SOUTH = 0
MOVE_NORTH = 1
MOVE_EAST = 2
MOVE_WEST = 3
WATER_LOW = 4
WATER_HIGH = 5
AERATE = 6 # Removing the excess water

BUCKET_DRY = 0 # < 40
BUCKET_IDEAL = 1 # 40-70
BUCKET_WET = 2 # > 70

PANIC_CALM = 0      # Few bad plants
PANIC_WORRIED = 1   # Some bad plants
PANIC_CRITICAL = 2  # Many bad plants

class IrrigationEnv(gym.Env):
    metadata = {"render_modes": ["rgb_array", "human"], "render_fps": 4}

    def __init__(self, render_mode=None):
        self.render_mode = render_mode
        self.num_rows = 4
        self.num_cols = 4
        self.cell_size = 64
        # Each episode is considered one day. When Max step is reached the episode ends, meaning the day ends
        # Another done condition is  "reaching ideal moisture" for all cells and this will be the SUCCESS result
        # Last done condition is "low or high moisture level in 80% of cells" and this will be the FAILED result
        self.max_steps = 600
        self.current_step = 0
        #STATE:
        # Agent-> Row: (0-5) Col: (0-5)
        # Moisture of current cell (0-2) -> 3 values
        # Global Panic (0-2) -> 3 values 
        # State = 4x4x3x3
        self.observation_space = spaces.Discrete(4*4*3*3)
        self.action_space = spaces.Discrete(7)
        # This grid simulates each cells's moisture level for each plant on the grid.
        # In order to not to grew the state exponentially, the agent does not see this. 
        # It is only aware of the cell it is currently on, hence the low state and small q table
        self.moisture_grid = np.zeros((self.num_rows, self.num_cols), dtype=np.float32)
        self.agent_pos = (0,0)
        self.consecutive_stays = 0
        self.prev_agent_pos = None


    
    def get_panic_level(self):
        bad_plants = np.sum((self.moisture_grid < 30) | (self.moisture_grid > 80))
        
        if bad_plants < 3:
            return PANIC_CALM
        elif bad_plants < 10:
            return PANIC_WORRIED
        else:
            return PANIC_CRITICAL

    def encode(self, row, col, panic_level, moisture_val):
        if moisture_val < 40:
            bucket = BUCKET_DRY
        elif moisture_val <= 70:
            bucket = BUCKET_IDEAL
        else: 
            bucket = BUCKET_WET
            
        i = row
        i *= 4 
        i += col
        i *= 3
        i += panic_level
        i *= 3
        i += bucket
        return int(i)
    
    def decode(self, i):
        out = []
        out.append(i % 3) # Bucket
        i = i // 3
        out.append(i % 3) # Panic Level
        i = i // 3
        out.append(i % 4) # Col
        i = i // 4
        out.append(i)     # Row
        return list(reversed(out))
    
    def _get_action_mask(self):
        mask = np.ones(7, dtype=np.int8)
        r, c = self.agent_pos

        if self.consecutive_stays >= 2:
            # 1. Disable stationary actions
            mask[WATER_LOW] = 0
            mask[WATER_HIGH] = 0
            mask[AERATE] = 0
            
            # 2. Disable moves that hit walls (keeping agent in same cell)
            # r, c = self.agent_pos
            # if r == self.num_rows - 1: mask[MOVE_SOUTH] = 0
            # if r == 0: mask[MOVE_NORTH] = 0
            # if c == self.num_cols - 1: mask[MOVE_EAST] = 0
            # if c == 0: mask[MOVE_WEST] = 0
        
        if self.consecutive_stays >=3:
            if self.prev_agent_pos is not None:
            # If a move action would take us exactly back to prev_agent_pos, block it.
                if r < self.num_rows - 1 and (r + 1, c) == self.prev_agent_pos: mask[MOVE_SOUTH] = 0
                if r > 0 and (r - 1, c) == self.prev_agent_pos: mask[MOVE_NORTH] = 0
                if c < self.num_cols - 1 and (r, c + 1) == self.prev_agent_pos: mask[MOVE_EAST] = 0
                if c > 0 and (r, c - 1) == self.prev_agent_pos: mask[MOVE_WEST] = 0
            
        return mask
  
    def step(self, action):
        self.current_step += 1
        old_row, old_col = self.agent_pos
        row, col = self.agent_pos
        current_moisture = self.moisture_grid[row, col]
        reward = -0.1
        
        if action in [MOVE_SOUTH, MOVE_NORTH, MOVE_EAST, MOVE_WEST]:
            new_row, new_col = row, col
            if action == MOVE_SOUTH:
                new_row = min(row + 1, self.num_rows -1)
            elif action == MOVE_NORTH:
                new_row = max(row -1, 0)
            elif action == MOVE_EAST:
                new_col = min(col + 1, self.num_cols -1)
            elif action == MOVE_WEST:
                new_col = max(col -1, 0)

            if (new_row, new_col) != (row, col):    
                self.prev_agent_pos = (row, col)
        
                if current_moisture < 40:
                    reward -= 5
                elif current_moisture > 70:
                    reward -= 5
      
                target_moisture = self.moisture_grid[new_row, new_col]
                if 40 <= target_moisture <= 70:
                    reward -= 5
                else:
                    reward += 1
                    
                row, col = new_row, new_col
            else:
                reward -= 0.1

        elif action in [WATER_LOW, WATER_HIGH]:  
            if action == WATER_LOW:
                self.moisture_grid[row, col] += 25 
                if current_moisture > 45:
                    reward -= 5
                else:
                    reward += 5
            elif action == WATER_HIGH:
                self.moisture_grid[row, col] += 50 
                if current_moisture > 20:
                    reward -= 5
                else:
                    reward += 5                
        
        elif action == AERATE:
            if current_moisture < 70:
                reward -= 5
            else:
                reward += 5
            self.moisture_grid[row, col] -= 30

        self.agent_pos = (row, col)

        if self.agent_pos == (old_row, old_col):
            self.consecutive_stays += 1
        else:
            self.consecutive_stays = 0 # Reset if moved

        self.moisture_grid = np.clip(self.moisture_grid, 0, 100)

        total_plants = self.num_rows * self.num_cols
        dead_dry = (self.moisture_grid < 30)
        ideal = (self.moisture_grid >= 40) & (self.moisture_grid <= 70)
        dead_wet = (self.moisture_grid > 80)
        
        n_dead = np.sum(dead_dry) + np.sum(dead_wet)
        n_ideal = np.sum(ideal)
        
        terminated = False
        if n_dead / total_plants > 0.8:
            terminated = True
            reward -= 500 
        elif n_ideal / total_plants >= 1:
            terminated = True
            reward += 1000 
        if self.current_step >= self.max_steps:
            terminated = True
     
        current_plant_moisture = self.moisture_grid[row, col]
        current_panic = self.get_panic_level()
        obs = self.encode(row, col, current_panic, current_plant_moisture)
        info = {
            "good_plants": n_ideal,
            "dead_plants": n_dead,
            "panic_level": current_panic,
            "action_mask": self._get_action_mask()

        }
        return int(obs), reward, terminated, False, info

 
    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self.moisture_grid = self.np_random.uniform(low=10, high=95, size=(self.num_rows, self.num_cols))
        self.agent_pos = (self.np_random.integers(0, 4), self.np_random.integers(0, 4))
        self.weather = self.np_random.integers(0, 3)
        self.current_step = 0        
        self.consecutive_stays = 0
        self.prev_agent_pos = None
        r, c = self.agent_pos
        panic = self.get_panic_level()
        obs = self.encode(r, c, panic, self.moisture_grid[r, c])        
        return int(obs), {"action_mask": self._get_action_mask()}
   
    def render(self):
        grid_img = np.zeros((self.num_rows * self.cell_size, self.num_cols * self.cell_size, 3), dtype=np.uint8)
        
        for r in range(self.num_rows):
            for c in range(self.num_cols):
                y_start = r * self.cell_size
                y_end = (r + 1) * self.cell_size
                x_start = c * self.cell_size
                x_end = (c + 1) * self.cell_size
                
                m = self.moisture_grid[r, c]
                
                if m < 30:
                    color = [139, 69, 19]
                elif m < 40:
                    color = [255, 215, 0]
                elif m <= 70:
                    color = [50, 205, 50]
                elif m <= 80:
                    color = [0, 255, 255]
                else:
                    color = [0, 0, 255]
                
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