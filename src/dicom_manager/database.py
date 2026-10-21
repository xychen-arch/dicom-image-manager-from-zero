import os  # 读取测试运行时指定的数据目录
import sqlite3
from pathlib import Path

# 未指定测试目录时，继续使用项目原有的 data 目录。
project_root = Path(__file__).resolve().parents[2]
data_dir = Path(os.environ.get("DICOM_DATA_DIR", str(project_root / "data")))
db_path = data_dir / "images.sqlite3"

def init_db():
    # 测试目录可能是新目录，先创建它再连接数据库。
    data_dir.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)

    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS images(
                id TEXT PRIMARY KEY NOT NULL,
                sop_instance_uid TEXT,
                modality TEXT NOT NULL,
                rows INTEGER NOT NULL,
                columns INTEGER NOT NULL,
                stored_filename TEXT NOT NULL,
                size_bytes INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 让数据库拒绝重复的、非空的 SOP Instance UID。
        # IF NOT EXISTS 允许应用重启时再次执行初始化。
        conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_images_sop_instance_uid
            ON images(sop_instance_uid)
            WHERE sop_instance_uid IS NOT NULL
            """
        )

        conn.commit()
    finally:
        conn.close()

def save_image_record(
        file_id, sop_instance_uid, modality, rows, columns, stored_filename, size_bytes
):
    conn = sqlite3.connect(db_path)

    try:
        conn.execute(
            """
            INSERT INTO images(
                id, sop_instance_uid, modality, rows, columns, stored_filename, size_bytes
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                file_id, sop_instance_uid, modality, rows, columns, stored_filename, size_bytes
            ),
        )
        conn.commit()
    except sqlite3.Error:
        conn.rollback()
        raise
    finally:
        conn.close()

def list_image_records(modality=None):
    """查询影像列表；给出 modality 时只查询该类型。"""
    conn = sqlite3.connect(db_path)  # 连接项目数据库。
    conn.row_factory = sqlite3.Row  # 让查询结果能按列名读取。
    try:
        if modality is None:
            # 没有筛选条件时，查询全部记录。
            rows = conn.execute(
                "SELECT * FROM images ORDER BY created_at DESC, id DESC"
            ).fetchall()
        else:
            # 问号接收参数，避免把用户输入直接拼进 SQL。
            rows = conn.execute(
                "SELECT * FROM images WHERE modality = ? "
                "ORDER BY created_at DESC, id DESC",
                (modality,),  # 单个参数也要写成元组，所以有结尾的逗号。
            ).fetchall()

        # 把每一行变成字典；没有记录时自然得到 []。
        return [dict(row) for row in rows]
    finally:
        conn.close()  # 查询成功或失败都关闭连接。


def get_image_record(file_id):
    """按 ID 查询一条影像记录。"""
    conn = sqlite3.connect(db_path)  # 连接项目数据库。
    conn.row_factory = sqlite3.Row  # 允许把查询行转换为字典。
    try:
        # fetchone() 找到时返回一行，找不到时返回 None。
        row = conn.execute(
            "SELECT * FROM images WHERE id = ?",
            (file_id,),  # 参数化传入 ID。
        ).fetchone()

        # 找不到就交回 None，由后续接口决定返回 404。
        return dict(row) if row is not None else None
    finally:
        conn.close()  # 始终关闭连接。

if __name__ == "__main__":
    init_db()
    
    print(f"数据库已初始化：{db_path}")
