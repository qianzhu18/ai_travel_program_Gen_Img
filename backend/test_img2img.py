#!/usr/bin/env python3
"""
图生图功能测试脚本
测试参考图是否正确传递到 API
"""
import asyncio
import base64
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.image_generator import APIYiImageClient
from app.core.config import settings


def create_test_image(path: str):
    """创建一个测试图片（红色背景）"""
    import cv2
    import numpy as np

    # 创建一个 576x1024 的红色背景图片
    img = np.zeros((1024, 576, 3), dtype=np.uint8)
    img[:] = [0, 0, 255]  # BGR 红色
    # 添加一些白色文字区域便于识别
    cv2.rectangle(img, (100, 100), (476, 300), (255, 255, 255), -1)

    Path(path).parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(path, img)
    print(f"✓ 创建测试图片: {path}")
    return True


def load_base64_image(path: str) -> str:
    """加载图片为 Base64"""
    import cv2

    if not Path(path).exists():
        print(f"✗ 图片不存在: {path}")
        return ""

    img = cv2.imread(path)
    if img is None:
        print(f"✗ 无法读取图片: {path}")
        return ""

    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 85])
    if not ok:
        print(f"✗ 无法编码图片: {path}")
        return ""

    b64 = base64.b64encode(buf.tobytes()).decode("utf-8")
    print(f"✓ 加载图片为 Base64: {len(b64)} 字符")
    return b64


async def test_image_generator():
    """测试图片生成服务"""
    print("\n" + "="*60)
    print("图生图功能测试")
    print("="*60)

    # 1. 检查 API Key
    api_key = settings.APIYI_API_KEY
    print(f"\n[1] API Key 检查")
    if not api_key or api_key == "your_apiyi_key_here":
        print(f"✗ API Key 未配置或为占位符")
        print(f"  当前值: {api_key[:20] if api_key else 'None'}...")
        return False
    print(f"✓ API Key 已配置 (长度: {len(api_key)})")

    # 2. 创建测试图片
    test_image_path = "/tmp/test_reference_red.jpg"
    print(f"\n[2] 创建测试参考图")
    if not create_test_image(test_image_path):
        return False

    # 3. 测试图片加载
    print(f"\n[3] 测试参考图 Base64 编码")
    ref_b64 = load_base64_image(test_image_path)
    if not ref_b64:
        return False

    # 4. 测试 APIYiImageClient
    print(f"\n[4] 测试 APIYiImageClient 参考图加载")
    client = APIYiImageClient(
        api_key=api_key,
        seedream_model="seedream-4-5-251128",
        disable_watermark=True,
        strict_reference=True,
    )

    loaded_b64 = client._load_reference_base64(test_image_path)
    if not loaded_b64:
        print(f"✗ APIYiImageClient._load_reference_base64 失败")
        return False
    print(f"✓ APIYiImageClient 加载参考图成功 (长度: {len(loaded_b64)})")

    # 5. 测试纯文生图（不带参考图）
    print(f"\n[5] 测试纯文生图（不带参考图）")
    text_only_output = "/tmp/test_text_only.jpg"
    success = await client.generate_image(
        engine="seedream",
        prompt="一个穿着蓝色连衣裙的少女，站在红色背景前",
        negative_prompt="",
        reference_image_path="",  # 空路径
        reference_weight=0,
        output_path=text_only_output,
    )

    if success:
        print(f"✓ 纯文生图成功: {text_only_output}")
    else:
        print(f"✗ 纯文生图失败")
        print(f"  错误码: {client.last_error_code}")
        print(f"  错误信息: {client.last_error_message}")

    # 6. 测试图生图（带参考图）
    print(f"\n[6] 测试图生图（带参考图）")
    img2img_output = "/tmp/test_img2img.jpg"
    success = await client.generate_image(
        engine="seedream",
        prompt="一个穿着白色连衣裙的少女",
        negative_prompt="",
        reference_image_path=test_image_path,  # 带参考图
        reference_weight=92,
        output_path=img2img_output,
    )

    if success:
        print(f"✓ 图生图成功: {img2img_output}")

        # 比较两张图片的相似度
        import cv2
        img1 = cv2.imread(text_only_output)
        img2 = cv2.imread(img2img_output)

        if img1 is not None and img2 is not None:
            # 简单的颜色直方图比较
            hist1 = cv2.calcHist([img1], [0, 1, 2], None, [8, 8, 8], [0, 256, 0, 256, 0, 256])
            hist2 = cv2.calcHist([img2], [0, 1, 2], None, [8, 8, 8], [0, 256, 0, 256, 0, 256])
            similarity = cv2.compareHist(hist1, hist2, cv2.HISTCMP_CORREL)

            print(f"\n[7] 图片相似度分析")
            print(f"  纯文生图 vs 图生图 相似度: {similarity:.4f}")
            if similarity < 0.8:
                print(f"  ✓ 相似度较低 (<0.8)，说明参考图可能起作用了")
            else:
                print(f"  ✗ 相似度较高 (>=0.8)，参考图可能未生效")
    else:
        print(f"✗ 图生图失败")
        print(f"  错误码: {client.last_error_code}")
        print(f"  错误信息: {client.last_error_message}")

    # 8. 测试总结
    print(f"\n" + "="*60)
    print(f"测试总结")
    print(f"="*60)
    print(f"API Key: {'✓ 已配置' if api_key and api_key != 'your_apiyi_key_here' else '✗ 未配置'}")
    print(f"参考图加载: {'✓ 成功' if loaded_b64 else '✗ 失败'}")
    print(f"纯文生图: {'✓ 成功' if success else '✗ 失败'}")
    print(f"图生图: {'✓ 成功' if success else '✗ 失败'}")

    return success


if __name__ == "__main__":
    asyncio.run(test_image_generator())
