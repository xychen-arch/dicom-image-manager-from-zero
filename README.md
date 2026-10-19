# DICOM Image Manager

## 项目目标

练习使用 Python 管理 DICOM 医学影像文件，并学习读取文件中的技术元数据。

## 当前进度

- 已创建 Python 入口文件，并能在项目虚拟环境中运行。
- 已创建项目目录和 Python 虚拟环境
- 程序可以读取 `data/samples/hello.txt`
- 程序可以列出 `data/samples` 中的文件
- 10.17
- 可读取公开 DICOM 样本的 Modality、Rows、Columns
- 可提示文件不存在、无法按 DICOM 格式读取两种错误
- 已建立 FastAPI 服务，GET /health 可返回状态信息
- 可通过 /docs 页面调用接口

## 样本来源

data/samples/CT_small.dcm 使用 pydicom 自带的公开示例文件。
项目仅用于学习，不用于临床诊断。

## 运行 DICOM 信息读取脚本

在项目根目录执行：

    .\.venv\Scripts\python.exe .\src\dicom_manager\inspect_dicom.py

## 启动 API 服务

在项目根目录执行：

    .\.venv\Scripts\python.exe -m pip install fastapi uvicorn python-multipart pydicom
    .\.venv\Scripts\python.exe -m uvicorn dicom_manager.app:app --app-dir src --reload

健康检查：http://127.0.0.1:8000/health

接口文档：http://127.0.0.1:8000/docs

停止服务：在运行服务的终端按 Ctrl+C。

## 计划功能

- 扫描 DICOM 文件
- 读取必要的技术元数据
- 保存元数据并支持查询

## 当前功能

- POST /upload 可接收并保存单个小文件
- 服务器生成保存文件名，上传内容存入 data/uploads
- 返回文件 ID、原始文件名、保存文件名和实际字节数
- 当前保存上限为 10 MiB，超限返回 413
- 上传前读取 DICOM 并检查 Modality、Rows、Columns；空文件、无法读取或缺少必要字段返回 400，且不保存
