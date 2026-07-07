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


def build_ipp_request(printer_ip, filename="document.pdf", copies=1, sides="one-sided", color_mode="color"):
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
    # 彩色/黑白
    data += _encode_attribute(0x44, "print-color-mode", color_mode)

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
    """解析 IPP 响应，返回状态和 job-id"""
    if len(data) < 8:
        return False, "响应数据太短", None

    version_major, version_minor, status_code, request_id = struct.unpack(
        ">bbHI", data[:8]
    )

    # 尝试提取 job-id
    job_id = None
    pos = 8
    while pos < len(data):
        tag = data[pos]
        pos += 1
        if tag == 0x03:
            break
        if tag in (0x01, 0x02, 0x04, 0x05):
            continue
        if pos + 2 > len(data):
            break
        name_len = struct.unpack(">H", data[pos:pos+2])[0]
        pos += 2
        name = data[pos:pos+name_len].decode("utf-8", errors="ignore") if name_len > 0 else ""
        pos += name_len
        if pos + 2 > len(data):
            break
        value_len = struct.unpack(">H", data[pos:pos+2])[0]
        pos += 2
        value_bytes = data[pos:pos+value_len]
        pos += value_len

        if name == "job-id" and tag == 0x21 and value_len == 4:
            job_id = struct.unpack(">I", value_bytes)[0]

    if status_code == 0x0000:
        return True, "打印任务已提交", job_id
    elif status_code == 0x0001:
        return True, "打印任务已提交（部分属性被忽略）", job_id
    elif status_code <= 0x00FF:
        return True, f"打印任务已提交 (0x{status_code:04x})", job_id
    else:
        return False, f"打印失败 (status: 0x{status_code:04x})", None


def print_pdf(printer_ip, pdf_data, filename="document.pdf", copies=1, sides="one-sided", color_mode="color"):
    """
    发送 PDF 到打印机（PDF 已经过旋转/缩放处理）
    返回 (success: bool, message: str)
    """
    session = get_session()
    url = get_print_url(printer_ip)

    ipp_header = build_ipp_request(
        printer_ip, filename=filename, copies=copies, sides=sides, color_mode=color_mode,
    )

    # IPP 请求 = header + PDF 数据
    payload = ipp_header + pdf_data

    headers = {"Content-Type": "application/ipp"}

    try:
        resp = session.post(url, data=payload, headers=headers, timeout=30)

        if resp.status_code == 200:
            success, message, job_id = parse_ipp_response(resp.content)
            return success, message, job_id
        else:
            return False, f"HTTP 错误: {resp.status_code}", None

    except Exception as e:
        return False, f"连接失败: {str(e)}", None


def get_printer_info(printer_ip):
    """
    查询打印机碳粉/墨盒信息
    通过 IPP Get-Printer-Attributes 获取 marker-names 和 marker-levels
    返回列表 [{"name": "Black", "level": 45}, ...]
    """
    session = get_session()
    scheme = "https" if USE_HTTPS else "http"
    url = f"{scheme}://{printer_ip}:{SCANNER_PORT}/ipp/print"

    # 构造 Get-Printer-Attributes 请求
    data = struct.pack(">bbHI", 2, 0, 0x000B, 1)  # IPP 2.0, Get-Printer-Attributes

    # Operation attributes
    data += b"\x01"
    data += _encode_attribute(0x47, "attributes-charset", "utf-8")
    data += _encode_attribute(0x48, "attributes-natural-language", "en")
    data += _encode_attribute(0x45, "printer-uri", f"ipp://{printer_ip}/ipp/print")

    # 请求特定属性
    data += _encode_attribute(0x44, "requested-attributes", "marker-names")
    # 追加属性（name 为空表示同一属性的额外值）
    data += _encode_attribute(0x44, "", "marker-levels")
    data += _encode_attribute(0x44, "", "marker-colors")
    data += _encode_attribute(0x44, "", "printer-state")
    data += _encode_attribute(0x44, "", "printer-state-reasons")

    data += b"\x03"  # end

    headers = {"Content-Type": "application/ipp"}

    try:
        resp = session.post(url, data=data, headers=headers, timeout=10)
        if resp.status_code != 200:
            return None

        return _parse_printer_attributes(resp.content)
    except Exception:
        return None


def _parse_printer_attributes(data):
    """
    解析 IPP Get-Printer-Attributes 响应，提取碳粉信息
    简单解析：从原始字节中搜索 marker 相关文本
    """
    result = {"markers": [], "state": "unknown"}

    # 转为文本搜索（IPP 二进制里属性值是明文）
    text = data.decode("latin-1", errors="ignore")

    # 提取 marker-names（逗号分隔的名称列表）
    names = []
    levels = []

    # 解析属性值 - 搜索关键字
    # marker-names 是 1setOf nameWithoutLanguage
    # marker-levels 是 1setOf integer

    # 简易方式：用二进制解析
    pos = 8  # 跳过 header
    current_attr = ""
    marker_names_list = []
    marker_levels_list = []

    while pos < len(data):
        if pos >= len(data):
            break

        tag = data[pos]
        pos += 1

        # Delimiter tags
        if tag in (0x01, 0x02, 0x04, 0x05):
            continue
        if tag == 0x03:  # end-of-attributes
            break

        # Value tag
        if pos + 2 > len(data):
            break
        name_len = struct.unpack(">H", data[pos:pos+2])[0]
        pos += 2

        name = ""
        if name_len > 0:
            name = data[pos:pos+name_len].decode("utf-8", errors="ignore")
            current_attr = name
        pos += name_len

        if pos + 2 > len(data):
            break
        value_len = struct.unpack(">H", data[pos:pos+2])[0]
        pos += 2

        value_bytes = data[pos:pos+value_len]
        pos += value_len

        # 收集属性
        if current_attr == "marker-names" and tag in (0x41, 0x42, 0x44, 0x48):
            marker_names_list.append(value_bytes.decode("utf-8", errors="ignore"))
        elif current_attr == "marker-levels" and tag == 0x21:
            if value_len == 4:
                marker_levels_list.append(struct.unpack(">I", value_bytes)[0])
            elif value_len == 1:
                marker_levels_list.append(value_bytes[0])
        elif current_attr == "printer-state" and tag == 0x23:
            if value_len == 4:
                state_val = struct.unpack(">I", value_bytes)[0]
                state_map = {3: "idle", 4: "processing", 5: "stopped"}
                result["state"] = state_map.get(state_val, "unknown")

    # 组合结果
    for i in range(min(len(marker_names_list), len(marker_levels_list))):
        result["markers"].append({
            "name": marker_names_list[i],
            "level": marker_levels_list[i],
        })

    # 如果只有 names 没有 levels
    if marker_names_list and not marker_levels_list:
        for name in marker_names_list:
            result["markers"].append({"name": name, "level": -1})

    return result


def get_job_status(printer_ip, job_id):
    """
    查询打印任务状态
    返回 {"state": "processing", "state_reasons": "none"}
    """
    session = get_session()
    scheme = "https" if USE_HTTPS else "http"
    url = f"{scheme}://{printer_ip}:{SCANNER_PORT}/ipp/print"

    # Get-Job-Attributes (0x0009)
    data = struct.pack(">bbHI", 2, 0, 0x0009, 1)

    data += b"\x01"
    data += _encode_attribute(0x47, "attributes-charset", "utf-8")
    data += _encode_attribute(0x48, "attributes-natural-language", "en")
    data += _encode_attribute(0x45, "printer-uri", f"ipp://{printer_ip}/ipp/print")
    data += _encode_integer(0x21, "job-id", job_id)
    data += _encode_attribute(0x44, "requested-attributes", "job-state")
    data += _encode_attribute(0x44, "", "job-state-reasons")

    data += b"\x03"

    headers = {"Content-Type": "application/ipp"}

    try:
        resp = session.post(url, data=data, headers=headers, timeout=10)
        if resp.status_code != 200:
            return None

        # 解析 job-state
        pos = 8
        state = "unknown"
        while pos < len(resp.content):
            tag = resp.content[pos]
            pos += 1
            if tag == 0x03:
                break
            if tag in (0x01, 0x02, 0x04, 0x05):
                continue
            if pos + 2 > len(resp.content):
                break
            name_len = struct.unpack(">H", resp.content[pos:pos+2])[0]
            pos += 2
            name = resp.content[pos:pos+name_len].decode("utf-8", errors="ignore") if name_len > 0 else ""
            pos += name_len
            if pos + 2 > len(resp.content):
                break
            value_len = struct.unpack(">H", resp.content[pos:pos+2])[0]
            pos += 2
            value_bytes = resp.content[pos:pos+value_len]
            pos += value_len

            if name == "job-state" and tag == 0x23 and value_len == 4:
                state_val = struct.unpack(">I", value_bytes)[0]
                # 3=pending, 4=pending-held, 5=processing, 6=processing-stopped,
                # 7=canceled, 8=aborted, 9=completed
                state_map = {
                    3: "pending", 4: "pending-held", 5: "processing",
                    6: "processing-stopped", 7: "canceled", 8: "aborted", 9: "completed"
                }
                state = state_map.get(state_val, f"unknown({state_val})")

        return {"state": state}
    except Exception:
        return None
