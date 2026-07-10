"""文档存储：本地 JSON 文件持久化，跨进程/重启不丢。

存储路径由构造函数传入（默认 backend/data/documents.json）。
- add/delete 后立即同步写盘。
- 启动时自动加载已有文档。
- 原子写：先写 .tmp 再 rename，避免写一半损坏。
"""

import json
import os
import threading
import uuid
from dataclasses import dataclass
from typing import Dict, List

DEFAULT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data",
    "documents.json",
)


@dataclass
class Document:
    id: str
    filename: str
    doc_type: str  # "resume" | "qa"
    text: str
    size_bytes: int

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "filename": self.filename,
            "doc_type": self.doc_type,
            "text": self.text,
            "size_bytes": self.size_bytes,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Document":
        return cls(
            id=d["id"],
            filename=d["filename"],
            doc_type=d["doc_type"],
            text=d["text"],
            size_bytes=d["size_bytes"],
        )


class DocumentStore:
    """按 id 索引的文档存储。

    path 传入时落盘到本地 JSON（生产用）；path=None 时纯内存（测试用）。
    """

    def __init__(self, path: str | None = None) -> None:
        self._path = path
        self._docs: Dict[str, Document] = {}
        # 写盘加锁，避免并发 add/delete 互相覆盖。
        self._lock = threading.Lock()
        if path is not None:
            self._load()

    # ---- 持久化 ----
    def _load(self) -> None:
        """启动时从磁盘加载已有文档。文件不存在或损坏时视为空。"""
        assert self._path is not None
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for d in data.get("documents", []):
                doc = Document.from_dict(d)
                self._docs[doc.id] = doc
        except FileNotFoundError:
            pass  # 首次运行，无文件
        except (json.JSONDecodeError, KeyError):
            # 文件损坏：视为空，避免启动崩溃（可加日志）
            pass

    def _save(self) -> None:
        """原子写：先写 .tmp 再 rename。path=None 时跳过（纯内存模式）。"""
        if self._path is None:
            return
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        data = {"documents": [d.to_dict() for d in self._docs.values()]}
        tmp = self._path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self._path)  # 原子重命名

    # ---- 业务 ----
    def add(self, filename: str, doc_type: str, text: str, size_bytes: int) -> Document:
        doc = Document(
            id=uuid.uuid4().hex,
            filename=filename,
            doc_type=doc_type,
            text=text,
            size_bytes=size_bytes,
        )
        with self._lock:
            self._docs[doc.id] = doc
            self._save()
        return doc

    def list(self) -> List[Document]:
        return list(self._docs.values())

    def delete(self, doc_id: str) -> bool:
        with self._lock:
            if doc_id in self._docs:
                del self._docs[doc_id]
                self._save()
                return True
            return False

    def get_by_type(self, doc_type: str) -> List[Document]:
        return [d for d in self._docs.values() if d.doc_type == doc_type]
