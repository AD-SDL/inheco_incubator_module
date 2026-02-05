"""Pydantic models for HTTP POST requests to FastAPI interface wrapper"""

from typing import Literal, Optional

from pydantic import BaseModel


class TemperatureRequest(BaseModel):
    """Model for setting temperature on incubator devices."""

    stack_floor: int
    temperature: float


class StartShakerRequest(BaseModel):
    """Model for starting the shaker on the incubator devices."""

    stack_floor: int
    status: Literal[1, "1", "ND"]


class SetShakerParametersRequest(BaseModel):
    """Model for setting shaker parameters on the incubator devices."""

    stack_floor: int
    frequency: Optional[float] = None
