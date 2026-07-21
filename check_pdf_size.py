"""
查看 PDF 文件的页面尺寸
用法：python check_pdf_size.py 文件.pdf
"""
import sys
import fitz  # PyMuPDF

if len(sys.argv) < 2:
    print("用法：python check_pdf_size.py 文件.pdf")
    sys.exit(1)

path = sys.argv[1]
doc = fitz.open(path)

# A4 = 595.28 x 841.89 点（pt），1 pt = 1/72 英寸
A4_WIDTH, A4_HEIGHT = 595.28, 841.89

for i, page in enumerate(doc):
    rect = page.rect
    w_pt, h_pt = rect.width, rect.height
    w_mm, h_mm = w_pt / 72 * 25.4, h_pt / 72 * 25.4

    is_a4 = abs(w_pt - A4_WIDTH) < 2 and abs(h_pt - A4_HEIGHT) < 2

    rotate = page.rotation  # PyMuPDF 里的 /Rotate 值

    print(f"第 {i+1} 页：")
    print(f"  尺寸（点）：{w_pt:.1f} x {h_pt:.1f} pt")
    print(f"  尺寸（毫米）：{w_mm:.1f} x {h_mm:.1f} mm")
    print(f"  是否标准 A4：{'是' if is_a4 else '否'}")
    print(f"  mediabox 原点：({page.mediabox.x0}, {page.mediabox.y0})")
    print(f"  /Rotate 标记：{rotate} 度")

doc.close()
