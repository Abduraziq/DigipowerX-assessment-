from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("message content must not be empty")
        return value.strip()


class ChatCompletionRequest(BaseModel):
    model: str
    messages: list[ChatMessage]
    max_tokens: int = Field(default=200, gt=0, le=2000)

    @field_validator("model")
    @classmethod
    def validate_model(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("messages")
    @classmethod
    def validate_messages(cls, value: list[ChatMessage]) -> list[ChatMessage]:
        if not value:
            raise ValueError("messages must not be empty")
        return value


class UsageInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input_tokens: int
    output_tokens: int
    total_tokens: int


class ChatCompletionResponse(BaseModel):
    request_id: str
    model: str
    worker_id: str
    response: str
    usage: UsageInfo
    latency_ms: int


class FailureConfig(BaseModel):
    healthy: bool | None = None
    mode: str | None = None
