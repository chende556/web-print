"""
PDF 变换工具
对 PDF 进行旋转和缩放，模拟实际打印效果
缩放时保持 A4 页面大小不变，内容居中
"""
from io import BytesIO
from PyPDF2 import PdfReader, PdfWriter, PageObject, Transformation
from PyPDF2.generic import RectangleObject

# A4 尺寸（点，1 point = 1/72 inch）
A4_WIDTH = 595.28   # 210mm
A4_HEIGHT = 841.89  # 297mm


def transform_pdf(pdf_data, orientation="portrait", scaling=100):
    """
    对 PDF 进行旋转和缩放变换
    模拟实际打印效果：内容在 A4 纸张上缩放并居中

    orientation: "portrait"（纵向）或 "landscape"（横向）
    scaling: 百分比数字，如 100 = 原始大小，50 = 缩小一半

    返回变换后的 PDF 二进制数据
    """
    if orientation == "portrait" and scaling == 100:
        return pdf_data

    reader = PdfReader(BytesIO(pdf_data))
    writer = PdfWriter()

    scale_factor = scaling / 100.0

    # 目标页面尺寸
    if orientation == "landscape":
        page_width = A4_HEIGHT
        page_height = A4_WIDTH
    else:
        page_width = A4_WIDTH
        page_height = A4_HEIGHT

    for page in reader.pages:
        # 获取原始页面尺寸
        orig_width = float(page.mediabox.width)
        orig_height = float(page.mediabox.height)

        # 创建空白目标页面
        new_page = PageObject.create_blank_page(width=page_width, height=page_height)

        # 计算缩放后的内容尺寸
        content_width = orig_width * scale_factor
        content_height = orig_height * scale_factor

        # 如果内容比页面大，额外缩放以适应页面（fit）
        fit_scale = min(page_width / content_width, page_height / content_height, 1.0)
        final_scale = scale_factor * fit_scale
        content_width = orig_width * final_scale
        content_height = orig_height * final_scale

        # 居中偏移
        tx = (page_width - content_width) / 2
        ty = (page_height - content_height) / 2

        # 应用变换：缩放 + 平移居中
        transformation = Transformation().scale(final_scale, final_scale).translate(tx, ty)
        page.add_transformation(transformation)

        # 合并到新页面
        new_page.merge_page(page)
        writer.add_page(new_page)

    output = BytesIO()
    writer.write(output)
    return output.getvalue()
