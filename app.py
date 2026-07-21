"""
HP 扫描仪 Web 服务
"""
from flask import Flask, render_template, request, send_file, jsonify
import os
import uuid
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime
from io import BytesIO

from scanner import scan, get_scanner_status
from printer import print_pdf, get_printer_info, get_job_status
from pdf_merge import merge_pdfs
from converter import to_pdf
from pdf_transform import transform_pdf
from config import UPLOAD_FOLDER, PRINTER_LOCATIONS, LOG_FILE
from PyPDF2 import PdfReader, PdfWriter

app = Flask(__name__)
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

# 日志配置
logger = logging.getLogger("webprint")
logger.setLevel(logging.INFO)
handler = RotatingFileHandler(LOG_FILE, maxBytes=5*1024*1024, backupCount=3, encoding="utf-8")
handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
logger.addHandler(handler)

# 存储临时扫描页面
scan_sessions = {}


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/locations")
def locations():
    """获取办公地点列表"""
    return jsonify(PRINTER_LOCATIONS)


@app.route("/api/status", methods=["POST"])
def status():
    """获取扫描仪状态"""
    data = request.json or {}
    scanner_ip = data.get("scanner_ip", "")
    if not scanner_ip:
        return jsonify({"status": "error", "message": "请输入打印机 IP"}), 400

    s = get_scanner_status(scanner_ip)
    return jsonify({"status": s})


@app.route("/api/printer-info", methods=["POST"])
def printer_info():
    """获取打印机碳粉/墨盒信息"""
    data = request.json or {}
    printer_ip = data.get("printer_ip", "")
    if not printer_ip:
        return jsonify({"error": "请输入打印机 IP"}), 400

    info = get_printer_info(printer_ip)
    if info is None:
        return jsonify({"error": "无法获取打印机信息"}), 500
    return jsonify(info)


@app.route("/api/job-status", methods=["POST"])
def job_status():
    """查询打印任务状态"""
    data = request.json or {}
    printer_ip = data.get("printer_ip", "")
    job_id = data.get("job_id", 0)
    if not printer_ip or not job_id:
        return jsonify({"error": "缺少参数"}), 400

    status = get_job_status(printer_ip, int(job_id))
    if status is None:
        return jsonify({"state": "unknown"})
    return jsonify(status)


@app.route("/api/scan", methods=["POST"])
def do_scan():
    """执行一次扫描"""
    data = request.json or {}
    scanner_ip = data.get("scanner_ip", "")
    session_id = data.get("session_id")
    dpi = data.get("dpi", 300)
    color = data.get("color", "RGB24")

    if not scanner_ip:
        return jsonify({"success": False, "error": "请输入打印机 IP"}), 400

    if not session_id:
        session_id = str(uuid.uuid4())

    try:
        pdf_data = scan(scanner_ip, dpi=dpi, color=color)

        if session_id not in scan_sessions:
            scan_sessions[session_id] = []

        page_num = len(scan_sessions[session_id]) + 1
        filename = f"{session_id}_page{page_num}.pdf"
        filepath = os.path.join(UPLOAD_FOLDER, filename)

        with open(filepath, "wb") as f:
            f.write(pdf_data)

        scan_sessions[session_id].append(filepath)

        client_ip = request.headers.get("X-Real-IP", request.remote_addr)
        logger.info(f"扫描成功 | 客户端={client_ip} | 打印机={scanner_ip} | 第{page_num}页 | DPI={dpi}")

        return jsonify({
            "success": True,
            "session_id": session_id,
            "page_count": len(scan_sessions[session_id]),
            "message": f"第 {page_num} 页扫描完成",
        })

    except Exception as e:
        client_ip = request.headers.get("X-Real-IP", request.remote_addr)
        logger.error(f"扫描失败 | 客户端={client_ip} | 打印机={scanner_ip} | 错误={str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/download", methods=["POST"])
def download():
    """合并所有扫描页并下载为一个 PDF"""
    data = request.json or {}
    session_id = data.get("session_id")

    if not session_id or session_id not in scan_sessions:
        return jsonify({"error": "无效的会话"}), 400

    pages = scan_sessions[session_id]
    if not pages:
        return jsonify({"error": "没有扫描页面"}), 400

    merged_pdf = merge_pdfs(pages)

    for f in pages:
        if os.path.exists(f):
            os.remove(f)
    del scan_sessions[session_id]

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return send_file(
        BytesIO(merged_pdf),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"scan_{timestamp}.pdf",
    )


@app.route("/api/cancel", methods=["POST"])
def cancel():
    """取消当前扫描会话"""
    data = request.json or {}
    session_id = data.get("session_id")

    if session_id and session_id in scan_sessions:
        for f in scan_sessions[session_id]:
            if os.path.exists(f):
                os.remove(f)
        del scan_sessions[session_id]

    return jsonify({"success": True})


@app.route("/api/preview", methods=["POST"])
def preview():
    """上传文件，转换为 PDF 后按方向/缩放参数渲染，返回最终打印效果预览"""
    file = request.files.get("file")
    if not file:
        return jsonify({"error": "无文件"}), 400

    orientation = request.form.get("orientation", "portrait")
    scaling = int(request.form.get("scaling", 100))

    try:
        file_data = file.read()
        pdf_data, error = to_pdf(file_data, file.filename)
        if error:
            return jsonify({"error": error}), 400

        # 应用方向和缩放（输出 A4 画布 + 栅格化）
        pdf_data = transform_pdf(pdf_data, orientation=orientation, scaling=scaling)

        reader = PdfReader(BytesIO(pdf_data))
        pages = len(reader.pages)
        response = send_file(
            BytesIO(pdf_data),
            mimetype="application/pdf",
        )
        response.headers["X-Page-Count"] = str(pages)
        return response
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/pdf-info", methods=["POST"])
def pdf_info():
    """获取 PDF 页数（转换后）"""
    file = request.files.get("file")
    if not file:
        return jsonify({"error": "无文件"}), 400
    try:
        file_data = file.read()
        pdf_data, error = to_pdf(file_data, file.filename)
        if error:
            return jsonify({"error": error}), 400
        reader = PdfReader(BytesIO(pdf_data))
        return jsonify({"pages": len(reader.pages)})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


def parse_page_ranges(pages_str, total_pages):
    """
    解析页码范围字符串，返回页码列表（0-indexed）
    支持格式：1-3, 5, 8-10
    """
    pages = set()
    parts = pages_str.replace("，", ",").split(",")
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start, end = part.split("-", 1)
            start = max(1, int(start.strip()))
            end = min(total_pages, int(end.strip()))
            for i in range(start, end + 1):
                pages.add(i - 1)  # 转为 0-indexed
        else:
            p = int(part)
            if 1 <= p <= total_pages:
                pages.add(p - 1)
    return sorted(pages)


@app.route("/api/print", methods=["POST"])
def do_print():
    """上传 PDF 并打印"""
    printer_ip = request.form.get("printer_ip", "").strip()
    if not printer_ip:
        return jsonify({"success": False, "error": "请输入打印机 IP"}), 400

    file = request.files.get("file")
    if not file:
        return jsonify({"success": False, "error": "请选择文件"}), 400

    ALLOWED_EXT = {".pdf", ".jpg", ".jpeg", ".png", ".docx", ".doc", ".xlsx", ".xls", ".pptx", ".ppt", ".csv"}
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXT:
        return jsonify({"success": False, "error": f"不支持的文件格式: {ext}"}), 400

    copies = int(request.form.get("copies", 1))
    duplex = request.form.get("duplex", "one-sided")
    orientation = request.form.get("orientation", "portrait")
    scaling = int(request.form.get("scaling", 100))
    color_mode = request.form.get("color_mode", "color")
    pages_str = request.form.get("pages", "").strip()

    try:
        file_data = file.read()

        # 转换为 PDF
        pdf_data, error = to_pdf(file_data, file.filename)
        if error:
            logger.error(f"转换失败 | 文件={file.filename} | 打印机={printer_ip} | 错误={error}")
            return jsonify({"success": False, "error": error}), 400

        # 如果指定了页码范围，提取对应页
        if pages_str:
            reader = PdfReader(BytesIO(pdf_data))
            total_pages = len(reader.pages)
            selected = parse_page_ranges(pages_str, total_pages)

            if not selected:
                return jsonify({"success": False, "error": "无效的页码范围"}), 400

            writer = PdfWriter()
            for idx in selected:
                writer.add_page(reader.pages[idx])

            output = BytesIO()
            writer.write(output)
            pdf_data = output.getvalue()

        # 应用旋转和缩放（内部已栅格化为图片版 PDF，同时解决文字缺失问题）
        pdf_data = transform_pdf(pdf_data, orientation=orientation, scaling=scaling)

        # 获取最终页数
        final_reader = PdfReader(BytesIO(pdf_data))
        final_pages = len(final_reader.pages)

        success, message, job_id = print_pdf(
            printer_ip,
            pdf_data,
            filename=file.filename,
            copies=copies,
            sides=duplex,
            color_mode=color_mode,
        )

        client_ip = request.headers.get("X-Real-IP", request.remote_addr)
        logger.info(
            f"打印{'成功' if success else '失败'} | "
            f"客户端={client_ip} | 打印机={printer_ip} | "
            f"文件={file.filename} | 页数={final_pages} | 份数={copies} | "
            f"双面={duplex} | 色彩={color_mode} | "
            f"job_id={job_id} | 消息={message}"
        )

        return jsonify({"success": success, "message": message, "job_id": job_id})
    except Exception as e:
        client_ip = request.headers.get("X-Real-IP", request.remote_addr)
        logger.error(f"打印异常 | 客户端={client_ip} | 打印机={printer_ip} | 文件={file.filename} | 错误={str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
