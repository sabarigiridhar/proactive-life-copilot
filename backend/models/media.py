"""Typed API responses for uploaded media processing."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class TranscriptionData(BaseModel):
    media_type: Literal["audio"] = "audio"
    text: str = Field(min_length=1, max_length=20_000)
    content_type: str
    duration_seconds: float = Field(gt=0)


class ImageExtractionData(BaseModel):
    media_type: Literal["image"] = "image"
    text: str = Field(min_length=1, max_length=50_000)
    content_type: str
    width: int = Field(gt=0)
    height: int = Field(gt=0)
