import asyncio
from autogen_core import AgentId, SingleThreadedAgentRuntime
from agents.aeropuerto import AirportAgent
from agents.aeropuerto_ar import AirportAgentAR
from agents.avion import AircraftAgent
from agents.clock import ClockAgent
from messages.messages import Message_Request


# ================== PARÁMETROS DE SIMULACIÓN ==================
# Tamaño de la cuadrícula
GRID_WIDTH = 20
GRID_HEIGHT = 20

TOTAL_MINUTES = 50

NUM_AIRPORTS = 3
NUM_AIRCRAFT = 6

MAX_RUNWAYS = 2

# Tiempo mínimo entre operaciones en pista
OPERATION_GAP_MINUTES = 3

# Velocidad media de cada aeronave (celdas/min)
AIRCRAFT_SPEEDS = [3, 3, 4, 6, 5, 5]

# Tiempos medios de despegue y aterrizaje por aeronave
TAKEOFF_TIMES = [2, 2, 3, 3, 3, 4]
LANDING_TIMES = [2, 3, 3, 4, 3, 4]

# Tiempo de espera en aeropuerto antes de pedir pista
WAIT_TIMES = [2, 3, 2, 3, 1, 2]
# Aprendizaje por refuerzo activado/desactivado
USE_RL = True


AIRPORTS = [
    {"id": "MAD", "x": 0, "y": 0, "num_runways": 2},
    {"id": "BCN", "x": 10, "y": 10, "num_runways": 2},
    {"id": "SEV", "x": 5, "y": 15, "num_runways": 2},
]
ROUTES = [
    ("PL001", "MAD", "BCN"),
    ("PL002", "BCN", "SEV"),
    ("PL003", "BCN", "MAD"),
    ("PL004", "SEV", "MAD"),
    ("PL005", "SEV", "BCN"),
    ("PL006", "MAD", "BCN"),
]

async def main():


    runtime = SingleThreadedAgentRuntime()

    for i, ap in enumerate(AIRPORTS[:NUM_AIRPORTS]):
        agent_class = AirportAgentAR if USE_RL else AirportAgent
        await agent_class.register(
            runtime,
            ap["id"],
            lambda ap=ap: agent_class(
                ap["id"],
                x=ap["x"],
                y=ap["y"],
                num_runways=ap["num_runways"],
                operation_gap_minutes=OPERATION_GAP_MINUTES
            )
        )


    for i, (aircraft_id, origin, dest) in enumerate(ROUTES[:NUM_AIRCRAFT]):
        await AircraftAgent.register(
            runtime,
            aircraft_id,
            lambda i=i, aircraft_id=aircraft_id, origin=origin, dest=dest: AircraftAgent(
                aircraft_id,
                airport_origin=origin,
                airport_destination=dest,
                wait_time=WAIT_TIMES[i],
                takeoff_time=TAKEOFF_TIMES[i],
                landing_time=LANDING_TIMES[i],
                speed=AIRCRAFT_SPEEDS[i]
            )
        )


    await ClockAgent.register(runtime, "clock", lambda: ClockAgent("clock", total_minutes=TOTAL_MINUTES, num_aircraft=NUM_AIRCRAFT, num_airports=NUM_AIRPORTS))

    runtime.start()

    clock_id = AgentId("clock", "default")
    await runtime.send_message(Message_Request(content="start", sender="system", time=0), clock_id)

    await runtime.stop_when_idle()

if __name__ == "__main__":  

    asyncio.run(main())