from pydantic import BaseModel
from typing import Optional

class AirportPosition(BaseModel):
    airport_id: str
    x: int
    y: int


class Message_Request(BaseModel):
    content: str  # "takeoff" o "landing"
    sender: str
    time: int


class Message_Finish(BaseModel):
    sender: str
    runway_id: int
    time: int


class Message_Respond(BaseModel):
    authorized: bool
    runway_id: Optional[int]
    time: int


class AircraftInfo(BaseModel):
    aircraft_id: str
    wait_time: int
    t_takeoff: int
    t_landing: int
    

class Message_Tick(BaseModel):
    time: int


class MetricsReport(BaseModel):    
    agent_id: str
    data: dict

class Message_End(BaseModel):
    pass