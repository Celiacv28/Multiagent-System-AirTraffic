from autogen_core import RoutedAgent, message_handler, MessageContext, AgentId, default_subscription, DefaultTopicId
from messages.messages import *
from collections import defaultdict
import random



@default_subscription
class AirportAgentAR(RoutedAgent):
    def __init__(self, airport_id: str, x: int, y: int, num_runways: int, operation_gap_minutes: int):
        super().__init__(airport_id)

        self.airport_id = airport_id
        self.x = x
        self.y = y
        self.num_runways = num_runways
        self.operation_gap_minutes = operation_gap_minutes
        self.queue = []  # [(aircraft_id, op_type, entry_time)]
        self.aircrafts = {}  # aircraft_id -> AircraftInfo
        self.my_metrics_dict = {}

        self.takeoffs = 0
        self.landings = 0

        self.current_time = 0


        self.runways = []
        for i in range(num_runways):
            self.runways.append({
                "runway_id": i,
                "status": "FREE",          # FREE / OCCUPIED
                "current_aircraft": None,
                "last_operation_time": -operation_gap_minutes
            })

        # ================ RL ================ #
        self.Q = defaultdict(lambda: defaultdict(float))  # Q[state][action] = value
        self.alpha = 0.1   # Learning rate
        self.gamma = 0.9   # Future discount
        self.epsilon = 0.2 # Exploration

    @message_handler
    async def on_tick(self, message: Message_Tick, ctx: MessageContext) -> None:
        self.current_time = message.time
        await self._process_queue() 

    @message_handler
    async def handle_info(self, message: AircraftInfo, ctx: MessageContext) -> None:
        self.aircrafts[message.aircraft_id] = message
        pos_msg = AirportPosition(airport_id=self.airport_id, x=self.x, y=self.y)
        await self.send_message(pos_msg, ctx.sender)
        print(f"[{self.airport_id}] Aircraft {message.aircraft_id} registered and position sent")



    @message_handler
    async def handle_request(self, message: Message_Request, ctx: MessageContext) -> None:
        op_type = message.content
        sender = message.sender
        time = message.time

        if op_type not in ("takeoff", "landing"):
            return await self.send_message(Message_Respond(authorized=False, runway_id=None, time=time), AgentId(sender, "default"))

        runway = self._get_available_runway(time)
        if runway:
            runway["status"] = "OCCUPIED"
            runway["current_aircraft"] = sender
            runway["last_operation_time"] = time
            await self.send_message(Message_Respond(authorized=True, runway_id=runway["runway_id"], time=time), AgentId(sender, "default"))
            print(f"[{self.airport_id}] AUTHORIZED {op_type} by {sender} on runway {runway['runway_id']}")
            if op_type == "takeoff":
                self.takeoffs += 1
            elif op_type == "landing":
                self.landings += 1
        else:
            if not any(s == sender for s, _, _ in self.queue):
                self.queue.append((sender, op_type, time))
                print(f"[{self.airport_id}] Queue: {sender} waiting for {op_type}")
            await self.send_message(Message_Respond(authorized=False, runway_id=None, time=time), AgentId(sender, "default"))




    @message_handler
    async def handle_finish(self, message: Message_Finish, ctx: MessageContext) -> None:
        runway_id = message.runway_id
        time = message.time

        for runway in self.runways:
            if runway["runway_id"] == runway_id:
                runway["status"] = "FREE"
                runway["current_aircraft"] = None
                runway["last_operation_time"] = time
                

    
    @message_handler
    async def on_finish(self, message: Message_End, ctx: MessageContext) -> None:
        self.my_metrics_dict = {
            "airport_id": self.airport_id,
            "num_runways": self.num_runways,
            "takeoffs": self.takeoffs,
            "landings": self.landings,
        }
        await self.send_message(
            MetricsReport(agent_id=self.airport_id, data=self.my_metrics_dict),
            AgentId("clock", "default")
    )


    def _get_available_runway(self, current_time):
        for runway in self.runways:
            if (runway["status"] == "FREE" and 
                current_time - runway["last_operation_time"] >= self.operation_gap_minutes):
                return runway
        return None
      
    def _get_state(self):
        free = sum(1 for r in self.runways if r["status"] == "FREE")
        
        if not self.queue:
            avg_wait = 0
        else:
            total_wait = sum(self.current_time - et for _, _, et in self.queue)
            avg_wait = total_wait // len(self.queue)  
        
        return (free, len(self.queue), avg_wait)


    

    def choose_action(self, state):
        """ε-greedy strategy with 2 fixed actions"""
        num_actions = 2  # [0: longest wait, 1: shortest duration]
        
        if not self.queue:
            return None

        # Random exploration
        if random.random() < self.epsilon:
            return random.randint(0, num_actions - 1)

        q_vals = self.Q[state]
        return max(q_vals, key=q_vals.get, default=0)
    

    def _select_aircraft_from_queue(self, action):
        if not self.queue:
            return None, None, None

        if action == 0: 
            idx = max(range(len(self.queue)), key=lambda i: self.current_time - self.queue[i][2])

        elif action == 1:  
            idx = min(
                range(len(self.queue)),
                key=lambda i: self.aircrafts[self.queue[i][0]].t_takeoff
                            if self.queue[i][1] == "takeoff"
                            else self.aircrafts[self.queue[i][0]].t_landing
            )

        return self.queue.pop(idx)
        



    def update_Q(self, state, action, reward, next_state):
        old_val = self.Q[state][action]
        best_next = max(self.Q[next_state].values(), default=0)
        self.Q[state][action] = old_val + self.alpha * (reward + self.gamma * best_next - old_val)



    async def _process_queue(self):
        while self.queue:
            runway = self._get_available_runway(self.current_time)
            if not runway:
                break

            state = self._get_state()
            action = self.choose_action(state)
            if action is None:
                break

            queue_length_penalty = len(self.queue)
            total_wait_time = sum(self.current_time - et for _, _, et in self.queue)
            reward = -(queue_length_penalty + 3 * total_wait_time)

            aircraft_id, op_type, entry_time = self._select_aircraft_from_queue(action)

            runway["status"] = "OCCUPIED"
            runway["current_aircraft"] = aircraft_id
            runway["last_operation_time"] = self.current_time

            if op_type == "takeoff":
                self.takeoffs += 1
            elif op_type == "landing":
                self.landings += 1

            next_state = self._get_state()
            self.update_Q(state, action, reward, next_state)

            await self.send_message(
                Message_Respond(authorized=True, runway_id=runway["runway_id"], time=self.current_time),
                AgentId(aircraft_id, "default")
            )
            print(f"[RL {self.airport_id}] Action {action}: runway {runway['runway_id']} → {aircraft_id} (reward={reward})")

