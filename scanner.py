"""
eSCL 扫描器接口
通过 HTTP 与 HP M427dw 通信
"""
import requests
import urllib3
import ssl
from requests.adapters import HTTPAdapter
from urllib3.util.ssl_ import create_urllib3_context
from config import SCANNER_PORT, USE_HTTPS

# 禁用 SSL 警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class LegacySSLAdapter(HTTPAdapter):
    """兼容旧版 TLS 的适配器（HP 打印机用的是旧协议）"""
    def init_poolmanager(self, *args, **kwargs):
        ctx = create_urllib3_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        ctx.set_ciphers("DEFAULT:@SECLEVEL=0")
        ctx.minimum_version = ssl.TLSVersion.TLSv1
        kwargs["ssl_context"] = ctx
        return super().init_poolmanager(*args, **kwargs)


def get_session():
    """创建兼容旧 SSL 的 requests session"""
    session = requests.Session()
    session.mount("https://", LegacySSLAdapter())
    session.verify = False
    return session


def get_base_url(scanner_ip):
    return f"{'https' if USE_HTTPS else 'http'}://{scanner_ip}:{SCANNER_PORT}/eSCL"


def get_scanner_status(scanner_ip):
    """获取打印机状态（先试 eSCL，再试 IPP）"""
    # 方式1：eSCL（带扫描功能的打印机）
    try:
        session = get_session()
        resp = session.get(f"{get_base_url(scanner_ip)}/ScannerStatus", timeout=5)
        if resp.status_code == 200:
            content = resp.text
            if "Idle" in content:
                return "idle"
            elif "Processing" in content:
                return "busy"
            else:
                return "idle"  # 能连上就算在线
    except Exception:
        pass

    # 方式2：IPP（纯打印机）
    try:
        session = get_session()
        scheme = "https" if USE_HTTPS else "http"
        resp = session.get(f"{scheme}://{scanner_ip}:{SCANNER_PORT}/ipp/print", timeout=5)
        # IPP 端点返回任何响应都算在线
        if resp.status_code in (200, 400, 401, 403, 405, 426):
            return "idle"
    except Exception:
        pass

    return "offline"


def scan(scanner_ip, dpi=300, color="RGB24"):
    """
    发起扫描请求（Platen 平板扫描）
    返回扫描结果（PDF 二进制数据）
    """
    base_url = get_base_url(scanner_ip)
    session = get_session()

    scan_settings = f"""<?xml version="1.0" encoding="UTF-8"?>
<scan:ScanSettings xmlns:scan="http://schemas.hp.com/imaging/escl/2011/05/03"
                   xmlns:pwg="http://www.pwg.org/schemas/2010/12/sm">
    <pwg:Version>2.5</pwg:Version>
    <scan:Intent>Document</scan:Intent>
    <pwg:InputSource>Platen</pwg:InputSource>
    <scan:ColorMode>{color}</scan:ColorMode>
    <scan:XResolution>{dpi}</scan:XResolution>
    <scan:YResolution>{dpi}</scan:YResolution>
    <scan:DocumentFormatExt>application/pdf</scan:DocumentFormatExt>
</scan:ScanSettings>"""

    headers = {"Content-Type": "text/xml"}
    resp = session.post(
        f"{base_url}/ScanJobs",
        data=scan_settings,
        headers=headers,
        timeout=10,
    )

    if resp.status_code == 201:
        job_url = resp.headers.get("Location")
        if not job_url:
            job_url = f"{base_url}/ScanJobs"

        result_url = f"{job_url}/NextDocument"
        result = session.get(result_url, timeout=120)

        if result.status_code == 200:
            return result.content
        else:
            raise Exception(f"获取扫描结果失败: {result.status_code}")
    elif resp.status_code == 409:
        raise Exception("打印机忙碌，请稍后重试（上一个扫描任务未完成）")
    else:
        raise Exception(f"扫描请求失败: {resp.status_code} - {resp.text[:200]}")
