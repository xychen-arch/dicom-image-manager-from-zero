import hashlib
import importlib
import io
import os
import sqlite3
import sys
from pathlib import Path
from uuid import uuid4

import pydicom
import pytest
from fastapi.testclient import TestClient

# 每次运行使用 D:\Codex 内的新目录，避免碰到真实影像数据。
project_root = Path(__file__).resolve().parents[1]
run_dir = project_root.parent / "dicom-image-manager-test-runs" / f"pytest-{uuid4().hex}"

# 必须先设置目录，再导入应用；应用在导入时会初始化数据库。
os.environ["DICOM_DATA_DIR"] = str(run_dir)
sys.path.insert(0, str(project_root / "src"))
database = importlib.import_module("dicom_manager.database")
app_module = importlib.import_module("dicom_manager.app")

# 确认应用确实指向测试目录。
assert database.data_dir == run_dir
assert app_module.upload_dir == run_dir / "uploads"

# 只读取现有 CT 样本，不修改它。
ct_bytes = (project_root / "data" / "samples" / "CT_small.dcm").read_bytes()


@pytest.fixture
def isolated_client(monkeypatch):
    # 每个测试使用自己的数据库和上传目录，测试之间互不影响。
    case_dir = run_dir / uuid4().hex
    monkeypatch.setattr(database, "data_dir", case_dir)
    monkeypatch.setattr(database, "db_path", case_dir / "images.sqlite3")
    monkeypatch.setattr(app_module, "upload_dir", case_dir / "uploads")

    database.init_db()
    app_module.upload_dir.mkdir(parents=True, exist_ok=True)

    client = TestClient(app_module.app)
    yield client, case_dir
    client.close()


def upload(client, filename, content):
    # 模拟浏览器向 /upload 发送文件。
    return client.post(
        "/upload",
        files={"file": (filename, content, "application/dicom")},
    )


def saved_state(case_dir):
    # 同时查看数据库记录数和磁盘文件名，用于检查失败请求的副作用。
    with sqlite3.connect(case_dir / "images.sqlite3") as conn:
        record_count = conn.execute("SELECT COUNT(*) FROM images").fetchone()[0]
    filenames = {path.name for path in (case_dir / "uploads").glob("*.bin")}
    return record_count, filenames


def dicom_without(field_name):
    # 在内存里复制样本并删除指定字段，不修改原始 CT 文件。
    dataset = pydicom.dcmread(io.BytesIO(ct_bytes))
    delattr(dataset, field_name)
    output = io.BytesIO()
    pydicom.dcmwrite(output, dataset)
    return output.getvalue()


def test_new_upload_then_duplicate_returns_409(isolated_client):
    client, case_dir = isolated_client

    # 第一次上传成功，文件与数据库各增加一份。
    first = upload(client, "CT_small.dcm", ct_bytes)
    assert first.status_code == 201
    stored_name = first.json()["stored_filename"]
    assert (case_dir / "uploads" / stored_name).read_bytes() == ct_bytes
    assert saved_state(case_dir) == (1, {stored_name})

    # 数据库保存的是服务器根据实际文件字节计算出的 SHA-256。
    with sqlite3.connect(case_dir / "images.sqlite3") as conn:
        saved_hash = conn.execute(
            "SELECT content_sha256 FROM images"
        ).fetchone()[0]
    assert saved_hash == hashlib.sha256(ct_bytes).hexdigest()

    # 即使修改客户端文件名，相同字节第二次上传仍被拒绝。
    second = upload(client, "renamed_CT.dcm", ct_bytes)
    assert second.status_code == 409
    assert saved_state(case_dir) == (1, {stored_name})


def test_same_uid_with_different_bytes_returns_409(isolated_client):
    client, case_dir = isolated_client

    # 修改非身份字段，使文件字节变化，但保留原 SOP Instance UID。
    dataset = pydicom.dcmread(io.BytesIO(ct_bytes))
    dataset.PatientName = "Changed^Name"
    output = io.BytesIO()
    pydicom.dcmwrite(output, dataset)
    changed_bytes = output.getvalue()
    assert changed_bytes != ct_bytes

    first = upload(client, "original.dcm", ct_bytes)
    second = upload(client, "changed.dcm", changed_bytes)

    assert first.status_code == 201
    assert second.status_code == 409
    assert saved_state(case_dir) == (1, {first.json()["stored_filename"]})


@pytest.mark.parametrize("kind", ["text", "empty", "missing_rows"])
def test_invalid_upload_returns_400_without_saving(isolated_client, kind):
    client, case_dir = isolated_client

    # 三种错误输入分别覆盖非 DICOM、空文件和缺少 Rows。
    if kind == "text":
        content = b"not a DICOM file"
    elif kind == "empty":
        content = b""
    else:
        content = dicom_without("Rows")

    response = upload(client, f"{kind}.dcm", content)
    assert response.status_code == 400
    assert saved_state(case_dir) == (0, set())


def test_oversize_returns_413_without_saving(isolated_client):
    client, case_dir = isolated_client

    # 比 10 MiB 上限多 1 字节。
    content = b"x" * (10 * 1024 * 1024 + 1)
    response = upload(client, "oversize.dcm", content)

    assert response.status_code == 413
    assert saved_state(case_dir) == (0, set())


def test_unknown_id_returns_404(isolated_client):
    client, case_dir = isolated_client

    # 查询不存在的 ID 不应产生数据库记录或文件。
    response = client.get("/images/missing-id")
    assert response.status_code == 404
    assert saved_state(case_dir) == (0, set())


def test_same_content_without_uid_returns_409(isolated_client):
    client, case_dir = isolated_client
    content = dicom_without("SOPInstanceUID")

    # 缺少 UID 仍可首次接收，但相同字节由 SHA-256 阻止重复保存。
    first = upload(client, "no-uid.dcm", content)
    second = upload(client, "renamed-no-uid.dcm", content)
    assert first.status_code == 201
    assert second.status_code == 409
    assert saved_state(case_dir) == (1, {first.json()["stored_filename"]})


def test_hash_integrity_error_cleans_new_file(isolated_client, monkeypatch):
    client, case_dir = isolated_client

    # 模拟两个并发请求都未在预查询阶段发现重复。
    monkeypatch.setattr(
        app_module,
        "get_image_record_by_content_sha256",
        lambda _content_sha256: None,
    )

    # 模拟数据库唯一索引在插入时发现内容哈希冲突。
    def raise_hash_conflict(**_kwargs):
        raise sqlite3.IntegrityError(
            "UNIQUE constraint failed: images.content_sha256"
        )

    monkeypatch.setattr(app_module, "save_image_record", raise_hash_conflict)
    response = upload(client, "CT_small.dcm", ct_bytes)

    assert response.status_code == 409
    assert saved_state(case_dir) == (0, set())


def test_database_error_cleans_new_file(isolated_client, monkeypatch):
    client, case_dir = isolated_client

    # 临时模拟数据库登记失败，只影响这一项测试。
    def fail_to_save(**_kwargs):
        raise sqlite3.OperationalError("模拟数据库失败")

    monkeypatch.setattr(app_module, "save_image_record", fail_to_save)
    response = upload(client, "CT_small.dcm", ct_bytes)

    assert response.status_code == 500
    assert saved_state(case_dir) == (0, set())
