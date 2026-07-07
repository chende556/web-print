"""
PDF 合并工具
将多个单页 PDF 合并为一个 PDF 文件
"""
from PyPDF2 import PdfMerger


def merge_pdfs(pdf_files):
    """
    合并多个 PDF 文件为一个
    返回合并后的 PDF 二进制数据
    """
    merger = PdfMerger()

    for pdf_file in pdf_files:
        merger.append(pdf_file)

    from io import BytesIO
    output = BytesIO()
    merger.write(output)
    merger.close()

    return output.getvalue()
