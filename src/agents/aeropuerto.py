from autogen_core import RoutedAgent, message_handler, MessageContext, AgentId, default_subscription, DefaultTopicId
from messages.messages import *
import heapq



@default_subscription
class AirportAgent(RoutedAgent):
    def __init__(self, airport_id: str, x: int, y: int, num_runways: int, operation_gap_minutes: int):
        super().__init__(airport_id)

        # Datos básicos
        self.airport_id = airport_id
        self.x = x
        self.y = y
        self.num_runways = num_runways
        self.operation_gap_minutes = operation_gap_minutes
        self.queue = []  # [(aircraft_id, op_type, sender_time)]
        self.planes = {}  # plane_id -> PlaneInfo
        self.counter = 0  # para ordenar en la cola

        self.current_time = 0

        # Estado dinámico de las pistas
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
        await self._process_queue()  # Revisa la cola en cada tick

    @message_handler
    async def handle_info(self, message: PlaneInfo, ctx: MessageContext) -> None:
        self.planes[message.plane_id] = message
        # Responder con la posición del aeropuerto
        pos_msg = AirportPosition(airport_id=self.airport_id, x=self.x, y=self.y)
        await self.send_message(pos_msg, ctx.sender)
        print(f"[{self.airport_id}] Registrado avión {message.plane_id} y enviada posición")



    @message_handler
    async def handle_request(self, message: Message_Request, ctx: MessageContext) -> None:
        """Procesa solicitudes de aviones"""
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

        else:
            if not any(item[0] == sender for item in self.queue):
                info = self.planes[sender]
                duration = info.t_takeoff if op_type == "takeoff" else info.t_landing

                self.counter += 1
                heapq.heappush(self.queue, (duration, self.counter, sender, op_type))
                await self.send_message(Message_Respond(authorized=False, runway_id=None, time=time), AgentId(sender, "default"))
                print(f"[{self.airport_id}] Cola: {sender} esperando para {op_type} (duración {duration})")

            await self.send_message(Message_Respond(authorized=False, runway_id=None, time=time), AgentId(sender, "default"))




    @message_handler
    async def handle_finish(self, message: Message_Finish, ctx: MessageContext) -> None:
        """Procesa confirmaciones de finalización de operaciones"""
        runway_id = message.runway_id
        time = message.time

        for runway in self.runways:
            if runway["runway_id"] == runway_id:
                runway["status"] = "FREE"
                runway["current_aircraft"] = None
                runway["last_operation_time"] = time
                

    
    @message_handler
    async def on_finish(self, message: Message_End, ctx: MessageContext) -> None:
        await self.send_message(
            MetricsReport(agent_type="airport", agent_id=self.aircraft_id, data=self.my_metrics_dict),
            AgentId("clock", "default")
    )


    def _get_available_runway(self, current_time):
        """Encuentra pista libre que respete el tiempo mínimo"""
        for runway in self.runways:
            if (runway["status"] == "FREE" and 
                current_time - runway["last_operation_time"] >= self.operation_gap_minutes):
                return runway
        return None
      



    async def _process_queue(self):
        """Procesa la cola de espera si hay pistas libres"""
        while self.queue:
            runway = self._get_available_runway(self.current_time)
            if not runway:
                break  # No hay pistas libres

            duration, _, plane_id, op_type = heapq.heappop(self.queue)
            runway["status"] = "OCCUPIED"
            runway["current_aircraft"] = plane_id
            runway["last_operation_time"] = self.current_time

            # Notificar al avión (lógica de notificación no implementada aquí)
            await self.send_message(Message_Respond(authorized=True, runway_id=runway["runway_id"], time=self.current_time), AgentId(plane_id, "default"))
            print(f"Notificando a {plane_id} que su {op_type} está autorizado en pista {runway['runway_id']}")