"""
IPP 打印接口
通过 IPP 协议向 HP M427dw 发送打印任务
需要同时指定 media + media-type 才能让双面生效
"""
import struct
from scanner import get_session
from config import SCANNER_PORT, USE_HTTPS


def get_print_url(printer_ip):
    scheme = "https" if USE_HTTPS else "http"
    return f"{scheme}://{printer_ip}:{SCANNER_PORT}/ipp/print"


def build_ipp_request(printer_ip, filename="document.pdf", copies=1, sides="one-sided"):
    """
    构造 IPP Print-Job 请求的二进制数据头
    IPP version 2.0, operation Print-Job (0x0002)
    """
    data = struct.pack(">bbHI", 2, 0, 0x0002, 1)

    # Operation attributes tag
    data += b"\x01"
    data += _encode_attribute(0x47, "attributes-charset", "utf-8")
    data += _encode_attribute(0x48, "attributes-natural-language", "en")
    data += _encode_attribute(0x45, "printer-uri", f"ipp://{printer_ip}/ipp/print")
    data += _encode_attribute(0x42, "requesting-user-name", "web-print")
    data += _encode_attribute(0x42, "job-name", filename)
    data += _encode_attribute(0x49, "document-format", "application/pdf")

    # Job attributes tag
    data += b"\x02"
    data += _encode_integer(0x21, "copies", copies)
    data += _encode_attribute(0x44, "sides", sides)
    # 必须指定 media 和 media-type，否则打印机会忽略 sides 属性
    data += _encode_attribute(0x44, "media", "iso_a4_210x297mm")
    data += _encode_attribute(0x44, "media-type", "stationery")

    # End of attributes
    data += b"\x03"

    return data


def _encode_attribute(tag, name, value):
    """编码 IPP 文本/URI/keyword 属性"""
    name_bytes = name.encode("utf-8")
    value_bytes = value.encode("utf-8")
    return (
        struct.pack(">b", tag)
        + struct.pack(">H", len(name_bytes))
        + name_bytes
        + struct.pack(">H", len(value_bytes))
        + value_bytes
    )


def _encode_integer(tag, name, value):
    """编码 IPP 整数属性"""
    name_bytes = name.encode("utf-8")
    return (
        struct.pack(">b", tag)
        + struct.pack(">H", len(name_bytes))
        + name_bytes
        + struct.pack(">H", 4)
        + struct.pack(">I", value)
    )


def parse_ipp_response(data):
    """解析 IPP 响应，返回状态"""
    if len(data) < 8:
        return False, "响应数据太短"

    version_major, version_minor, status_code, request_id = struct.unpack(
        ">bbHI", data[:8]
    )

    if status_code == 0x0000:
        return True, "打印任务已提交"
    elif status_code == 0x0001:
        # successful-ok-ignored-or-substituted-attributes
        return True, "打印任务已提交（部分属性被忽略）"
    elif status_code <= 0x00FF:
        return True, f"打印任务已提交 (0x{status_code:04x})"
    else:
        return False, f"打印失败 (status: 0x{status_code:04x})"


def print_pdf(printer_ip, pdf_data, filename="document.pdf", copies=1, sides="one-sided"):
    """
    发送 PDF 到打印机（PDF 已经过旋转/缩放处理）
    返回 (success: bool, message: str)
    """
    session = get_session()
    url = get_print_url(printer_ip)

    ipp_header = build_ipp_request(
        printer_ip, filename=filename, copies=copies, sides=sides,
    )

    # IPP 请求 = header + PDF 数据
    payload = ipp_header + pdf_data

    headers = {"Content-Type": "application/ipp"}

    try:
        resp = session.post(url, data=payload, headers=headers, timeout=30)

        if resp.status_code == 200:
            return parse_ipp_response(resp.content)
        else:
            return False, f"HTTP 错误: {resp.status_code}"

    except Exception as e:
        return False, f"连接失败: {str(e)}"
