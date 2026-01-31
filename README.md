# Smart Irrigation and Autonomous Drainage System Report (DQN)

## Project Summary

This project aims to develop an autonomous artificial intelligence agent that performs both irrigation management and drainage (evacuation) management in case of excessive rainfall on a 10x10 agricultural field. Unlike traditional Q-Table methods, the Deep Q-Network (DQN) algorithm is used in this system to manage the high-dimensional state space.

## 1. Environment

The simulation takes place on a 10x10 grid consisting of 100 cells. Each cell has its own moisture value (between 0-100).

Weather Dynamics: There are 3 stochastically changing weather conditions in the environment:

Normal: Standard evaporation.

Hot: High evaporation (Drought risk).

Rainy: Water is added to the soil (Flood risk).

Drainage Point: The bottom-right corner of the grid (9, 9) is designated as the drainage channel. This point is of critical importance when a flood risk occurs.

## 2. State / Observation Space

The "Bucket" and "Discrete" structure in the old system has been abandoned, and replaced by a Continuous vector structure that feeds the neural network. The agent can perceive not only the cell it is in but the entire field and environmental factors.

State Vector Size: 107
Content:

Agent Position (2 Values): Normalized Row and Column information.

Soil Moisture Map (100 Values): Moisture values of all cells in the 10x10 field (flattened & normalized).

Weather (3 Values): One-Hot Encoding (Normal, Hot, Rainy).

Target Direction / GPS (2 Values): The agent's relative position to the nearest dry cell (Delta X, Delta Y). This feature gives the agent a sense of direction like a "compass".

## 3. Action Space

The agent can perform a total of 7 different actions:

Movements (0-3): North, South, East, West.

Irrigation (4-5):

WATER_LOW: Adds +25 units of water to the cell.

WATER_HIGH: Adds +50 units of water to the cell.

Wait / Energy Saving (6 - STAY):

The agent waits in place.

Critical Function (Drainage): If the weather is Rainy, there is a Flood Risk, and the agent is at the Drainage Point (9,9); this action Activates Drainage and evacuates excess water from the field.

Normal Function: Provides energy saving if there is no work to be done in the field.

## 4. Reward System (Reward Shaping)

A multi-layered reward function has been designed for the agent to learn complex tasks.

Positive Rewards (Incentives)

Irrigation Success: Irrigating a dry (Moisture < 40) cell yields +5.0 reward. Saving a cell at a critical level (Moisture < 20) provides an extra +2.0 bonus.

Drainage (Crisis) Management: Keeping the drainage channel (9,9) active (STAY) when there is a flood risk (more than 50% excessively wet area) and it is raining yields +5.0 reward.

Navigation: Positive feedback is given for every step taken closer to the nearest dry cell (Distance Shaping).

Energy Saving: Staying in STAY mode when there is no dry region in the field yields +1.0 reward.

Negative Rewards (Penalties)

Flood Penalty: A penalty is applied for every excessively wet (>80) cell in the field per step (-0.05).

Drought Penalty: A penalty is applied for every plant below the critical level per step (-0.01).

Incorrect Action: Irrigating wet soil (Overwatering) or staying idle when there is work (Laziness) is penalized.

Game Loss: If more than 40% of the plants die, a -50 penalty is given and the episode is terminated.

## 5. Model Architecture (DQN)

The agent's decision-making mechanism is provided by a Deep Q-Network.

Input Layer: 107 Neurons (State size).

Hidden Layers: 2 Fully Connected layers. Each has 128 neurons and ReLU activation.

Output Layer: 7 Neurons (Q-value of each action).

Learning Technique:

Replay Buffer: Past experiences (State, Action, Reward, Next State) are kept in memory and randomly sampled for training.

Target Network: Target values are calculated over a separate network for training stability.

## 6. Code Structure and Operation

irrigation_environment.py (New Environment)

Contains the physical rules of the simulation.

step(): Takes the agent's action, applies rain/evaporation/drainage logic, and returns the new state and reward.

reset(): Randomly initializes the field and weather.

render(): Visualizes the environment. (Red: Agent, Black Box: Drainage Point).

dqn.py (Model)

Contains the neural network architecture (DQN class) and the agent's learning logic (Agent class).

select_action(): Makes an exploration (random) or exploitation (model prediction) decision using the Epsilon-Greedy strategy. The epsilon value is dynamically reduced throughout the training.

optimize_model(): Trains the neural network by pulling a random batch of data from memory (Backpropagation).

dqn_train.py (Training Loop)

The main file managing the training.

Tracks rewards throughout the training.

Saves animation (.gif) and graph (.png) at specific intervals.

Saves the model as a .pth file at the end of training and performs a validation test.

## 7. Results

Training graphs show that the agent initially moves randomly (-1500 scores), but over time learns both to irrigate and to flee to the drainage point when it rains, reaching positive scores (+500 and above). The agent has successfully automated the strategy of "work when needed, rest when not needed, evacuate in crisis".



![validation_run.gif](./validation_run.gif)
