import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np
import random
from collections import deque

# --- Hiperparametreler ---
BATCH_SIZE = 64
GAMMA = 0.99
EPS_START = 1.0
EPS_END = 0.05
# NOT: EPS_DECAY artık burada sabit değil, Agent sınıfında dinamik hesaplanıyor.
TAU = 0.005 
LR = 1e-3
MEMORY_SIZE = 10000

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# --- Sinir Ağı Mimarisi ---
class DQN(nn.Module):
    def __init__(self, n_observations, n_actions):
        super(DQN, self).__init__()
        self.layer1 = nn.Linear(n_observations, 128)
        self.layer2 = nn.Linear(128, 128)
        self.layer3 = nn.Linear(128, n_actions)
        self.relu = nn.ReLU()

    def forward(self, x):
        x = self.relu(self.layer1(x))
        x = self.relu(self.layer2(x))
        return self.layer3(x)

# --- Replay Buffer (Hafıza) ---
class ReplayBuffer:
    def __init__(self, capacity):
        self.memory = deque(maxlen=capacity)

    def push(self, state, action, reward, next_state, done, mask):
        self.memory.append((state, action, reward, next_state, done, mask))

    def sample(self, batch_size):
        batch = random.sample(self.memory, batch_size)
        states, actions, rewards, next_states, dones, masks = zip(*batch)
        
        return (torch.tensor(np.array(states), dtype=torch.float32).to(device),
                torch.tensor(actions, dtype=torch.int64).unsqueeze(1).to(device),
                torch.tensor(rewards, dtype=torch.float32).unsqueeze(1).to(device),
                torch.tensor(np.array(next_states), dtype=torch.float32).to(device),
                torch.tensor(dones, dtype=torch.float32).unsqueeze(1).to(device),
                torch.tensor(np.array(masks), dtype=torch.int8).to(device))

    def __len__(self):
        return len(self.memory)

# --- DQN Ajanı ---
class Agent:
    def __init__(self, state_dim, action_dim, total_episodes=2000, max_steps_per_episode=1000):
        self.state_dim = state_dim
        self.action_dim = action_dim
        
        self.policy_net = DQN(state_dim, action_dim).to(device)
        self.target_net = DQN(state_dim, action_dim).to(device)
        self.target_net.load_state_dict(self.policy_net.state_dict())
        
        self.optimizer = optim.AdamW(self.policy_net.parameters(), lr=LR, amsgrad=True)
        self.memory = ReplayBuffer(MEMORY_SIZE)
        self.steps_done = 0
        self.epsilon = EPS_START
        
        # --- DİNAMİK EPSILON DECAY HESABI ---
        # Kullanıcı bölüm sayısını artırırsa decay otomatik yavaşlar.
        # Hedef: Eğitimin %75'i bittiğinde epsilon minimuma (EPS_END) insin.
        # Geriye kalan %25'lik kısımda ajan öğrendiklerini pekiştirsin (Exploitation).
        total_training_steps = total_episodes * max_steps_per_episode
        decay_steps = total_training_steps * 0.75 # Adımların %75'i boyunca azalt
        
        # Formül: eps_end = eps_start * (decay_rate ^ steps)
        # Buradan decay_rate'i çekersek: decay_rate = (eps_end / eps_start) ^ (1 / steps)
        if decay_steps > 0:
            self.epsilon_decay = (EPS_END / EPS_START) ** (1 / decay_steps)
        else:
            self.epsilon_decay = 0.999998 # Güvenli varsayılan değer
            
        print(f"Agent initialized. Dynamic Epsilon Decay Rate: {self.epsilon_decay:.8f}")

    def select_action(self, state, action_mask=None):
        self.steps_done += 1
        # Dinamik hesaplanan decay oranını kullan
        self.epsilon = max(EPS_END, self.epsilon * self.epsilon_decay)

        if random.random() > self.epsilon:
            # --- EXPLOITATION ---
            with torch.no_grad():
                state_tensor = torch.tensor(state, dtype=torch.float32).unsqueeze(0).to(device)
                q_values = self.policy_net(state_tensor)
                
                # Maskeleme
                if action_mask is not None:
                    mask_tensor = torch.tensor(action_mask, dtype=torch.bool).to(device)
                    mask_tensor = mask_tensor.unsqueeze(0) 
                    q_values[~mask_tensor] = -1e9
                
                return q_values.max(1)[1].item()
        else:
            # --- EXPLORATION ---
            if action_mask is not None:
                valid_actions = np.where(action_mask == 1)[0]
                if len(valid_actions) > 0:
                    return np.random.choice(valid_actions)
                return 0
            else:
                return random.randrange(self.action_dim)

    def optimize_model(self):
        if len(self.memory) < BATCH_SIZE:
            return
        
        states, actions, rewards, next_states, dones, next_masks = self.memory.sample(BATCH_SIZE)

        current_q_values = self.policy_net(states).gather(1, actions)

        with torch.no_grad():
            next_q_values_raw = self.target_net(next_states)
            
            # Gelecek adımları maskele
            next_q_values_raw[next_masks == 0] = -1e9
            
            next_state_values = next_q_values_raw.max(1)[0].unsqueeze(1)
            expected_q_values = rewards + (GAMMA * next_state_values * (1 - dones))

        criterion = nn.SmoothL1Loss()
        loss = criterion(current_q_values, expected_q_values)

        self.optimizer.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_value_(self.policy_net.parameters(), 100)
        self.optimizer.step()

        # Target Update
        target_net_state_dict = self.target_net.state_dict()
        policy_net_state_dict = self.policy_net.state_dict()
        for key in policy_net_state_dict:
            target_net_state_dict[key] = policy_net_state_dict[key]*TAU + target_net_state_dict[key]*(1-TAU)
        self.target_net.load_state_dict(target_net_state_dict)