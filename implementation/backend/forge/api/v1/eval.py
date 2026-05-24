from __future__ import annotations

from fastapi import APIRouter, Depends

from forge.core.security import verify_api_key
from forge.services.eval_service import EvalService

router = APIRouter(prefix="/eval", tags=["eval"])
_eval_service = EvalService()


@router.post("/run")
async def run_eval(_key: str = Depends(verify_api_key)):
    return await _eval_service.run_eval_suite()


@router.get("/results")
async def get_results(_key: str = Depends(verify_api_key)):
    return _eval_service.get_last_results()
