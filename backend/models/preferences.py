"""Typed contracts for preferences, provider readiness, and local snapshots."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class AppPreferences(BaseModel):
    model_config = ConfigDict(extra="forbid")

    default_currency: str = Field(min_length=3, max_length=8)
    weekly_spending_limit: float | None = Field(default=None, ge=0)
    weekly_learning_minutes: int = Field(ge=0, le=10080)
    weekly_workouts: int = Field(ge=0, le=14)
    sleep_hours_target: float = Field(ge=0, le=24)
    updated_at: datetime

    @field_validator("default_currency", mode="before")
    @classmethod
    def normalize_currency(cls, value):
        return str(value).strip().upper() if value is not None else value


class AppPreferencesPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    default_currency: str | None = Field(default=None, min_length=3, max_length=8)
    weekly_spending_limit: float | None = Field(default=None, ge=0)
    weekly_learning_minutes: int | None = Field(default=None, ge=0, le=10080)
    weekly_workouts: int | None = Field(default=None, ge=0, le=14)
    sleep_hours_target: float | None = Field(default=None, ge=0, le=24)

    @field_validator("default_currency", mode="before")
    @classmethod
    def normalize_currency(cls, value):
        return str(value).strip().upper() if value is not None else value

    @model_validator(mode="after")
    def require_change(self):
        if not self.model_fields_set:
            raise ValueError("At least one preference must be supplied.")
        nullable = {"weekly_spending_limit"}
        if any(
            field not in nullable and getattr(self, field) is None
            for field in self.model_fields_set
        ):
            raise ValueError("Configured preference values cannot be null.")
        return self


class ProviderConfiguration(BaseModel):
    provider: str
    capability: str
    model: str
    configured: bool


class SettingsData(BaseModel):
    preferences: AppPreferences
    providers: list[ProviderConfiguration]


class BackupData(BaseModel):
    backup_name: str
    created_at: datetime
    includes: list[str]
    warnings: list[str] = Field(default_factory=list)
