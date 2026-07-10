"""文档上传/列表/删除路由。"""

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.deps import get_document_store
from app.schemas import DocumentInfo, DocumentListResponse
from app.services.doc_parser import UnsupportedFormatError, parse_document
from app.services.document_store import DocumentStore

router = APIRouter(prefix="/api/documents")

VALID_DOC_TYPES = {"resume", "qa"}
MAX_DOC_SIZE_BYTES = 10 * 1024 * 1024  # 单文件 10MB 上限


@router.post("/upload", response_model=DocumentInfo)
async def upload_document(
    doc_type: str = Form(...),
    file: UploadFile = File(...),
    store: DocumentStore = Depends(get_document_store),
) -> DocumentInfo:
    if doc_type not in VALID_DOC_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"doc_type 必须是 {sorted(VALID_DOC_TYPES)} 之一",
        )
    file_bytes = await file.read()
    if len(file_bytes) > MAX_DOC_SIZE_BYTES:
        raise HTTPException(status_code=400, detail="单个文件超过 10MB 限制")
    try:
        text = parse_document(file.filename or "unknown", file_bytes)
    except UnsupportedFormatError as e:
        raise HTTPException(status_code=400, detail=str(e))
    doc = store.add(
        filename=file.filename or "unknown",
        doc_type=doc_type,
        text=text,
        size_bytes=len(file_bytes),
    )
    return DocumentInfo(
        id=doc.id,
        filename=doc.filename,
        doc_type=doc.doc_type,
        size_bytes=doc.size_bytes,
    )


@router.get("/list", response_model=DocumentListResponse)
def list_documents(
    store: DocumentStore = Depends(get_document_store),
) -> DocumentListResponse:
    docs = store.list()
    return DocumentListResponse(
        documents=[
            DocumentInfo(
                id=d.id,
                filename=d.filename,
                doc_type=d.doc_type,
                size_bytes=d.size_bytes,
            )
            for d in docs
        ]
    )


@router.delete("/{doc_id}")
def delete_document(
    doc_id: str,
    store: DocumentStore = Depends(get_document_store),
) -> dict:
    ok = store.delete(doc_id)
    if not ok:
        raise HTTPException(status_code=404, detail="文档不存在")
    return {"id": doc_id, "deleted": True}
