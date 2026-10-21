import hashlib
import sqlite3  # 捕获数据库写入错误
from uuid import uuid4  # 生成随机标识，作为服务器保存文件时的名字

from fastapi import FastAPI, HTTPException, UploadFile
import pydicom
from pydicom.errors import InvalidDicomError

# 导入建表、写入、列表查询和单条查询函数。
# 数据库和上传文件共用同一个数据目录。
from dicom_manager.database import (
    data_dir,
    get_image_record_by_content_sha256,
    init_db,
    save_image_record,
    list_image_records,
    get_image_record,
)


app = FastAPI(title="DICOM Image Manager")
# 启动应用时确保 images 表存在。
init_db()

# 上传文件保存在与数据库相同的数据目录下。
upload_dir = data_dir / "uploads"

# 文件夹不存在时创建；已经存在时正常继续。
upload_dir.mkdir(parents=True, exist_ok=True)

# 当前练习允许单个文件最大为 10 MiB，即 10485760 字节。
MAX_FILE_SIZE = 10 * 1024 * 1024


@app.get("/health")
def health():
    # 保留原来的健康检查接口。
    return {"status": "ok"}


# POST 用于提交文件；201 表示成功创建了新的资源。
@app.post("/upload", status_code=201)
def upload_file(file: UploadFile):
    # 最多读取“大小上限 + 1”字节，避免无限制地读入内存。
    content = file.file.read(MAX_FILE_SIZE + 1)

    # bytes 的长度就是本次读取到的字节数。
    size_bytes = len(content)

    # 多读到的那 1 字节，可以帮助判断文件是否超过上限。
    if size_bytes > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail="文件超过大小限制，未保存",
        )

    if size_bytes == 0:
        raise HTTPException(
            status_code=400,
            detail="文件为空，未保存",
        )
    file.file.seek(0)

    try:
        ds = pydicom.dcmread(file.file, stop_before_pixels=True)
    except InvalidDicomError:
        raise HTTPException(
            status_code=400,
            detail="不是可读取的DICOM文件,未保存",
        )

    if not ds.get("Modality") or ds.get("Rows") is None or ds.get("Columns") is None:
        raise HTTPException(status_code=400, detail="缺少必要的影像字段，未保存")

    # 哈希由服务器根据实际收到的字节计算，不信任客户端文件名或声明值。
    content_sha256 = hashlib.sha256(content).hexdigest()

    try:
        existing_image = get_image_record_by_content_sha256(content_sha256)
    except sqlite3.Error as exc:
        raise HTTPException(status_code=500, detail="保存或登记失败") from exc

    # 顺序重复上传在写文件前拒绝，避免产生需要清理的新副本。
    if existing_image is not None:
        raise HTTPException(status_code=409, detail="相同文件内容已存在")

    # 由服务器生成随机标识，不使用上传者提供的文件名拼接路径。
    file_id = uuid4().hex

    # 目前统一使用 .bin 后缀，表示按二进制内容保存。
    stored_filename = f"{file_id}.bin"

    # 保存路径只由固定目录和服务器生成的名字组成。
    saved_path = upload_dir / stored_filename

    # 记录本次是否真的新建了文件，避免出错时误删已有文件。
    saved_file_created = False

    try:
        # 先保存文件本体。
        with saved_path.open("xb") as output_file:
            saved_file_created = True
            output_file.write(content)

        # 再把这次上传的信息登记到 SQLite。
        save_image_record(
            file_id=file_id,
            sop_instance_uid=str(ds.SOPInstanceUID) if ds.get("SOPInstanceUID") else None,
            content_sha256=content_sha256,
            modality=str(ds.Modality),
            rows=int(ds.Rows),
            columns=int(ds.Columns),
            stored_filename=stored_filename,
            size_bytes=size_bytes,
        )
    except sqlite3.IntegrityError as exc:
        # 数据库拒绝登记时，清理本次新建的文件。
        if saved_file_created:
            saved_path.unlink(missing_ok=True)

        # 并发请求可能同时通过预查询，最终由数据库唯一索引拒绝重复内容。
        if "images.content_sha256" in str(exc):
            raise HTTPException(
                status_code=409,
                detail="相同文件内容已存在",
            ) from exc

        # 字节不同但 SOP UID 相同的影像仍由 UID 唯一约束拒绝。
        if "images.sop_instance_uid" in str(exc):
            raise HTTPException(
                status_code=409,
                detail="相同 SOP Instance UID 的影像已存在",
            ) from exc
        raise HTTPException(status_code=500, detail="保存或登记失败") from exc

    except (OSError, sqlite3.Error) as exc:
        # 文件保存失败或其他数据库错误，仍按原逻辑处理。
        if saved_file_created:
            saved_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail="保存或登记失败") from exc
    # 将文件信息交给 FastAPI，转换成 JSON 返回给浏览器。
    return {
        "id": file_id,
        "original_filename": file.filename,
        "stored_filename": stored_filename,
        "size_bytes": size_bytes,
    }

@app.get("/images")
def list_images(modality: str | None = None):
    # URL 中没有 modality 时查全部；有值时按该类型筛选。
    # 查询不到记录时，数据库函数返回空列表 []，接口正常返回 200。
    return list_image_records(modality)


@app.get("/images/{file_id}")
def image_detail(file_id: str):
    # 从 URL 路径取出 ID，查询对应的一条记录。
    image = get_image_record(file_id)

    # 只有按 ID 查详情且记录不存在时，才返回 404。
    if image is None:
        raise HTTPException(status_code=404, detail="影像不存在")

    # 找到记录时，把字典作为 JSON 返回。
    return image
