from autogen_core import RoutedAgent, message_handler, MessageContext, AgentId, default_subscription, DefaultTopicId
from messages.messages import *


@default_subscription
class AirportAgent(RoutedAgent):
    def __init__(self, airport_id: str, x: int, y: int, num_runways: int, operation_gap_minutes: int):
        super().__init__(airport_id)

        self.airport_id = airport_id
        self.x = x
        self.y = y
        self.num_runways = num_runways
        self.operation_gap_minutes = operation_gap_minutes
        self.queue = []  # [(aircraft_id, op_type, entry_time)]
        self.aircrafts = {}  # aircraft_id -> AircraftInfo
        self.counter = 0  
        self.my_metrics_dict = {}

        self.current_time = 0

        self.takeoffs = 0
        self.landings = 0

        self.runways = []
        for i in range(num_runways):
            self.runways.append({
                "runway_id": i,
                "status": "FREE",          # FREE / OCCUPIED
                "current_aircraft": None,
                "last_operation_time": -operation_gap_minutes
            })

    @message_handler
    async def on_tick(self, message: Message_Tick, ctx: MessageContext) -> None:
        self.current_time = message.time
        await self._process_queue()

    @message_handler
    async def handle_info(self, message: AircraftInfo, ctx: MessageContext) -> None:

        self.aircrafts[message.aircraft_id] = message
        pos_msg = AirportPosition(airport_id=self.airport_id, x=self.x, y=self.y)
        await self.send_message(pos_msg, ctx.sender)
        print(f"[{self.airport_id}] Registrado avión {message.aircraft_id} y enviada posición")



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
            print(f"[{self.airport_id}] AUTORIZADO {op_type} de {sender} en pista {runway['runway_id']}")
            if op_type == "takeoff":
                self.takeoffs += 1
            elif op_type == "landing":
                self.landings += 1

        else:
            if not any(item[0] == sender for item in self.queue):

                self.queue.append((sender, op_type, time))
                print(f"[{self.airport_id}] Queue: {sender} waiting for {op_type} since t={time}")

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
      



    async def _process_queue(self):

        while self.queue:
            runway = self._get_available_runway(self.current_time)
            if not runway:
                break 
            best_idx = 0
            best_score = float('inf')

            for i, (aircraft_id, op_type, entry_time) in enumerate(self.queue):

                wait_time = self.current_time - entry_time
                duration = self.aircrafts[aircraft_id].t_takeoff if op_type == "takeoff" else self.aircrafts[aircraft_id].t_landing

                score = duration / (wait_time + 1)

                if wait_time > 8:  # After 8 minutes penalize more
                    score = score * 0.5  # Reduce score 
                
                if score < best_score:
                    best_score = score
                    best_idx = i

            aircraft_id, op_type, entry_time = self.queue.pop(best_idx)
            runway["status"] = "OCCUPIED"
            runway["current_aircraft"] = aircraft_id
            runway["last_operation_time"] = self.current_time

            if op_type == "takeoff":
                self.takeoffs += 1
            elif op_type == "landing":
                self.landings += 1

            
            await self.send_message(Message_Respond(authorized=True, runway_id=runway["runway_id"], time=self.current_time), AgentId(aircraft_id, "default"))
            print(f"Notificando a {aircraft_id} que su {op_type} está autorizado en pista {runway['runway_id']} en {self.airport_id}")
