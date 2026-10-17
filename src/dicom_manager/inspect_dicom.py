from pathlib import Path  # 用于拼接和处理文件路径
from pydicom import dcmread  # 用于读取 DICOM 文件
from pydicom.errors import InvalidDicomError  # 用于识别一类 DICOM 格式读取错误

# 从当前脚本的位置找到项目根目录。
# parents[0] 是 dicom_manager，parents[1] 是 src，parents[2] 是项目根目录。
project_root = Path(__file__).resolve().parents[2]

# 指向刚才复制进新项目的真实样本。
dicom_file = project_root / "data" / "samples" / "CT_small.dcm"

try:
    # 读取文件，返回包含 DICOM 信息的 Dataset 对象。
    dataset = dcmread(
        dicom_file,  # 要读取的文件路径
        stop_before_pixels=True,  # 在像素数据之前停止读取
        specific_tags=["Modality", "Rows", "Columns"],  # 只选取这三个技术字段
    )

    # get() 获取字段的值；字段不存在时，返回我们指定的“未知”。
    modality = dataset.get("Modality", "未知")
    rows = dataset.get("Rows", "未知")
    columns = dataset.get("Columns", "未知")

    # 打印文件名及读取到的技术信息。
    print(f"文件名：{dicom_file.name}")
    print(f"影像类型：{modality}")
    print(f"图像行数：{rows}")
    print(f"图像列数：{columns}")

except FileNotFoundError:
    # 文件不在指定位置时，打印路径，方便查找原因。
    print(f"找不到文件：{dicom_file}")

except InvalidDicomError:
    # 文件存在，但不能按当前读取方式识别为 DICOM 时，给出提示。
    print(f"无法按 DICOM 格式读取：{dicom_file.name}")
