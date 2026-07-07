# HP 打印机配置
SCANNER_PORT = 443  # eSCL 通常是 443 或 80
USE_HTTPS = True  # M427dw 通常使用 HTTPS

# 扫描参数
DEFAULT_DPI = 300
DEFAULT_COLOR = "RGB24"

# Web 服务配置
UPLOAD_FOLDER = "/tmp/scans"

# 办公地点 → 打印机 IP 映射
PRINTER_LOCATIONS = {
    "办公室A": "10.0.0.1",
    "办公室B": "10.0.0.2",
}
