from pathlib import Path  # 处理文件和文件夹路径
from uuid import uuid4  # 生成随机标识，作为服务器保存文件时的名字

from fastapi import FastAPI, HTTPException, UploadFile
import pydicom
from pydicom.errors import InvalidDicomError


app = FastAPI(title="DICOM Image Manager")

# 从当前 app.py 的位置，找到项目根目录。
project_root = Path(__file__).resolve().parents[2]

# 所有上传文件都保存在项目自己的 data/uploads 中。
upload_dir = project_root / "data" / "uploads"

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

    # 由服务器生成随机标识，不使用上传者提供的文件名拼接路径。
    file_id = uuid4().hex

    # 目前统一使用 .bin 后缀，表示按二进制内容保存。
    stored_filename = f"{file_id}.bin"

    # 保存路径只由固定目录和服务器生成的名字组成。
    saved_path = upload_dir / stored_filename

    # x 表示新建文件，重名时会报错；b 表示以二进制方式写入。
    # with 代码块结束后，会自动关闭保存文件的句柄。
    with saved_path.open("xb") as output_file:
        output_file.write(content)

    # 将文件信息交给 FastAPI，转换成 JSON 返回给浏览器。
    return {
        "id": file_id,
        "original_filename": file.filename,
        "stored_filename": stored_filename,
        "size_bytes": size_bytes,
    }
