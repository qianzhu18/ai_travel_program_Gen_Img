"""
IOPaint 服务启动器
从后端系统设置读取配置，自动启动 IOPaint HTTP 服务
"""
import subprocess
import sys


def get_config_from_backend():
    """从后端 API 读取 IOPaint 相关配置，失败时返回默认值"""
    defaults = {
        "model": "lama",
        "device": "cuda",
        "port": "8090",
    }
    try:
        import httpx
        resp = httpx.get("http://localhost:8000/api/settings/raw", timeout=3.0)
        if resp.status_code == 200:
            data = resp.json().get("data", {})
            defaults["model"] = data.get("iopaint_model", {}).get("value", "lama")
            gpu = data.get("gpu_acceleration", {}).get("value", "1")
            defaults["device"] = "cuda" if gpu == "1" else "cpu"
            defaults["port"] = data.get("iopaint_port", {}).get("value", "8090")
    except Exception:
        print("无法连接后端，使用默认配置")
    return defaults


def main():
    config = get_config_from_backend()
    cmd = [
        sys.executable, "-m", "iopaint", "start",
        f"--model={config['model']}",
        f"--device={config['device']}",
        f"--port={config['port']}",
    ]
    print(f"启动 IOPaint: {' '.join(cmd)}")
    print(f"  模型: {config['model']}")
    print(f"  设备: {config['device']}")
    print(f"  端口: {config['port']}")
    print()
    subprocess.run(cmd)


if __name__ == "__main__":
    main()
