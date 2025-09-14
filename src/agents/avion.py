from autogen_core import Agent, message_handler, RoutedAgent, AgentId, MessageContext, default_subscription, DefaultTopicId
from messages.messages import *


@default_subscription
class AircraftAgent(RoutedAgent):
    def __init__(self, aircraft_id, airport_origin, airport_destination, wait_time, takeoff_time, landing_time, speed):
        super().__init__(aircraft_id)
        
        # Solo los datos básicos
        self.aircraft_id = aircraft_id
        self.airport_origin = airport_origin
        self.airport_destination = airport_destination
        self.wait_time = wait_time
        self.takeoff_time = takeoff_time
        self.landing_time = landing_time
        self.speed = speed
        self.origin_pos = None
        self.destination_pos = None
        self.time_traveler = None

        self.initialized = False

        # Estado actual
        self.state = "WAITING"
        self.assigned_runway = None

        
        # Control de tiempo
        self.wait_start_time = 0  # Cuándo empezó a esperar
        self.operation_start_time = 0  # Cuándo empezó despegue/aterrizaje
        self.flight_start_time = 0  # Cuándo empezó el vuelo

        # Métricas
        self.flight_count = 0
        self.takeoff_delays = []
        self.landing_delays = []
        # Para medir retrasos
        self.takeoff_request_time = None
        self.landing_request_time = None

    @message_handler
    async def on_tick(self, message: Message_Tick, ctx: MessageContext) -> None:
        # Llama a step con el tiempo recibido
        if not self.initialized:
            self.initialized = True
            await self.setup()


        await self.step(message.time)

    
    async def setup(self):
        # Enviar info al aeropuerto de origen
        msg = PlaneInfo(
            plane_id=self.aircraft_id,
            wait_time=self.wait_time,
            t_takeoff=self.takeoff_time,
            t_landing=self.landing_time,
            
        )
        await self.send_message(msg, AgentId(self.airport_origin, "default"))
        await self.send_message(msg, AgentId(self.airport_destination, "default"))
        print(f"[{self.aircraft_id}] Enviada info a aeropuertos")


    async def step(self, current_time: int):
        if self.state == "WAITING":
            # Verificar si ya esperó suficiente tiempo
            if current_time - self.wait_start_time >= self.wait_time:
                print(f"Avión {self.aircraft_id} listo para solicitar despegue.")

                msg = Message_Request(content="takeoff", sender=self.aircraft_id, time=current_time)
                self.state = "AWAITING_TAKEOFF_AUTH"
                self.takeoff_request_time = current_time
                await self.send_message(msg, AgentId(self.airport_origin, "default"))

                
        elif self.state == "TAKING_OFF":
            # Verificar si terminó el despegue
            if current_time - self.operation_start_time >= self.takeoff_time:                
                self.state = "FLYING"
                self.flight_start_time = current_time
                print(f"Avión {self.aircraft_id} ha despegado.")

                msg = Message_Finish(sender=self.aircraft_id, runway_id=self.assigned_runway, time=current_time)
                await self.send_message(msg, AgentId(self.airport_origin, "default"))

                
        elif self.state == "LANDING":
            # Verificar si terminó el aterrizaje
            if current_time - self.operation_start_time >= self.landing_time:
                self.state = "WAITING"
                msg = Message_Finish(sender=self.aircraft_id, runway_id=self.assigned_runway, time=current_time)
                await self.send_message(msg, AgentId(self.airport_destination, "default"))
                
                self.wait_start_time = current_time  # Empieza nueva espera
                # Intercambiar origen y destino para ruta de vuelta
                self._swap_route()
                self.flight_count += 1 

            
        elif self.state == "FLYING":
            # Verificar si terminó el vuelo
            if (current_time - self.flight_start_time) >= self.time_traveler:
                print(f"Avión {self.aircraft_id} listo para aterrizar.")
                msg = Message_Request(content="landing", sender=self.aircraft_id, time=current_time)
                self.state = "AWAITING_LANDING_AUTH"
                self.landing_request_time = current_time 
                await self.send_message(msg, AgentId(self.airport_destination, "default"))
               

        elif self.state in ("AWAITING_TAKEOFF_AUTH", "AWAITING_LANDING_AUTH"):
            # Esperando autorización, nada que hacer aquí
            pass

        return None
    

    def _calculate_flight_time(self):
        """Calcula tiempo de vuelo basado en distancia y velocidad"""
        if self.origin_pos is None or self.destination_pos is None:
            return None
        distance = abs(self.destination_pos[0] - self.origin_pos[0]) + abs(self.destination_pos[1] - self.origin_pos[1])
        flight_time = distance / self.speed
        return flight_time

    @message_handler
    async def handle_airport_position(self, message: AirportPosition, ctx: MessageContext) -> None:
        # Guardar la posición recibida
        if message.airport_id == self.airport_origin:
            self.origin_pos = (message.x, message.y)
        elif message.airport_id == self.airport_destination:
            self.destination_pos = (message.x, message.y)
        # Si ya tenemos ambas posiciones, calcular el tiempo de vuelo
        if self.origin_pos is not None and self.destination_pos is not None:
            self.time_traveler = self._calculate_flight_time()
            print(f"[{self.aircraft_id}] Tiempo de vuelo calculado: {self.time_traveler}")
    

    @message_handler
    async def handle_respond(self, message: Message_Respond, ctx: MessageContext) -> None:

        if message.authorized:
            print(f"[{self.aircraft_id}] autorizado en pista {message.runway_id} t={message.time}")
            self.assigned_runway = message.runway_id
            self.operation_start_time = message.time

            if self.state == "AWAITING_TAKEOFF_AUTH":
                if self.takeoff_request_time is not None:
                    delay = message.time - self.takeoff_request_time
                    self.takeoff_delays.append(delay)
                    self.takeoff_request_time = None
                self.state = "TAKING_OFF"
                
            elif self.state == "AWAITING_LANDING_AUTH":
                if self.landing_request_time is not None:
                    delay = message.time - self.landing_request_time
                    self.landing_delays.append(delay)
                    self.landing_request_time = None
                self.state = "LANDING"
                
        else:
            print(f"[{self.aircraft_id}] NO autorizado, esperando...")

    
    @message_handler
    async def on_finish(self, message: Message_End, ctx: MessageContext) -> None:
        self.my_metrics_dict = {
            "flights": self.flight_count,
            "takeoff_delays": self.takeoff_delays,
            "landing_delays": self.landing_delays,
        }
        await self.send_message(
            MetricsReport(agent_type="aircraft", agent_id=self.aircraft_id, data=self.my_metrics_dict),
            AgentId("clock", "default")
        )

    


    def _swap_route(self):
        """Intercambia origen y destino para vuelta"""
        self.airport_origin, self.airport_destination = self.airport_destination, self.airport_origin
        
