from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from forge.core.security import verify_api_key
from forge.services.rag_service import rag_service

router = APIRouter(prefix="/rag", tags=["rag"])


class IngestFileRequest(BaseModel):
    file_path: str


class IngestDirectoryRequest(BaseModel):
    dir_path: str
    pattern: str = "*"


class DeleteDocumentRequest(BaseModel):
    filename: str


@router.post("/ingest/file")
async def ingest_file(request: IngestFileRequest, _key: str = Depends(verify_api_key)):
    return await rag_service.ingest_file(request.file_path)


@router.post("/ingest/directory")
async def ingest_directory(
    request: IngestDirectoryRequest, _key: str = Depends(verify_api_key)
):
    return await rag_service.ingest_directory(request.dir_path, request.pattern)


@router.get("/search")
async def search(q: str, top_k: int = 5, _key: str = Depends(verify_api_key)):
    return await rag_service.search(q, top_k=top_k)


@router.delete("/document")
async def delete_document(
    request: DeleteDocumentRequest, _key: str = Depends(verify_api_key)
):
    return await rag_service.delete_from_index(request.filename)
