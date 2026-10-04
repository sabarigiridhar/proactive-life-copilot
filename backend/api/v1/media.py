"""Multipart media-processing routes."""

from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, UploadFile

from backend.core.dependencies import RequestIdDep, SettingsDep
from backend.models.media import ImageExtractionData, TranscriptionData
from backend.models.responses import ApiResponse, success_response
from backend.services.media import MediaInputError, extract_image, transcribe_audio
from life_copilot.agent.provider import ProviderCallError


router = APIRouter(prefix="/media", tags=["media"])


def _media_error(exc: Exception) -> HTTPException:
    if isinstance(exc, MediaInputError):
        return HTTPException(status_code=exc.status_code, detail=str(exc))
    return HTTPException(status_code=503, detail=str(exc))


@router.post("/transcriptions", response_model=ApiResponse[TranscriptionData])
async def post_transcription(
    settings: SettingsDep,
    request_id: RequestIdDep,
    file: UploadFile = File(...),
) -> ApiResponse[TranscriptionData]:
    try:
        data = await transcribe_audio(file, settings)
    except (MediaInputError, ProviderCallError) as exc:
        raise _media_error(exc) from None
    return success_response(data, request_id)


@router.post("/extractions", response_model=ApiResponse[ImageExtractionData])
async def post_image_extraction(
    settings: SettingsDep,
    request_id: RequestIdDep,
    file: UploadFile = File(...),
) -> ApiResponse[ImageExtractionData]:
    try:
        data = await extract_image(file, settings)
    except (MediaInputError, ProviderCallError) as exc:
        raise _media_error(exc) from None
    return success_response(data, request_id)
