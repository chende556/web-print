"""
PDF 变换工具
对 PDF 进行旋转和缩放，输出固定为标准 A4 页面

使用 PyMuPDF (fitz) 直接渲染+变换，避免 PyPDF2 的 /Rotate 属性
与实际内容坐标系不一致导致的各种偏移/裁切/空白 bug。

设计原则：
- orientation 决定 A4 画布本身是竖放还是横放
- 如果原始内容的长宽比跟选择的画布方向不匹配，自动旋转 90 度后缩放居中
- scaling 在此基础上再整体缩小
"""
from io import BytesIO

# A4 尺寸（点，1 point = 1/72 inch）
A4_WIDTH = 595.28   # 210mm
A4_HEIGHT = 841.89  # 297mm


def transform_pdf(pdf_data, orientation="portrait", scaling=100):
    """
    对 PDF 进行旋转和缩放变换，输出固定为标准 A4 页面。
    使用 PyMuPDF 渲染方式，完全绕开 PyPDF2 的坐标系问题。

    orientation: "portrait"（A4 竖放）或 "landscape"（A4 横放）
    scaling: 百分比数字，100 = 内容尽量占满 A4 画布（等比缩放）

    返回变换后的 PDF 二进制数据
    """
    import fitz

    src = fitz.open(stream=pdf_data, filetype="pdf")
    out = fitz.open()

    scale_factor = scaling / 100.0

    if orientation == "landscape":
        canvas_width, canvas_height = A4_HEIGHT, A4_WIDTH
    else:
        canvas_width, canvas_height = A4_WIDTH, A4_HEIGHT

    for page in src:
        orig_width = page.rect.width
        orig_height = page.rect.height

        # 不做旋转，只是把内容等比缩放居中放进目标画布
        # 选纵向 = A4 竖放纸，选横向 = A4 横放纸，内容保持原始阅读方向不旋转
        fit_scale = min(canvas_width / orig_width, canvas_height / orig_height)
        final_scale = fit_scale * scale_factor

        # 用高分辨率渲染原始页面为图片（不旋转）
        dpi = 200
        zoom = dpi / 72.0
        matrix = fitz.Matrix(zoom, zoom)

        pix = page.get_pixmap(matrix=matrix, alpha=False)
        img_bytes = pix.tobytes("png")

        # 创建目标 A4 页面
        new_page = out.new_page(width=canvas_width, height=canvas_height)

        # 图片在画布上的放置区域（居中，等比缩放）
        img_width_pt = pix.width / zoom
        img_height_pt = pix.height / zoom

        place_scale = min(canvas_width / img_width_pt, canvas_height / img_height_pt) * scale_factor
        place_width = img_width_pt * place_scale
        place_height = img_height_pt * place_scale

        # 位置策略：100% 时居中，缩小时靠顶对齐（跟系统打印对话框行为一致）
        x0 = (canvas_width - place_width) / 2
        if scale_factor < 1.0:
            y0 = 0  # 缩小时靠顶
        else:
            y0 = (canvas_height - place_height) / 2  # 100% 时居中
        x1 = x0 + place_width
        y1 = y0 + place_height

        new_page.insert_image(fitz.Rect(x0, y0, x1, y1), stream=img_bytes)

    result = out.tobytes(deflate=True)
    src.close()
    out.close()
    return result


def rasterize_pdf(pdf_data, dpi=200):
    """
    将 PDF 每一页渲染为图片，再重新包装成 PDF。
    用于绕过打印机对某些字体/图层解析不完整导致的文字缺失问题。

    注意：如果之前已经调用了 transform_pdf（且 scaling != 100 或 orientation != portrait），
    那次调用内部已经完成了栅格化（因为 transform_pdf 现在基于渲染实现），
    所以 rasterize_pdf 再处理一次实际上是"对已栅格化的图片再栅格化一次"——
    效果等同，但会多一次无意义的编解码。
    调用方可以通过检查是否已被 transform_pdf 处理过来决定是否跳过。

    dpi: 渲染分辨率
    返回：栅格化后的 PDF 二进制数据
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
