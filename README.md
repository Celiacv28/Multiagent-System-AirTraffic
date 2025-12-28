# Multi-Agent Air Traffic Control System

## Overview

This project implements a **multi-agent simulation system** for managing air traffic operations at multiple airports using reinforcement learning (RL) and discrete event simulation. The system models the coordination between aircraft agents and airport agents to optimize runway allocation and minimize operational delays.

### Key Features

- **Multi-Agent Architecture**: Independent aircraft and airport agents communicating asynchronously
- **Reinforcement Learning**: Q-learning algorithm for intelligent runway scheduling at airports
- **Discrete Event Simulation**: Time-based simulation using a central clock agent
- **Message-Driven Communication**: Agents communicate through typed messages
- **Performance Metrics**: Comprehensive tracking of delays, throughput, and operational efficiency

---

## Project Structure

```
src/
├── main.py                    # Simulation entry point and configuration
├── agents/
│   ├── aeropuerto.py         # Airport agent (baseline scheduling policy)
│   ├── aeropuerto_ar.py      # Airport agent with RL (Q-learning)
│   ├── avion.py              # Aircraft agent
│   ├── clock.py              # Global clock agent (time coordinator)
│   └── __pycache__/
├── messages/
│   ├── messages.py           # Message type definitions
│   └── __pycache__/
└── README.md
```

---

## Detailed Components

### 1. **main.py** - Simulation Configuration & Initialization

The main entry point orchestrates the entire simulation setup and execution.

#### Key Parameters:

```python
# Grid dimensions
GRID_WIDTH = 20
GRID_HEIGHT = 20

# Simulation duration
TOTAL_MINUTES = 300

# Agent counts
NUM_AIRPORTS = 4
NUM_AIRCRAFT = 6

# Runway configuration
MAX_RUNWAYS = 1
OPERATION_GAP_MINUTES = 3  # Minimum time between consecutive operations on same runway

# Aircraft characteristics
AIRCRAFT_SPEEDS = [3, 4, 2, 4, 5, 6]           # cells/minute
TAKEOFF_TIMES = [2, 2, 3, 3, 2, 4]             # minutes
LANDING_TIMES = [2, 3, 3, 4, 2, 5]             # minutes
WAIT_TIMES = [2, 3, 2, 3, 4, 1]                # minutes at airport before requesting runway

# Feature Toggle
USE_RL = False  # Switch between baseline and RL-based airport agent
```

#### Agent Registration:

The simulation creates three types of agents:

1. **Airport Agents** (4 instances)
   - Location: MAD (0,0), BCN (10,15), SEV (5,20), VLC (12,3)
   - Variable runway counts (1-3 per airport)
   - Agent type depends on `USE_RL` flag

2. **Aircraft Agents** (6 instances)
   - Defined routes between airports
   - Individual performance characteristics
   - State machine: WAITING → AWAITING_TAKEOFF_AUTH → TAKING_OFF → FLYING → AWAITING_LANDING_AUTH → LANDING

3. **Clock Agent** (1 instance)
   - Broadcasts time ticks to all agents
   - Collects and summarizes metrics at simulation end

#### Routes Definition:

```
PL001: MAD → BCN
PL002: BCN → MAD
PL003: SEV → BCN
PL004: VLC → MAD
PL005: SEV → MAD
PL006: VLC → SEV
```

---

### 2. **agents/clock.py** - Time Coordinator

Manages simulation time progression and metrics aggregation.

#### Responsibilities:

- **Time Broadcasting**: Sends `Message_Tick` at each discrete time step (one per minute)
- **Metrics Collection**: Receives `MetricsReport` messages from all agents
- **Simulation Lifecycle**: Initiates simulation with "start" message and broadcasts `Message_End` when complete

#### Core Methods:

```python
async def start(self, message: Message_Request, ctx: MessageContext)
    # Iterates through TOTAL_MINUTES
    # Publishes Message_Tick to all subscribers
    # Adds 1-second delay between ticks for observable output
    # Broadcasts Message_End at completion
```

#### Metrics Output:

At simulation end, the clock agent aggregates:
- Takeoffs and landings per airport
- Runway utilization
- Aircraft delays (takeoff and landing)
- Average queue lengths

---

### 3. **agents/avion.py** - Aircraft Agent

Simulates individual aircraft behavior and flight operations.

#### State Machine:

```
WAITING
  ↓
AWAITING_TAKEOFF_AUTH  → (TAKEOFF_REQUEST sent to origin airport)
  ↓
TAKING_OFF  → (runway operation)
  ↓
FLYING  → (in-flight state)
  ↓
AWAITING_LANDING_AUTH  → (LANDING_REQUEST sent to destination airport)
  ↓
LANDING  → (runway operation)
  ↓
COMPLETED
```

#### Key Attributes:

```python
# Configuration
aircraft_id: str
airport_origin: str              # Starting airport
airport_destination: str          # Destination airport
wait_time: int                   # Minutes to wait before requesting takeoff
takeoff_time: int                # Duration of takeoff operation (minutes)
landing_time: int                # Duration of landing operation (minutes)
speed: int                       # Flight speed (cells/minute)

# State Tracking
state: str                       # Current state in the FSM
assigned_runway: int             # Assigned runway (if authorized)
operation_start_time: int        # When current operation began
flight_start_time: int           # When flight phase started

# Metrics
flight_count: int                # Number of completed flights
takeoff_delays: List[int]        # Delays for each takeoff request
landing_delays: List[int]        # Delays for each landing request
```

#### Core Methods:

```python
async def setup()
    # Sends AircraftInfo to both origin and destination airports
    # Registers itself with the system

async def step(current_time: int)
    # Implements state transitions based on elapsed time
    # Sends requests and handles responses from airports
    # Tracks timing and delay metrics
```

#### Message Types Used:

- **Sends**: `Message_Request`, `Message_Finish`
- **Receives**: `Message_Respond` (authorization decision), `Message_Tick` (time updates)

---

### 4. **agents/aeropuerto.py** - Baseline Airport Agent

Implements a basic airport management policy without learning.

#### Responsibilities:

- **Runway Management**: Tracks runway status (FREE/OCCUPIED)
- **Queue Management**: Maintains FIFO queue of waiting aircraft
- **Authorization Logic**: Grants runway access based on availability and gap constraints
- **Operation Tracking**: Monitors takeoffs and landings

#### Key Methods:

```python
def _get_available_runway(current_time)
    # Finds first FREE runway that respects OPERATION_GAP_MINUTES
    # Returns runway dict or None if all occupied

async def handle_request(message: Message_Request, ctx: MessageContext)
    # Processes takeoff/landing requests from aircraft
    # Either authorizes immediately or queues the request

async def handle_finish(message: Message_Finish, ctx: MessageContext)
    # Frees up runway when aircraft completes operation
    # Updates runway status and timing metadata
```

#### Data Structure:

```python
self.runways = [
    {
        "runway_id": 0,
        "status": "FREE" | "OCCUPIED",
        "current_aircraft": str | None,
        "last_operation_time": int
    },
    ...
]

self.queue = [
    (aircraft_id, operation_type, entry_time),
    ...
]
```

---

### 5. **agents/aeropuerto_ar.py** - RL-Enhanced Airport Agent

Extends the baseline agent with Q-learning for intelligent runway scheduling.

#### Reinforcement Learning Framework:

**State Space**: `(free_runways, queue_length, avg_wait_time)`
- `free_runways`: Number of available runways
- `queue_length`: Current number of waiting aircraft
- `avg_wait_time`: Average waiting time of queued aircraft

**Action Space**: 2 discrete actions
- **Action 0**: Select aircraft with **longest wait time** (fairness priority)
- **Action 1**: Select aircraft with **shortest operation duration** (efficiency priority)

**Reward Function**:
```
R(t) = -(queue_length + 3 × total_wait_time)
```
- Negative reward encourages minimizing queue and delays
- Weight of 3 on wait time emphasizes reducing passenger delays

#### Q-Learning Parameters:

```python
self.Q = defaultdict(lambda: defaultdict(float))  # Q[state][action] = value

# Hyperparameters
self.alpha = 0.1    # Learning rate
self.gamma = 0.9    # Discount factor (emphasizes future rewards)
self.epsilon = 0.2  # Exploration rate (20% random action, 80% greedy)
```

#### ε-Greedy Strategy:

```python
def choose_action(self, state)
    if random.random() < self.epsilon:
        return random.randint(0, 1)  # Exploration: random action
    else:
        q_vals = self.Q[state]
        return max(q_vals, key=q_vals.get, default=0)  # Exploitation: best Q-value
```

#### Aircraft Selection Logic:

```python
def _select_aircraft_from_queue(self, action)
    if action == 0:
        # Find aircraft with maximum wait time
        idx = max(range(len(self.queue)), 
                  key=lambda i: current_time - self.queue[i][2])
    
    elif action == 1:
        # Find aircraft with shortest operation duration
        idx = min(range(len(self.queue)),
                  key=lambda i: get_operation_time(self.queue[i]))
    
    return self.queue.pop(idx)
```

#### Q-Table Update (Temporal Difference Learning):

```python
def update_Q(self, state, action, reward, next_state)
    old_val = self.Q[state][action]
    best_next = max(self.Q[next_state].values(), default=0)
    
    # Standard Q-learning update rule
    self.Q[state][action] = old_val + alpha × (reward + gamma × best_next - old_val)
```

#### Processing Loop:

```python
async def _process_queue()
    while self.queue is not empty:
        runway = _get_available_runway(current_time)
        if not runway: break
        
        state = _get_state()
        action = choose_action(state)
        reward = calculate_reward()
        
        aircraft = _select_aircraft_from_queue(action)
        
        runway["status"] = "OCCUPIED"
        runway["current_aircraft"] = aircraft
        
        update_Q(state, action, reward, next_state)
```

---

### 6. **messages/messages.py** - Message Types

All inter-agent communication uses typed Pydantic models.

#### Message Definitions:

```python
class Message_Request(BaseModel):
    """Aircraft → Airport: Request runway access"""
    content: str        # "takeoff" | "landing"
    sender: str         # Aircraft ID
    time: int          # Request timestamp

class Message_Respond(BaseModel):
    """Airport → Aircraft: Authorization decision"""
    authorized: bool    # True if runway granted
    runway_id: int | None
    time: int          # Response timestamp

class Message_Finish(BaseModel):
    """Aircraft → Airport: Operation completed"""
    sender: str         # Aircraft ID
    runway_id: int      # Which runway was used
    time: int          # Completion timestamp

class Message_Tick(BaseModel):
    """Clock → All Agents: Time increment"""
    time: int          # Current simulation minute

class AircraftInfo(BaseModel):
    """Aircraft → Airports: Registration and performance data"""
    aircraft_id: str
    wait_time: int     # Pre-takeoff waiting period
    t_takeoff: int     # Takeoff duration
    t_landing: int     # Landing duration

class MetricsReport(BaseModel):
    """Agent → Clock: Performance metrics at simulation end"""
    agent_id: str
    data: dict         # Agent-specific metrics

class AirportPosition(BaseModel):
    """Airport → Aircraft: Location information"""
    airport_id: str
    x: int            # X coordinate
    y: int            # Y coordinate
```

---

## Simulation Workflow

### Initialization Phase (t=0):

1. **Clock Agent** starts and broadcasts `Message_Tick(time=0)`
2. **Aircraft Agents** receive tick, initialize, and send `AircraftInfo` to both airports
3. **Airport Agents** receive aircraft information and register them
4. **Airport Agents** respond with `AirportPosition`

### Main Loop (t=1 to TOTAL_MINUTES-1):

For each time step:

1. **Clock broadcasts tick** to all agents
2. **Aircraft evaluate state**:
   - WAITING: Check if wait time elapsed → send takeoff request
   - TAKING_OFF: Check if operation time elapsed → transition to FLYING
   - FLYING: Calculate position and ETA
   - AWAITING_LANDING_AUTH: Check conditions → send landing request
   - LANDING: Check if operation complete → send finish message

3. **Airport evaluates queue**:
   - Check for available runways (respecting operation gap)
   - If queue not empty and runway available:
     - **Baseline**: Select first aircraft in queue (FIFO)
     - **RL**: Apply Q-learning to choose selection strategy
   - Grant runway access or keep aircraft waiting

### Termination Phase (t=TOTAL_MINUTES):

1. **Clock broadcasts `Message_End`**
2. **All agents** collect final metrics and send `MetricsReport` to Clock
3. **Clock** aggregates and prints summary statistics
4. **Simulation terminates**

---

## Running the Simulation

### Prerequisites:

```bash
pip install autogen-core pydantic asyncio
```

### Basic Execution:

```bash
python src/main.py
```

### Configuration Options:

Edit `src/main.py` to modify:

```python
# Switch between baseline and RL
USE_RL = True   # Enable Q-learning optimization
USE_RL = False  # Use baseline FIFO scheduling

# Simulation duration
TOTAL_MINUTES = 300  # Simulate 5 hours

# System size
NUM_AIRPORTS = 4
NUM_AIRCRAFT = 6

# Individual aircraft parameters
AIRCRAFT_SPEEDS[0] = 5      # Make first aircraft faster
TAKEOFF_TIMES[2] = 4        # Increase takeoff time for aircraft 3
```

---

## Performance Metrics

The simulation tracks:

### Per-Airport Metrics:
- **Takeoffs**: Total number of authorized departures
- **Landings**: Total number of authorized arrivals
- **Runway Utilization**: Percentage of time runways are occupied
- **Average Queue Length**: Mean number of waiting aircraft

### Per-Aircraft Metrics:
- **Takeoff Delay**: Time between request and authorization
- **Landing Delay**: Time between arrival and landing authorization
- **Total Flight Time**: From takeoff to landing
- **Completion Status**: Success or timeout

### System-Wide Metrics:
- **Throughput**: Total aircraft processed per unit time
- **Average Delay**: Mean delay across all operations
- **Queue Instability**: Variance in queue length over time

---

## Reinforcement Learning Details

### Why Q-Learning?

Q-learning is model-free and doesn't require knowing transition probabilities between states. Perfect for the stochastic nature of air traffic:
- Aircraft arrival times are unpredictable
- Operation durations vary
- Runway availability changes dynamically

### Learning Process:

1. **Exploration Phase** (early episodes): Agent tries both strategies randomly
2. **Convergence Phase** (middle episodes): Agent gradually favors better actions
3. **Exploitation Phase** (final episodes): Agent consistently applies learned policy

### Expected Behavior:

- **Action 0 preferred** when: Multiple aircraft waiting (fairness minimizes max delay)
- **Action 1 preferred** when: Few aircraft, long operation times (process quick jobs first)
- **Trade-off learned**: Balance between passenger fairness and system throughput

### Customization:

Modify hyperparameters to change learning dynamics:

```python
self.alpha = 0.1    # Lower = slower learning, more stable
self.gamma = 0.9    # Higher = values long-term rewards more
self.epsilon = 0.2  # Higher = more exploration, slower convergence
```

---

## Architecture Decisions

### Why Message-Driven?

- **Decoupling**: Agents don't know internal details of others
- **Concurrency**: Asynchronous communication enables true parallel operation
- **Scalability**: Easy to add/remove agents without modifying core logic
- **Realistic**: Mirrors actual air traffic control (radar contacts, radio)

### Why Discrete Events?

- **Efficiency**: Only processes significant time points (no busy-waiting)
- **Determinism**: Reproducible given same random seed
- **Scale**: Can simulate weeks of operations in seconds

### Why Reinforcement Learning?

- **Adaptability**: Policy learns from experience, improves over time
- **Optimality**: RL can discover non-obvious efficient strategies
- **Generalization**: Can handle new airport configurations with retraining

---

## Limitations & Future Work

### Current Limitations:

1. **Single Runway Focus**: Most airports have only 1 runway (unrealistic)
2. **No Geographic Routing**: Aircraft take shortest path, no real airspace
3. **Deterministic Timing**: All operations take fixed time (no weather, congestion)
4. **Limited RL State**: Only 3 state dimensions; could include more features
5. **No Inter-Airport Coordination**: Each airport decides independently

### Future Enhancements:

1. **Multi-Runway Optimization**: Learn policies for selecting specific runways
2. **Dynamic Arrival Scheduling**: Pre-schedule arrivals instead of reactively queuing
3. **Stochastic Durations**: Add random variation to operation times
4. **Hierarchical Learning**: Central authority agent that coordinates airports
5. **Advanced RL**: Deep Q-Network (DQN) or Policy Gradient methods
6. **Real Data Integration**: Import actual flight schedules and airport layouts
7. **Conflict Resolution**: Model separation requirements, avoid collisions

---

## Code Examples

### Monitoring Simulation Progress:

```python
# In clock.py, modify start() to log metrics per interval
async def start(self, message: Message_Request, ctx: MessageContext):
    for t in range(self.total_minutes):
        print(f"\n===== MINUTE {t} =====")
        tick_msg = Message_Tick(time=t)
        await self.publish_message(tick_msg, topic_id=DefaultTopicId())
        
        if t % 60 == 0:  # Log every hour
            print(f"Queue lengths: {[len(runway['queue']) for runway in self.runways]}")
```

### Extracting Q-Table for Analysis:

```python
# After simulation (requires modifying agents to export)
def get_learned_policy(self):
    """Return learned Q-values for each state"""
    return dict(self.Q)

# Analysis in post-processing
learned_policy = airport_agent.get_learned_policy()
for state, actions in learned_policy.items():
    print(f"State {state}: Action 0 value={actions[0]}, Action 1 value={actions[1]}")
```

### Changing Reward Function:

```python
# In aeropuerto_ar.py, modify _process_queue()
def calculate_reward(self):
    # Original: penalize queue and wait time
    # reward = -(queue_length + 3 * total_wait_time)
    
    # Alternative: reward based on throughput
    # reward = 1 if aircraft_served else 0
    
    # Alternative: multi-objective
    throughput_bonus = 5  # per aircraft processed
    fairness_penalty = sum(abs(w - avg_wait) for w in wait_times)
    reward = throughput_bonus - 0.1 * fairness_penalty
    
    return reward
```

---

## References

- **AutoGen Core Framework**: Microsoft's multi-agent orchestration library
- **Q-Learning**: Sutton & Barto, "Reinforcement Learning: An Introduction"
- **Discrete Event Simulation**: Banks & Carson, "Discrete-Event System Simulation"
- **Air Traffic Control**: FAA guidelines and ICAO standards

---

