"""REST routes for saved records and dashboard aggregates."""

from __future__ import annotations

import sqlite3
from typing import Annotated

from fastapi import APIRouter, Body, HTTPException, Path, Query
from pydantic import ValidationError

from backend.core.dependencies import RequestIdDep, SettingsDep
from backend.models.records import (
    DashboardQuery,
    DashboardSummary,
    RecordDeletionData,
    RecordDomain,
    RecordListQuery,
    RecordMutationData,
    RecordPage,
    RecordPatch,
)
from backend.models.responses import ApiResponse, success_response
from backend.services.records import (
    RecordInputError,
    get_dashboard_summary,
    get_record_page,
    patch_record,
    remove_record,
)


router = APIRouter(tags=["records"])


def _record_error(exc: Exception) -> HTTPException:
    if isinstance(exc, KeyError):
        return HTTPException(status_code=404, detail="The requested record was not found.")
    if isinstance(exc, sqlite3.IntegrityError):
        return HTTPException(
            status_code=409,
            detail="The update conflicts with an existing record.",
        )
    if isinstance(exc, ValidationError):
        fields = sorted({str(error["loc"][-1]) for error in exc.errors()})
        return HTTPException(
            status_code=422,
            detail=f"Invalid values for: {', '.join(fields)}.",
        )
    return HTTPException(status_code=422, detail=str(exc))


@router.get("/logs/{domain}", response_model=ApiResponse[RecordPage])
def get_logs(
    domain: Annotated[RecordDomain, Path()],
    query: Annotated[RecordListQuery, Query()],
    settings: SettingsDep,
    request_id: RequestIdDep,
) -> ApiResponse[RecordPage]:
    try:
        data = get_record_page(domain, query, settings)
    except RecordInputError as exc:
        raise _record_error(exc) from None
    return success_response(data, request_id)


@router.patch(
    "/logs/{domain}/{record_id}",
    response_model=ApiResponse[RecordMutationData],
)
def patch_log(
    domain: Annotated[RecordDomain, Path()],
    record_id: Annotated[int, Path(gt=0)],
    payload: Annotated[RecordPatch, Body()],
    settings: SettingsDep,
    request_id: RequestIdDep,
) -> ApiResponse[RecordMutationData]:
    try:
        data = patch_record(domain, record_id, payload, settings)
    except (KeyError, RecordInputError, ValidationError, sqlite3.IntegrityError) as exc:
        raise _record_error(exc) from None
    return success_response(data, request_id)


@router.delete(
    "/logs/{domain}/{record_id}",
    response_model=ApiResponse[RecordDeletionData],
)
def delete_log(
    domain: Annotated[RecordDomain, Path()],
    record_id: Annotated[int, Path(gt=0)],
    confirm: Annotated[bool, Query()],
    settings: SettingsDep,
    request_id: RequestIdDep,
) -> ApiResponse[RecordDeletionData]:
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="Set confirm=true to delete this record.",
        )
    try:
        data = remove_record(domain, record_id, settings)
    except KeyError as exc:
        raise _record_error(exc) from None
    return success_response(data, request_id)


@router.get(
    "/dashboard/summary",
    response_model=ApiResponse[DashboardSummary],
    tags=["dashboard"],
)
def dashboard_summary(
    query: Annotated[DashboardQuery, Query()],
    settings: SettingsDep,
    request_id: RequestIdDep,
) -> ApiResponse[DashboardSummary]:
    try:
        data = get_dashboard_summary(query, settings)
    except RecordInputError as exc:
        raise _record_error(exc) from None
    return success_response(data, request_id)
