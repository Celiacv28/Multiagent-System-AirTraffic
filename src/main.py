import asyncio
from autogen_core import AgentId, SingleThreadedAgentRuntime
from agents.aeropuerto import AirportAgent
from agents.avion import AircraftAgent
from agents.clock import ClockAgent
from messages.messages import Message_Request

async def main():
    runtime = SingleThreadedAgentRuntime()

    # Registrar aeropuertos
    await AirportAgent.register(
        runtime,
        "MAD",
        lambda: AirportAgent("MAD", x=0, y=0, num_runways=1, operation_gap_minutes=3),
    )
    await AirportAgent.register(
        runtime,
        "BCN",
        lambda: AirportAgent("BCN", x=10, y=10, num_runways=1, operation_gap_minutes=3),
    )


    # Registrar aviones
    await AircraftAgent.register(runtime, "PL001", lambda: AircraftAgent("PL001", airport_origin="MAD", airport_destination="BCN",
                          wait_time=2, takeoff_time=2, landing_time=2, speed=2))
    await AircraftAgent.register(runtime, "PL002", lambda: AircraftAgent("PL002", airport_origin="BCN", airport_destination="MAD",
                          wait_time=3, takeoff_time=2, landing_time=3, speed=3))
    await AircraftAgent.register(runtime, "PL003", lambda: AircraftAgent("PL003", airport_origin="BCN", airport_destination="MAD",
                          wait_time=2, takeoff_time=3, landing_time=3, speed=4))

    # Registrar el ClockAgent (broadcast)
    await ClockAgent.register(runtime, "clock", lambda: ClockAgent("clock", total_minutes=30))

    runtime.start()

    # Enviar mensaje de inicio al ClockAgent
    clock_id = AgentId("clock", "default")
    await runtime.send_message(Message_Request(content="start", sender="system", time=0), clock_id)

    await runtime.stop_when_idle()

if __name__ == "__main__":
    asyncio.run(main())