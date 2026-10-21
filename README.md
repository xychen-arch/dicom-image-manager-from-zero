# DICOM Image Manager

## 项目简介

这是一个用于学习 Python、FastAPI、pydicom 和 SQLite 的 DICOM 影像管理后端。

项目可以接收 DICOM 文件，校验文件大小和必要影像字段，保存文件本体，并将技术元数据登记到 SQLite。项目还提供影像列表、类型筛选、详情查询和重复影像检测接口。

本项目仅用于编程学习，不用于临床诊断或医疗决策。

## 当前功能

- `GET /health`：检查服务是否正常运行
- `POST /upload`：上传并保存 DICOM 文件
- `GET /images`：查询影像列表，可使用 `modality` 参数筛选
- `GET /images/{file_id}`：按服务器生成的 ID 查询单条影像详情
- 单个上传文件最大为 10 MiB，超限返回 `413`
- 空文件、无法解析的文件或缺少必要影像字段时返回 `400`
- 上传前使用 pydicom 读取 DICOM，并检查 `Modality`、`Rows`、`Columns`
- 文件本体使用服务器生成的随机名称保存到 `data/uploads`
- 技术元数据保存到 SQLite 数据库 `data/images.sqlite3`
- 文件保存和数据库登记都成功后才返回 `201`
- 服务器计算文件内容的 SHA-256，完全相同的文件重复上传返回 `409`
- 非空的 SOP Instance UID 具有唯一约束，重复上传返回 `409`
- 数据库登记失败或重复冲突时，只清理本次新建的文件
- 查询不到影像详情时返回 `404`
- 查询列表没有匹配记录时返回 `200` 和空列表 `[]`
- 可以通过 `DICOM_DATA_DIR` 指定独立数据目录，用于隔离自动化测试

## 保存的数据

上传成功后，SQLite 会记录以下技术信息：

- 服务器生成的影像 ID
- SOP Instance UID
- 文件内容 SHA-256
- Modality
- Rows
- Columns
- 服务器保存文件名
- 文件字节数
- 创建时间

项目不使用患者姓名作为文件名或主键。

## 样本来源

`data/samples/CT_small.dcm` 使用 pydicom 自带的公开测试样本。

项目中的样本和接口仅用于软件开发学习，不代表完整的临床 DICOM 支持范围。

## 安装依赖

在项目根目录执行：

只运行项目时安装：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

需要运行自动化测试时安装：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

运行项目需要：

- FastAPI
- Uvicorn
- python-multipart
- pydicom

运行自动化测试还需要：

- pytest
- httpx

## 启动 API 服务

在项目根目录执行：

```powershell
.\.venv\Scripts\python.exe -m uvicorn dicom_manager.app:app --app-dir src --reload
```

启动后可以访问：

- 健康检查：http://127.0.0.1:8000/health
- Swagger 接口文档：http://127.0.0.1:8000/docs

停止服务时，在运行服务的终端中按 `Ctrl+C`。

## 接口响应

| 场景 | HTTP 状态码 |
| --- | ---: |
| 有效 DICOM 上传成功 | 201 |
| 普通文本、空文件或缺少必要字段 | 400 |
| 完全相同的文件内容 | 409 |
| 重复的非空 SOP Instance UID | 409 |
| 文件超过 10 MiB | 413 |
| 查询不存在的影像 ID | 404 |
| 文件或数据库处理失败 | 500 |

## 运行自动化测试

自动化测试使用独立的数据库和上传目录，不会修改真实的 `data/images.sqlite3` 和 `data/uploads`。

测试数据保存在 `D:\Codex\求职\dicom-image-manager-test-runs` 下每次运行生成的唯一目录中。

在项目根目录执行：

```powershell
.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider
```

当前自动化测试覆盖：

- 新 DICOM 首次上传返回 `201`
- 相同内容即使改名或缺少 UID，再次上传仍返回 `409`
- 相同 SOP Instance UID 即使文件字节不同仍返回 `409`
- 重复上传不增加数据库记录或磁盘文件
- 普通文本、空文件和缺少 `Rows` 返回 `400`
- 超限文件返回 `413`
- 未知影像 ID 返回 `404`
- 缺少 SOP Instance UID 时仍使用 SHA-256 阻止相同内容重复保存
- 模拟并发哈希冲突时返回 `409` 并清理本次新文件
- 数据库登记失败时返回 `500`，并清理本次新建的文件

最近一次本地运行结果为：

```text
10 passed, 2 warnings
```

两条警告分别来自 pydicom 对 Python 3.17 的兼容性提醒，以及 Starlette
TestClient 对当前 httpx 用法的弃用提醒；当前测试均已通过。

## 运行 DICOM 信息读取脚本

在项目根目录执行：

```powershell
.\.venv\Scripts\python.exe .\src\dicom_manager\inspect_dicom.py
```

## 已知限制

- 项目仅用于学习，不用于临床诊断
- 当前只检查少量必要的 DICOM 技术字段
- 缺少 SOP Instance UID 的文件仍允许首次上传，但无法判断字节不同的文件是否属于同一影像实例
- 当前没有影像预览和文件下载接口
- 当前没有用户认证、权限控制和完整的医疗工作流
- 当前测试环境仍有两条第三方依赖弃用警告
