"""Schemas for the echo debug tool."""

from pydantic import BaseModel, Field


class EchoInput(BaseModel):
    message: str = Field(..., min_length=1, description='Text to echo back.')
    customer_id: str | None = Field(
        default=None,
        description='Optional; echoed for scoping smoke tests.',
    )
    machine_serial: str | None = Field(
        default=None,
        description='Optional; echoed for scoping smoke tests.',
    )


class EchoOutput(BaseModel):
    echo: str
    customer_id: str | None = None
    machine_serial: str | None = None
