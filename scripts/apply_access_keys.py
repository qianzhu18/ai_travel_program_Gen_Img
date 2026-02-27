#!/usr/bin/env python3
"""
从 AccessKey 文本文件中提取密钥并写入 .env。

默认读取:
- 可行性分析/AccessKey.txt

支持写入:
- APIYI_API_KEY
- BAILIAN_API_KEY
- VOLC_ACCESS_KEY_ID
- VOLC_SECRET_ACCESS_KEY
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Dict, List, Tuple


SK_RE = re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b")
AK_RE = re.compile(r"\bAK[0-9A-Za-z]{12,}\b")
VOLC_SK_RE = re.compile(r"(?i)\bsecretaccesskey\s*[:：]\s*([^\s#]+)")


def mask_secret(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 10:
        return "*" * len(value)
    return f"{value[:6]}...{value[-4:]}"


def parse_access_keys(text: str) -> Dict[str, str]:
    lines = text.splitlines()

    volc_ak = ""
    volc_sk = ""
    sk_candidates: List[Tuple[str, str]] = []

    for raw in lines:
        line = raw.strip()
        if not line:
            continue

        lower = line.lower()

        if not volc_ak:
            m_ak = AK_RE.search(line)
            if m_ak:
                volc_ak = m_ak.group(0)

        if not volc_sk:
            m_vsk = VOLC_SK_RE.search(line)
            if m_vsk:
                volc_sk = m_vsk.group(1).strip()

        for sk in SK_RE.findall(line):
            sk_candidates.append((sk, lower))

    # 规则优先级：
    # 1) APIYI: 明确标注 apiyi 的 sk；否则使用“非 kimi/kimmi”的第一个；否则最后一个 sk。
    # 2) BAILIAN: 明确标注 bailian/dashscope 的 sk；否则使用 kimi/kimmi 的 sk。
    apiyi = ""
    bailian = ""

    for key, lower in sk_candidates:
        if "apiyi" in lower:
            apiyi = key
            break

    for key, lower in sk_candidates:
        if "bailian" in lower or "dashscope" in lower or "百炼" in lower:
            bailian = key
            break

    if not bailian:
        for key, lower in sk_candidates:
            if "kimi" in lower or "kimmi" in lower or "moonshot" in lower:
                bailian = key
                break

    if not apiyi:
        for key, lower in sk_candidates:
            if "kimi" not in lower and "kimmi" not in lower:
                apiyi = key
                break

    if not apiyi and sk_candidates:
        apiyi = sk_candidates[-1][0]

    return {
        "APIYI_API_KEY": apiyi,
        "BAILIAN_API_KEY": bailian,
        "VOLC_ACCESS_KEY_ID": volc_ak,
        "VOLC_SECRET_ACCESS_KEY": volc_sk,
    }


def read_env(path: Path) -> Dict[str, str]:
    env: Dict[str, str] = {}
    if not path.exists():
        return env
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def upsert_env_lines(lines: List[str], updates: Dict[str, str]) -> List[str]:
    out = list(lines)
    for key, value in updates.items():
        if not value:
            continue
        pattern = re.compile(rf"^\s*{re.escape(key)}\s*=")
        replaced = False
        for i, raw in enumerate(out):
            if pattern.match(raw):
                out[i] = f"{key}={value}"
                replaced = True
                break
        if not replaced:
            out.append(f"{key}={value}")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply keys from AccessKey.txt to .env")
    parser.add_argument(
        "--access-key-file",
        default="可行性分析/AccessKey.txt",
        help="Path to AccessKey text file",
    )
    parser.add_argument("--env-file", default=".env", help="Path to .env file")
    parser.add_argument("--env-example", default=".env.example", help="Path to .env.example")
    parser.add_argument("--quiet", action="store_true", help="Reduce output")
    args = parser.parse_args()

    access_key_path = Path(args.access_key_file)
    env_path = Path(args.env_file)
    env_example = Path(args.env_example)

    if not env_path.exists() and env_example.exists():
        env_path.write_text(
            env_example.read_text(encoding="utf-8", errors="ignore"),
            encoding="utf-8",
        )
        if not args.quiet:
            print(f"[INFO] Created {env_path} from {env_example}")

    if not access_key_path.exists():
        if not args.quiet:
            print(f"[WARN] Access key file not found: {access_key_path}")
        return 0

    text = access_key_path.read_text(encoding="utf-8", errors="ignore")
    updates = parse_access_keys(text)
    updates = {k: v for k, v in updates.items() if v}

    if not updates:
        if not args.quiet:
            print("[WARN] No recognizable keys found in AccessKey file.")
        return 0

    original_lines = []
    if env_path.exists():
        original_lines = env_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    new_lines = upsert_env_lines(original_lines, updates)
    env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")

    if not args.quiet:
        print("[INFO] Updated .env keys from AccessKey file:")
        for key in sorted(updates.keys()):
            print(f"  - {key}={mask_secret(updates[key])}")

        env_now = read_env(env_path)
        missing = [k for k in ("APIYI_API_KEY",) if not env_now.get(k)]
        if missing:
            print(f"[WARN] Required key still missing: {', '.join(missing)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
