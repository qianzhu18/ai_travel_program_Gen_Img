"""
安全工具函数
- 文件名清洗
- 路径穿越防护
- SSRF 防护（URL 校验）
"""
import re
import ipaddress
import logging
from pathlib import Path
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# 允许的文件名字符：字母、数字、中文、下划线、连字符、点
_SAFE_FILENAME_RE = re.compile(r"[^\w\u4e00-\u9fff.\-]")


def sanitize_filename(name: str) -> str:
    """
    清洗文件名：
    - 去除路径分隔符
    - 替换特殊字符为下划线
    - 限制长度 200 字符
    - 空结果返回 'unnamed'
    """
    # 只取最后一段（防止 ../../etc/passwd 之类）
    name = Path(name).name
    # 替换不安全字符
    name = _SAFE_FILENAME_RE.sub("_", name)
    # 去除连续下划线
    name = re.sub(r"_{2,}", "_", name).strip("_")
    # 限制长度
    if len(name) > 200:
        stem, dot, ext = name.rpartition(".")
        if dot:
            name = stem[:195] + "." + ext
        else:
            name = name[:200]
    return name or "unnamed"


def safe_resolve(user_path: str, allowed_root: Path) -> Path:
    """
    安全解析用户提供的路径，确保结果在 allowed_root 下。
    防止路径穿越攻击。
    """
    resolved = Path(user_path).resolve()
    root = allowed_root.resolve()
    if not str(resolved).startswith(str(root)):
        raise ValueError(f"路径不在允许范围内: {user_path}")
    return resolved


def validate_export_dir(export_dir: str) -> Path:
    """
    校验导出目录：
    - 不允许 .. 路径穿越
    - 不允许指向系统关键目录
    """
    if ".." in export_dir:
        raise ValueError("导出路径不允许包含 '..'")

    # 禁止写入系统关键目录（先检查用户输入路径本身，再检查 resolve 结果）
    _BLOCKED_PREFIXES = ("/etc", "/usr", "/bin", "/sbin", "/boot", "/proc", "/sys", "/dev")
    raw_str = str(Path(export_dir))
    for prefix in _BLOCKED_PREFIXES:
        if raw_str.startswith(prefix):
            raise ValueError(f"不允许导出到系统目录: {prefix}")

    resolved = Path(export_dir).resolve()
    resolved_str = str(resolved)
    for prefix in _BLOCKED_PREFIXES:
        if resolved_str.startswith(prefix):
            raise ValueError(f"不允许导出到系统目录: {prefix}")

    return resolved


# SSRF 防护：禁止访问的内网 IP 段
_PRIVATE_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),  # link-local
    ipaddress.ip_network("::1/128"),          # IPv6 loopback
    ipaddress.ip_network("fc00::/7"),         # IPv6 private
    ipaddress.ip_network("fe80::/10"),        # IPv6 link-local
]

# 允许的 URL scheme
_ALLOWED_SCHEMES = {"http", "https"}


def validate_url(url: str) -> str:
    """
    校验 URL 安全性，防止 SSRF：
    - 只允许 http/https
    - 禁止内网 IP 地址
    - 禁止 localhost
    """
    parsed = urlparse(url)

    if parsed.scheme not in _ALLOWED_SCHEMES:
        raise ValueError(f"不支持的协议: {parsed.scheme}，仅允许 http/https")

    hostname = parsed.hostname
    if not hostname:
        raise ValueError("URL 缺少主机名")

    # 检查 localhost 变体
    _LOCALHOST_NAMES = {"localhost", "localhost.localdomain", "0.0.0.0"}
    if hostname.lower() in _LOCALHOST_NAMES:
        raise ValueError("不允许访问本地地址")

    # 尝试解析为 IP 并检查是否为内网
    try:
        addr = ipaddress.ip_address(hostname)
        for network in _PRIVATE_NETWORKS:
            if addr in network:
                raise ValueError(f"不允许访问内网地址: {hostname}")
    except ValueError as e:
        if "不允许" in str(e):
            raise
        # 不是 IP 格式，是域名 — 这里不做 DNS 解析（本地工具可接受）
        pass

    return url
