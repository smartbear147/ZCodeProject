"""测试文档上传/列表/删除路由。"""

from io import BytesIO

from fastapi.testclient import TestClient

from app.deps import get_document_store
from app.main import app
from app.services.document_store import DocumentStore


def _override_store() -> DocumentStore:
    store = DocumentStore()
    app.dependency_overrides[get_document_store] = lambda: store
    return store


def test_upload_markdown_then_list():
    _override_store()
    client = TestClient(app)
    resp = client.post(
        "/api/documents/upload",
        data={"doc_type": "qa"},
        files={"file": ("q.md", BytesIO("# 题目\n答案".encode("utf-8")), "text/markdown")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["filename"] == "q.md"
    assert body["doc_type"] == "qa"

    listed = client.get("/api/documents/list").json()
    assert len(listed["documents"]) == 1
    assert listed["documents"][0]["filename"] == "q.md"
    app.dependency_overrides.clear()


def test_upload_invalid_doc_type_returns_400():
    _override_store()
    client = TestClient(app)
    resp = client.post(
        "/api/documents/upload",
        data={"doc_type": "unknown"},
        files={"file": ("x.md", BytesIO(b"x"), "text/markdown")},
    )
    assert resp.status_code == 400
    app.dependency_overrides.clear()


def test_upload_unsupported_format_returns_400():
    _override_store()
    client = TestClient(app)
    resp = client.post(
        "/api/documents/upload",
        data={"doc_type": "resume"},
        files={"file": ("x.docx", BytesIO(b"x"), "application/octet-stream")},
    )
    assert resp.status_code == 400
    app.dependency_overrides.clear()


def test_delete_removes_document():
    store = _override_store()
    doc = store.add(filename="a.md", doc_type="qa", text="x", size_bytes=1)
    client = TestClient(app)
    resp = client.delete(f"/api/documents/{doc.id}")
    assert resp.status_code == 200
    assert resp.json()["deleted"] is True
    assert store.list() == []
    app.dependency_overrides.clear()


def test_delete_unknown_returns_404():
    _override_store()
    client = TestClient(app)
    resp = client.delete("/api/documents/nonexistent")
    assert resp.status_code == 404
    app.dependency_overrides.clear()
