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


class MobileRemoteConfigRequest(BaseModel):
    enabled: bool


class MobileDeviceRegisterRequest(BaseModel):
    device_id: str = Field(min_length=8, max_length=128)
    platform: str = Field(min_length=2, max_length=64, default="web_pwa")
    network_mode: str = Field(min_length=3, max_length=16, default="auto")
    push_subscription: dict[str, Any] | None = None
    push_token: str = ""


class MobileDeviceUnregisterRequest(BaseModel):
    device_id: str = Field(min_length=8, max_length=128)


class MobileNotificationPreferencesRequest(BaseModel):
    push_enabled: bool | None = None
    telegram_fallback_enabled: bool | None = None
    quiet_hours: dict[str, Any] | None = None


class RuntimeSettingUpdateRequest(BaseModel):
    key: str = Field(min_length=1, max_length=64)
    value: str = Field(min_length=1, max_length=64)


class CameraOnboardingApplyRequest(BaseModel):
    node_id: str = Field(min_length=1, max_length=64)
    stream_url: str = Field(min_length=1, max_length=512)
    fallback_stream_url: str = Field(default="", max_length=512)
