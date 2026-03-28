from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str
    password: str


class DeviceRegisterRequest(BaseModel):
    node_id: str = Field(min_length=1, max_length=64)
    label: str = Field(min_length=1, max_length=120)
    device_type: str = Field(min_length=1, max_length=32)
    location: str = ""
    ip: str = ""
    note: str = ""


class DeviceHeartbeatRequest(BaseModel):
    node_id: str = Field(min_length=1, max_length=64)
    ip: str = ""
    note: str = ""


class SensorEventRequest(BaseModel):
    node_id: str | None = None
    node: str | None = None
    event: str
    location: str | None = None
    value: float | None = None
    details: dict[str, Any] | str | None = None
    ip: str | None = None
    ts: str | None = None


class SensorReadingRequest(BaseModel):
    node_id: str
    reading_type: str
    value: float
    unit: str | None = None
    details: dict[str, Any] | None = None


class CreateFaceRequest(BaseModel):
    name: str
    note: str = ""


class CaptureFaceRequest(BaseModel):
    name: str
    image: str


class CameraControlRequest(BaseModel):
    node_id: str
    command: str


class AckRequest(BaseModel):
    status: str = "ACK"
