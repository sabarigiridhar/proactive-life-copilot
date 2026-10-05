"""REST routes for settings and local data snapshots."""

from fastapi import APIRouter

from backend.core.dependencies import RequestIdDep, SettingsDep
from backend.models.preferences import (
    AppPreferencesPatch,
    BackupData,
    SettingsData,
)
from backend.models.responses import ApiResponse, success_response
from backend.services.preferences import (
    create_local_backup,
    get_settings_data,
    save_preferences,
)


router = APIRouter(tags=["settings"])


@router.get("/settings", response_model=ApiResponse[SettingsData])
def get_settings(
    settings: SettingsDep,
    request_id: RequestIdDep,
) -> ApiResponse[SettingsData]:
    return success_response(get_settings_data(settings), request_id)


@router.patch("/settings", response_model=ApiResponse[SettingsData])
def patch_settings(
    payload: AppPreferencesPatch,
    settings: SettingsDep,
    request_id: RequestIdDep,
) -> ApiResponse[SettingsData]:
    return success_response(save_preferences(payload, settings), request_id)


@router.post("/data/backups", response_model=ApiResponse[BackupData], status_code=201)
def create_backup(
    settings: SettingsDep,
    request_id: RequestIdDep,
) -> ApiResponse[BackupData]:
    return success_response(create_local_backup(settings), request_id)
