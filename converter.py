"""
文件转 PDF 转换器
支持：图片（JPG/PNG）、Word（.docx）、Excel（.xlsx）
"""
import subprocess
import tempfile
import shutil
import os
import platform
import threading

# LibreOffice 同时只能运行一个实例，用锁防止并发冲突
_soffice_lock = threading.Lock()


def get_soffice_path():
    """获取 LibreOffice 命令行路径"""
    if platform.system() == "Darwin":
        # macOS
        mac_path = "/Applications/LibreOffice.app/Contents/MacOS/soffice"
        if os.path.exists(mac_path):
            return mac_path
    # Linux 或 fallback
    path = shutil.which("soffice") or shutil.which("libreoffice")
    if path:
        return path
    return None


def convert_image_to_pdf(image_data, filename):
    """
    将图片转为 PDF（使用 Pillow）
    返回 PDF 二进制数据
    """
    from PIL import Image
    from io import BytesIO

    img = Image.open(BytesIO(image_data))

    # 转为 RGB（去掉透明通道）
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")

    output = BytesIO()
    img.save(output, "PDF", resolution=150)
    return output.getvalue()


def convert_office_to_pdf(file_data, filename):
    """
    将 Word/Excel 转为 PDF（使用 LibreOffice）
    返回 PDF 二进制数据
    """
    soffice = get_soffice_path()
    if not soffice:
        raise Exception("未安装 LibreOffice，无法转换 Word/Excel 文件")

    # 创建临时目录
    tmp_dir = tempfile.mkdtemp()
    try:
        # 写入源文件
        src_path = os.path.join(tmp_dir, filename)
        with open(src_path, "wb") as f:
            f.write(file_data)

        # 加锁，防止多个 LibreOffice 实例同时运行
        with _soffice_lock:
            result = subprocess.run(
                [soffice, "--headless", "--convert-to", "pdf", "--outdir", tmp_dir, src_path],
                capture_output=True,
                text=True,
                timeout=60,
            )

        if result.returncode != 0:
            raise Exception(f"LibreOffice 转换失败: {result.stderr}")

        # 找到输出的 PDF 文件
        pdf_name = os.path.splitext(filename)[0] + ".pdf"
        pdf_path = os.path.join(tmp_dir, pdf_name)

        if not os.path.exists(pdf_path):
            raise Exception("转换后的 PDF 文件未找到")

        with open(pdf_path, "rb") as f:
            return f.read()

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def to_pdf(file_data, filename):
    """
    统一转换入口
    根据文件扩展名选择转换方式
    返回 (pdf_data, error)
    """
    ext = os.path.splitext(filename)[1].lower()

    try:
        if ext == ".pdf":
            return file_data, None
        elif ext in (".jpg", ".jpeg", ".png"):
            pdf_data = convert_image_to_pdf(file_data, filename)
            return pdf_data, None
        elif ext in (".docx", ".doc", ".xlsx", ".xls", ".pptx", ".ppt", ".csv"):
            pdf_data = convert_office_to_pdf(file_data, filename)
            return pdf_data, None
        else:
            return None, f"不支持的文件格式: {ext}"
    except Exception as e:
        return None, str(e)
