#!/usr/bin/env python3
"""
直接测试 API 易平台的图生图接口
用于验证参数格式是否正确
"""
import asyncio
import base64
import cv2
import httpx
import sys
from pathlib import Path

# 从配置加载 API Key
sys.path.insert(0, str(Path(__file__).parent.parent))
from app.core.config import settings


def create_test_image(path: str, color: tuple = (0, 0, 255)):
    """创建测试图片"""
    import numpy as np
    img = np.zeros((1024, 576, 3), dtype=np.uint8)
    img[:] = color
    # 添加特征便于识别
    cv2.rectangle(img, (100, 100), (476, 300), (255, 255, 255), -1)
    cv2.putText(img, "REF", (200, 250), cv2.FONT_HERSHEY_SIMPLEX, 3, (0, 0, 0), 5)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(path, img)
    return path


def image_to_base64(path: str) -> str:
    """图片转 Base64"""
    img = cv2.imread(path)
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 85])
    return base64.b64encode(buf.tobytes()).decode("utf-8") if ok else ""


async def test_text_only(api_key: str):
    """测试纯文生图"""
    print("\n" + "="*60)
    print("测试 1: 纯文生图（不带参考图）")
    print("="*60)

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": "seedream-4-5-251128",
        "prompt": "一个穿着蓝色连衣裙的少女，站在红色背景前",
        "size": "1440x2560",
        "n": 1,
    }

    print(f"请求参数: {payload}")

    try:
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{settings.APIYI_API_URL}/v1/images/generations",
                json=payload,
                headers=headers,
            )

            print(f"响应状态: {resp.status_code}")
            if resp.status_code == 200:
                data = resp.json()
                print(f"响应数据结构: {list(data.keys())}")
                return True
            else:
                print(f"错误响应: {resp.text[:300]}")
                return False
    except Exception as e:
        print(f"异常: {e}")
        return False


async def test_img2img_format1(api_key: str, ref_b64: str):
    """测试图生图格式 1: image + reference_strength"""
    print("\n" + "="*60)
    print("测试 2: 图生图格式 1 (image + reference_strength)")
    print("="*60)

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": "seedream-4-5-251128",
        "prompt": "一个穿着白色连衣裙的少女",
        "size": "1440x2560",
        "n": 1,
        "image": f"data:image/jpeg;base64,{ref_b64}",
        "reference_strength": 0.92,
    }

    print(f"请求参数: model={payload['model']}, has_image=True, reference_strength={payload['reference_strength']}")

    try:
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{settings.APIYI_API_URL}/v1/images/generations",
                json=payload,
                headers=headers,
            )

            print(f"响应状态: {resp.status_code}")
            if resp.status_code == 200:
                data = resp.json()
                print(f"✓ 成功！响应数据结构: {list(data.keys())}")

                # 保存结果图片
                results = data.get("output", {}).get("results", []) or data.get("data", [])
                if results and isinstance(results[0], dict):
                    b64 = results[0].get("b64_image") or results[0].get("b64_json", "")
                    if b64:
                        img_data = base64.b64decode(b64)
                        output_path = "/tmp/test_apiyi_format1.jpg"
                        Path(output_path).write_bytes(img_data)
                        print(f"✓ 图片已保存: {output_path}")
                return True
            else:
                print(f"✗ 错误响应: {resp.text[:500]}")
                return False
    except Exception as e:
        print(f"✗ 异常: {e}")
        return False


async def test_img2img_format2(api_key: str, ref_b64: str):
    """测试图生图格式 2: 使用 input_image 参数"""
    print("\n" + "="*60)
    print("测试 3: 图生图格式 2 (input_image 参数)")
    print("="*60)

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": "seedream-4-5-251128",
        "prompt": "一个穿着白色连衣裙的少女",
        "size": "1440x2560",
        "n": 1,
        "input_image": f"data:image/jpeg;base64,{ref_b64}",
        "reference_strength": 0.92,
    }

    print(f"请求参数: model={payload['model']}, has_input_image=True")

    try:
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{settings.APIYI_API_URL}/v1/images/generations",
                json=payload,
                headers=headers,
            )

            print(f"响应状态: {resp.status_code}")
            if resp.status_code == 200:
                data = resp.json()
                print(f"✓ 成功！响应数据结构: {list(data.keys())}")

                # 保存结果图片
                results = data.get("output", {}).get("results", []) or data.get("data", [])
                if results and isinstance(results[0], dict):
                    b64 = results[0].get("b64_image") or results[0].get("b64_json", "")
                    if b64:
                        img_data = base64.b64decode(b64)
                        output_path = "/tmp/test_apiyi_format2.jpg"
                        Path(output_path).write_bytes(img_data)
                        print(f"✓ 图片已保存: {output_path}")
                return True
            else:
                print(f"✗ 错误响应: {resp.text[:500]}")
                return False
    except Exception as e:
        print(f"✗ 异常: {e}")
        return False


async def test_img2img_format3(api_key: str, ref_b64: str):
    """测试图生图格式 3: 使用 edits 端点"""
    print("\n" + "="*60)
    print("测试 4: 图生图格式 3 (使用 /edits 端点)")
    print("="*60)

    headers = {
        "Authorization": f"Bearer {api_key}",
    }

    # 先保存图片到临时文件
    ref_path = "/tmp/test_reference.jpg"
    img_data = base64.b64decode(ref_b64)
    Path(ref_path).write_bytes(img_data)

    data = {
        "model": "seedream-4-5-251128",
        "prompt": "一个穿着白色连衣裙的少女",
        "n": 1,
    }

    files = {
        "image": ("reference.jpg", img_data, "image/jpeg"),
    }

    print(f"请求: POST /v1/images/edits")

    try:
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{settings.APIYI_API_URL}/v1/images/edits",
                data=data,
                files=files,
                headers=headers,
            )

            print(f"响应状态: {resp.status_code}")
            if resp.status_code == 200:
                data = resp.json()
                print(f"✓ 成功！响应数据结构: {list(data.keys())}")
                return True
            else:
                print(f"响应: {resp.text[:500]}")
                return False
    except Exception as e:
        print(f"异常: {e}")
        return False


async def main():
    print("\n" + "="*60)
    print("API 易平台图生图接口测试")
    print("="*60)

    api_key = settings.APIYI_API_KEY
    print(f"\nAPI Key: {api_key[:20]}... (长度: {len(api_key)})")

    # 创建测试图片
    ref_path = "/tmp/test_reference_red.jpg"
    create_test_image(ref_path)
    ref_b64 = image_to_base64(ref_path)
    print(f"\n参考图 Base64 长度: {len(ref_b64)}")

    # 执行测试
    results = {}

    results["text_only"] = await test_text_only(api_key)
    results["img2img_format1"] = await test_img2img_format1(api_key, ref_b64)
    results["img2img_format2"] = await test_img2img_format2(api_key, ref_b64)
    results["img2img_format3"] = await test_img2img_format3(api_key, ref_b64)

    # 总结
    print("\n" + "="*60)
    print("测试总结")
    print("="*60)
    for test_name, result in results.items():
        status = "✓ 通过" if result else "✗ 失败"
        print(f"{test_name}: {status}")

    # 推荐
    if results["img2img_format1"]:
        print("\n推荐使用格式 1: image + reference_strength")
    elif results["img2img_format2"]:
        print("\n推荐使用格式 2: input_image + reference_strength")
    elif results["img2img_format3"]:
        print("\n推荐使用格式 3: /edits 端点")
    else:
        print("\n⚠️ 所有图生图格式均失败，可能 API 易平台不支持该功能")
        print("建议联系 API 易技术支持确认 SeedDream 4.5 是否支持图生图")


if __name__ == "__main__":
    asyncio.run(main())
