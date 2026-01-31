import matplotlib.pyplot as plt
import matplotlib.animation as animation
import torch
import numpy as np
# --- GÜNCELLEME 1: Yeni ortam dosyasını import et ---
from irrigation_environment import IrrigationEnv
# --- GÜNCELLEME 2: Yeni ajan dosyasını import et ---
from dqn import Agent

# Eğitim Ayarları
NUM_EPISODES = 1000 
PRINT_INTERVAL = 50
ANIMATION_LOG_INTERVAL = 250 # Her 250 bölümde bir animasyon için kayıt al

def animate_training_progression(all_grids, log_interval=1000, save_path="training_progression.gif", label="Training"):    
    all_frames = []
    episode_labels = []    
    for i, episode_frames in enumerate(all_grids):
        # Eğer validation ise log_interval 1 sayılır, eğitim ise parametre kullanılır
        episode_num = (i + 1) * log_interval 
        for frame in episode_frames:
            all_frames.append(frame)
            episode_labels.append(f"{label} Episode: {episode_num}")
            
    if len(all_frames) == 0:
        print("No frames found to animate.")
        return
        
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.axis('off')
    im = ax.imshow(all_frames[0])
    title = ax.set_title(episode_labels[0])
    
    def update(frame_idx):
        im.set_array(all_frames[frame_idx])
        title.set_text(episode_labels[frame_idx])
        return [im, title]
        
    print(f"Generating animation ({label}) with {len(all_frames)} frames...")
    ani = animation.FuncAnimation(
        fig, update, frames=len(all_frames), interval=50, blit=False
    )
    
    try:
        print(f"Saving to {save_path} (this might take a minute)...")
        ani.save(save_path, writer='pillow', fps=15)
        print(f"Success! Saved to {save_path}")
    except Exception as e:
        print(f"Error saving animation: {e}")
    finally:
        plt.close(fig)

def validate(agent, env, num_episodes=5):
    """
    Eğitilmiş ajanı test eder (Exploration kapalı).
    """
    print("\n--- Validation (Test) Başlıyor ---")
    val_grids = []
    val_rewards = []
    
    # Ajanın epsilon değerini sakla ve 0 yap (Tamamen greedy/öğrenilmiş davranış)
    original_epsilon = agent.epsilon
    agent.epsilon = 0.0
    
    for i in range(num_episodes):
        state, info = env.reset()
        action_mask = info["action_mask"]
        done = False
        total_reward = 0
        frames = []
        
        # İlk kareyi kaydet
        frames.append(env.render())
        
        while not done:
            action = agent.select_action(state, action_mask)
            next_state, reward, done, _, info = env.step(action)
            
            frames.append(env.render())
            
            state = next_state
            action_mask = info["action_mask"]
            total_reward += reward
            
        val_grids.append(frames)
        val_rewards.append(total_reward)
        print(f"Validation Episode {i+1}: Reward {total_reward:.2f}")

    # Epsilon'u eski haline getir (Gerekirse eğitim devam ederse diye)
    agent.epsilon = original_epsilon
    
    avg_val_reward = np.mean(val_rewards)
    print(f"Validation Avg Reward: {avg_val_reward:.2f}")
    return val_grids, avg_val_reward

def train():
    env = IrrigationEnv()
    
    state_dim = env.observation_space.shape[0] # Artık 18 (yeni ortamdan otomatik alınır)
    action_dim = env.action_space.n          # 7
    
    agent = Agent(state_dim, action_dim)
    
    episode_rewards = []
    training_grids = [] # Animasyon için seçilen bölümlerin kareleri
    success_count = 0
    
    print(f"Eğitim Başlıyor... Cihaz: {torch.device('cuda' if torch.cuda.is_available() else 'cpu')}")
    print(f"State Dim: {state_dim}, Action Dim: {action_dim}")

    for i_episode in range(NUM_EPISODES):
        state, info = env.reset()
        action_mask = info["action_mask"]
        
        total_reward = 0
        done = False
        
        # Animasyon için bu bölümü kaydedelim mi?
        capture_frames = (i_episode + 1) % ANIMATION_LOG_INTERVAL == 0
        current_episode_frames = []
        
        if capture_frames:
            current_episode_frames.append(env.render())
        
        while not done:
            # 1. Ajan hareket seçer
            action = agent.select_action(state, action_mask)
            
            # 2. Ortamda adım atılır
            next_state, reward, done, _, info = env.step(action)
            next_mask = info["action_mask"]
            
            # 3. Deneyim hafızaya atılır
            agent.memory.push(state, action, reward, next_state, done, next_mask)
            
            # 4. Ajan optimize edilir
            agent.optimize_model()
            
            # Durum güncelleme
            state = next_state
            action_mask = next_mask
            total_reward += reward
            
            if capture_frames:
                current_episode_frames.append(env.render())
            
        episode_rewards.append(total_reward)
        
        if capture_frames:
            training_grids.append(current_episode_frames)
        
        # --- GÜNCELLEME 3: Başarı Eşiği ---
        # Yeni ortamda maksimum ödül 100 civarı olduğu için eşiği 800'den 50'ye düşürdük.
        if total_reward > 50: 
            success_count += 1

        if (i_episode + 1) % PRINT_INTERVAL == 0:
            avg_reward = np.mean(episode_rewards[-PRINT_INTERVAL:])
            print(f"Episode: {i_episode+1}/{NUM_EPISODES} | "
                  f"Avg Reward: {avg_reward:.2f} | "
                  f"Epsilon: {agent.epsilon:.3f} | "
                  f"Success Last {PRINT_INTERVAL}: {success_count}")
            success_count = 0

    print("Eğitim Tamamlandı!")
    
    # Modeli Kaydet
    torch.save(agent.policy_net.state_dict(), "irrigation_dqn_model.pth")
    print("Model 'irrigation_dqn_model.pth' olarak kaydedildi.")
    
    # --- DOĞRULAMA (TEST) AŞAMASI ---
    # Eğitim bitti, şimdi ajanı test edelim
    val_grids, val_score = validate(agent, env, num_episodes=3)
    
    # --- GÖRSELLEŞTİRME ---
    
    # 1. Reward Grafiği
    plt.figure(figsize=(10,5))
    plt.plot(episode_rewards, label='Episode Reward')
    plt.title("Eğitim Süreci - Ödüller")
    plt.xlabel("Episode")
    plt.ylabel("Toplam Ödül")
    
    # Smoothing
    window_size = 50
    if len(episode_rewards) >= window_size:
        moving_avg = np.convolve(episode_rewards, np.ones(window_size)/window_size, mode='valid')
        plt.plot(range(window_size-1, len(episode_rewards)), moving_avg, color='red', label='50-Ep Moving Avg', linewidth=2)
    
    plt.legend()
    plt.savefig("training_plot_dqn.png")
    plt.show()
    print("Eğitim grafiği 'training_plot_dqn.png' olarak kaydedildi.")

    # 2. Eğitim Animasyonu (Gelişim Süreci)
    if len(training_grids) > 0:
        animate_training_progression(
            training_grids, 
            log_interval=ANIMATION_LOG_INTERVAL, 
            save_path="training_progress.gif",
            label="Training"
        )
        
    # 3. Test Animasyonu (Sonuç)
    if len(val_grids) > 0:
        animate_training_progression(
            val_grids, 
            log_interval=1, # Test bölümleri ardışık olduğu için 1
            save_path="validation_run.gif",
            label="Validation"
        )

if __name__ == "__main__":
    train()