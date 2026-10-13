"""
PDF 变换工具
对 PDF 进行旋转和缩放，输出固定为标准 A4 页面

使用 PyMuPDF (fitz) 做 PDF → 图片渲染并组装输出。

设计原则：
- orientation 决定 A4 画布本身是竖放还是横放
- 内容保持原始阅读方向不旋转，等比缩放放进目标画布
- scaling < 100 时靠顶对齐，== 100 时居中（跟系统打印行为一致）
"""
from io import BytesIO

# A4 尺寸（点，1 point = 1/72 inch）
A4_WIDTH = 595.28   # 210mm
A4_HEIGHT = 841.89  # 297mm


def transform_pdf(pdf_data, orientation="portrait", scaling=100):
    """
    对 PDF 进行旋转和缩放变换，输出固定为标准 A4 页面。

    orientation: "portrait"（A4 竖放）或 "landscape"（A4 横放）
    scaling: 百分比数字，100 = 内容尽量占满 A4 画布

    返回变换后的 PDF 二进制数据
    """
    import fitz

    scale_factor = scaling / 100.0

    if orientation == "landscape":
        canvas_width, canvas_height = A4_HEIGHT, A4_WIDTH
    else:
        canvas_width, canvas_height = A4_WIDTH, A4_HEIGHT

    src = fitz.open(stream=pdf_data, filetype="pdf")
    out = fitz.open()

    dpi = 300
    zoom = dpi / 72.0

    for page in src:
        # 渲染页面为图片
        matrix = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=matrix, alpha=False)
        img_bytes = pix.tobytes("png")

        # 图片对应的点尺寸（原始页面尺寸）
        img_width_pt = pix.width / zoom
        img_height_pt = pix.height / zoom

        # 计算放置尺寸（等比缩放到画布内）
        fit_scale = min(canvas_width / img_width_pt, canvas_height / img_height_pt)
        place_scale = fit_scale * scale_factor
        place_width = img_width_pt * place_scale
        place_height = img_height_pt * place_scale

        # 位置策略：100% 居中，缩小时靠顶
        x0 = (canvas_width - place_width) / 2
        if scale_factor < 1.0:
            y0 = 0
        else:
            y0 = (canvas_height - place_height) / 2
        x1 = x0 + place_width
        y1 = y0 + place_height

        new_page = out.new_page(width=canvas_width, height=canvas_height)
        new_page.insert_image(fitz.Rect(x0, y0, x1, y1), stream=img_bytes)

    result = out.tobytes(deflate=True)
    src.close()
    out.close()
    return result


def rasterize_pdf(pdf_data, dpi=300):
    """
    将 PDF 每一页渲染为图片再打包为 PDF。
    注意：transform_pdf 内部已包含栅格化，通常不需要额外调用此函数。
    """
    import fitz

    src = fitz.open(stream=pdf_data, filetype="pdf")
    out = fitz.open()
    zoom = dpi / 72.0
    matrix = fitz.Matrix(zoom, zoom)

    for page in src:
        pix = page.get_pixmap(matrix=matrix, alpha=False)
        img_bytes = pix.tobytes("png")
        new_page = out.new_page(width=page.rect.width, height=page.rect.height)
        new_page.insert_image(new_page.rect, stream=img_bytes)

    result = out.tobytes(deflate=True)
    src.close()
    out.close()
    return result
