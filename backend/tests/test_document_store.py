"""测试内存文档存储。"""

from app.services.document_store import Document, DocumentStore


def test_add_and_list():
    store = DocumentStore()
    doc = store.add(filename="resume.pdf", doc_type="resume", text="我的简历", size_bytes=100)
    assert doc.id
    assert doc.filename == "resume.pdf"
    listed = store.list()
    assert len(listed) == 1
    assert listed[0].id == doc.id
    assert listed[0].filename == "resume.pdf"


def test_list_does_not_lose_metadata():
    """list 返回完整 Document（含 text），元信息可断言。"""
    store = DocumentStore()
    store.add(filename="q.md", doc_type="qa", text="很长的内容...", size_bytes=10)
    listed = store.list()
    assert listed[0].size_bytes == 10
    assert listed[0].doc_type == "qa"


def test_delete_removes_document():
    store = DocumentStore()
    doc = store.add(filename="a.md", doc_type="qa", text="x", size_bytes=1)
    assert store.delete(doc.id) is True
    assert store.list() == []
    # 再删一次返回 False
    assert store.delete(doc.id) is False


def test_get_by_type_filters():
    store = DocumentStore()
    store.add(filename="r.pdf", doc_type="resume", text="r", size_bytes=1)
    store.add(filename="q1.md", doc_type="qa", text="q1", size_bytes=1)
    store.add(filename="q2.md", doc_type="qa", text="q2", size_bytes=1)
    resumes = store.get_by_type("resume")
    qas = store.get_by_type("qa")
    assert len(resumes) == 1
    assert len(qas) == 2


# ---- 持久化（落盘 + 重启加载）----
def test_persist_across_restart(tmp_path):
    """add 后新建同名 store（模拟重启），应能加载到已存文档。"""
    path = str(tmp_path / "docs.json")
    s1 = DocumentStore(path=path)
    doc = s1.add(filename="resume.pdf", doc_type="resume", text="我的简历内容", size_bytes=100)

    # 模拟重启：新实例读同一文件
    s2 = DocumentStore(path=path)
    loaded = s2.list()
    assert len(loaded) == 1
    assert loaded[0].id == doc.id
    assert loaded[0].filename == "resume.pdf"
    assert loaded[0].text == "我的简历内容"


def test_persist_after_delete(tmp_path):
    """delete 后落盘，重启后该文档不再存在。"""
    path = str(tmp_path / "docs.json")
    s1 = DocumentStore(path=path)
    doc = s1.add(filename="q.md", doc_type="qa", text="x", size_bytes=1)
    s1.delete(doc.id)

    s2 = DocumentStore(path=path)
    assert s2.list() == []


def test_corrupted_file_treated_as_empty(tmp_path):
    """文件损坏时视为空，不崩溃。"""
    path = str(tmp_path / "docs.json")
    path_file = tmp_path / "docs.json"
    path_file.write_text("{这不是合法json", encoding="utf-8")

    s = DocumentStore(path=path)
    assert s.list() == []


def test_in_memory_mode_does_not_touch_disk(tmp_path):
    """path=None 纯内存模式，不读写任何文件。"""
    s = DocumentStore()  # 无参
    s.add(filename="a.md", doc_type="qa", text="x", size_bytes=1)
    # data 目录下不应有文件被创建
    assert not (tmp_path / "docs.json").exists()
