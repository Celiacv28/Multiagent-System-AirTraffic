import asyncio
from autogen_core import AgentId, SingleThreadedAgentRuntime
from agents.aeropuerto import AirportAgent
from agents.aeropuerto_ar import AirportAgentAR
from agents.avion import AircraftAgent
from agents.clock import ClockAgent
from messages.messages import Message_Request


# ================== SIMULATION PARAMETERS ==================
GRID_WIDTH = 20
GRID_HEIGHT = 20

TOTAL_MINUTES = 300

NUM_AIRPORTS = 4
NUM_AIRCRAFT = 6

MAX_RUNWAYS = 1

# Minimum time between consecutive operations on the same runway
OPERATION_GAP_MINUTES = 3

# Average speed of each aircraft (cells/min)
AIRCRAFT_SPEEDS = [3, 4, 2, 4, 5, 6]

# Average takeoff and landing times per aircraft
TAKEOFF_TIMES = [2, 2, 3, 3, 2, 4]
LANDING_TIMES = [2, 3, 3, 4, 2, 5]

# Waiting time at airport before requesting runway
WAIT_TIMES = [2, 3, 2, 3, 4, 1]
# Reinforcement learning enabled/disabled
USE_RL = False


AIRPORTS = [
    {"id": "MAD", "x": 0, "y": 0, "num_runways": 1},
    {"id": "BCN", "x": 10, "y": 15, "num_runways": 2},
    {"id": "SEV", "x": 5, "y": 20, "num_runways": 3},
    {"id": "VLC", "x": 12, "y": 3, "num_runways": 1}
]
ROUTES = [
    ("PL001", "MAD", "BCN"),
    ("PL002", "BCN", "MAD"),
    ("PL003", "SEV", "BCN"),
    ("PL004", "VLC", "MAD"),
    ("PL005", "SEV", "MAD"),
    ("PL006", "VLC", "SEV")   
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