from pathlib import Path  # 导入 Path，用它处理文件和文件夹路径

print("DICOM Image Manager 正在启动")  # 程序运行时显示启动提示

# __file__ 表示当前这个 main.py 文件的位置。
# resolve() 把它转换成完整的绝对路径。
current_file = Path(__file__).resolve()

# 当前文件在 src/dicom_manager/main.py。
# parents[0] 是 dicom_manager，parents[1] 是 src，
# parents[2] 才是项目根目录 dicom-image-manager-from-zero。
project_root = current_file.parents[2]

# 用项目根目录拼出 data/samples/hello.txt 的完整路径。
# / 在这里是 Path 拼接路径的写法，不是手动输入 Windows 反斜杠。
sample_file = project_root / "data" / "samples" / "hello.txt"

# 先检查这个路径是否存在，并且确实是一个文件。
if sample_file.is_file():
    # 用 UTF-8 编码读取文本，这样中文内容也能正常处理。
    text = sample_file.read_text(encoding="utf-8")

    # f 字符串可以把变量 text 的值放进大括号的位置。
    print(f"示例文本内容：{text}")
else:
    # 文件不存在时打印完整路径，方便检查文件放错了位置没有。
    print(f"没找到示例文件：{sample_file}")

# 根据项目根目录，找到存放公开练习样本的文件夹。
samples_dir = project_root / "data" / "samples"

# 先确认这个路径是文件夹，再尝试读取里面的内容。
if samples_dir.is_dir():
    print("samples 文件夹中的文件：")

    # iterdir() 会逐个给出文件夹中的项目。
    for item in samples_dir.iterdir():
        # 只打印文件；如果里面有子文件夹，就跳过。
        if item.is_file():
            print(f"- {item.name}")
else:
    print(f"没找到样本文件夹：{samples_dir}")
