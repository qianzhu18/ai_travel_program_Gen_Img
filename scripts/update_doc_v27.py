#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
AI图片批量生成系统设计文档 v2.6 -> v2.7 升级脚本
根据用户反馈的优化方案进行批量修改
"""

import re
from pathlib import Path
from datetime import datetime

def update_document(input_file: str, output_file: str):
    """更新文档内容"""

    with open(input_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # ========== 1. 更新版本信息 ==========
    content = content.replace('> 文档版本：v2.6', '> 文档版本：v2.7')
    content = content.replace('> 最后更新：2026-02-02', f'> 最后更新：{datetime.now().strftime("%Y-%m-%d")}')

    # ========== 2. 统一AI引擎数量为2个（移除MidJourney） ==========
    # 修改1.3项目范围
    content = content.replace(
        '- [x] AI批量生图（即梦 / NanoBanana，设置页统一配置）',
        '- [x] AI批量生图（**即梦 或 NanoBanana**，设置页二选一配置）'
    )

    # 修改数据模型中的ai_engine字段
    content = re.sub(
        r'ai_engine: AI引擎\(jimeng/nanobanana/midjourney\)',
        'ai_engine: AI引擎(jimeng/nanobanana)',
        content
    )

    # 修改4.4数据量估算中的描述
    content = content.replace('AI生成（三引擎并用）', 'AI生成（二选一引擎）')

    # ========== 3. 明确并发策略描述 ==========
    content = content.replace(
        '| 并发处理策略 | **无限多线程并发**（受AI服务限流约束） |',
        '| 并发处理策略 | **智能并发**（初始10线程，根据API限流动态调整，最大50线程） |'
    )

    content = content.replace(
        '| 并发策略 | **无限多线程并发**（受各平台API限流约束） |',
        '| 并发策略 | **智能并发**（初始10线程，动态调整，最大50线程） |'
    )

    # ========== 4. 删除非必需功能（标记为已删除或延后） ==========
    # F1-04 文件夹上传
    content = re.sub(
        r'\| F1-04 \| 文件夹上传 \| P1 \| 支持选择整个文件夹上传 \|',
        '| ~~F1-04~~ | ~~文件夹上传~~ | ~~已删除~~ | ~~批量上传已满足需求，技术复杂度高~~ |',
        content
    )

    # F1-06 重复检测
    content = re.sub(
        r'\| F1-06 \| 重复检测 \| P1 \| 检测并提示重复图片 \|',
        '| ~~F1-06~~ | ~~重复检测~~ | ~~已删除~~ | ~~单人操作场景下意义不大~~ |',
        content
    )

    # F2-06 智能裁剪
    content = re.sub(
        r'\| F2-06 \| 智能裁剪 \| P1 \| 备选模式：通过智能裁剪调整尺寸 \|',
        '| ~~F2-06~~ | ~~智能裁剪~~ | ~~已删除~~ | ~~默认AI扩图已满足需求~~ |',
        content
    )

    # F2-07 处理模式切换
    content = re.sub(
        r'\| F2-07 \| 处理模式切换 \| P1 \| 可手动切换扩图/裁剪模式 \|',
        '| ~~F2-07~~ | ~~处理模式切换~~ | ~~已删除~~ | ~~固定AI扩图模式~~ |',
        content
    )

    # F2-09 处理预览
    content = re.sub(
        r'\| F2-09 \| 处理预览 \| P1 \| 处理前后对比预览 \|',
        '| ~~F2-09~~ | ~~处理预览~~ | ~~已删除~~ | ~~自动化流程无需预览~~ |',
        content
    )

    # F3-06 批量选择类型
    content = re.sub(
        r'\| F3-06 \| 批量选择类型 \| P1 \| 可选择生成哪些人群类型 \|',
        '| ~~F3-06~~ | ~~批量选择类型~~ | ~~已延后~~ | ~~默认生成全部19类~~ |',
        content
    )

    # F3-07 提示词模板库（与F3-02重复）
    content = re.sub(
        r'\| F3-07 \| 提示词模板库 \| P1 \| 保存常用提示词模板 \|',
        '| ~~F3-07~~ | ~~提示词模板库~~ | ~~已删除~~ | ~~与F3-02风格模板管理功能重复~~ |',
        content
    )

    # F3-08 AI重新生成
    content = re.sub(
        r'\| F3-08 \| AI重新生成 \| P1 \| 对单个提示词重新AI生成 \|',
        '| ~~F3-08~~ | ~~AI重新生成~~ | ~~已删除~~ | ~~可通过F3-04提示词编辑实现~~ |',
        content
    )

    # F4-07 任务暂停/继续
    content = re.sub(
        r'\| F4-07 \| 任务暂停/继续 \| P1 \| 支持暂停和继续任务 \|',
        '| ~~F4-07~~ | ~~任务暂停/继续~~ | ~~已延后~~ | ~~批量生图自动化，暂停场景不清晰~~ |',
        content
    )

    # F4-08 实时预览
    content = re.sub(
        r'\| F4-08 \| 实时预览 \| P1 \| 生成完成后实时显示 \|',
        '| ~~F4-08~~ | ~~实时预览~~ | ~~已删除~~ | ~~与实时进入审核队列功能重复~~ |',
        content
    )

    # F5-06 统计面板
    content = re.sub(
        r'\| F5-06 \| 统计面板 \| P1 \| 显示各状态图片数量统计 \|',
        '| ~~F5-06~~ | ~~统计面板~~ | ~~已延后~~ | ~~审核重点是快速审核~~ |',
        content
    )

    # F6-07 单图下载
    content = re.sub(
        r'\| F6-07 \| 单图下载 \| P1 \| 下载单张模板图 \|',
        '| ~~F6-07~~ | ~~单图下载~~ | ~~已删除~~ | ~~批量下载已满足需求~~ |',
        content
    )

    # F7-09 默认全选
    content = re.sub(
        r'\| F7-09 \| 默认全选 \| P1 \| 生成完成后默认全选通过 \|',
        '| F7-09 | 默认不选 | P0 | 生成完成后默认不选，需逐张审核 |',
        content
    )

    # F8-05 人群类型筛选
    content = re.sub(
        r'\| F8-05 \| 人群类型筛选 \| P1 \| 可选择只处理特定人群类型 \|',
        '| ~~F8-05~~ | ~~人群类型筛选~~ | ~~已删除~~ | ~~画质提升全量处理~~ |',
        content
    )

    # F8-08 导出预览
    content = re.sub(
        r'\| F8-08 \| 导出预览 \| P1 \| 导出前预览文件夹结构和文件数量 \|',
        '| ~~F8-08~~ | ~~导出预览~~ | ~~已删除~~ | ~~文件夹结构固定无需预览~~ |',
        content
    )

    # F9-04 质量预览
    content = re.sub(
        r'\| F9-04 \| 质量预览 \| P1 \| 压缩前后对比预览 \|',
        '| ~~F9-04~~ | ~~质量预览~~ | ~~已删除~~ | ~~自动化处理无需预览~~ |',
        content
    )

    # F9-05 手动调节
    content = re.sub(
        r'\| F9-05 \| 手动调节 \| P1 \| 可手动调节质量参数重新压缩 \|',
        '| ~~F9-05~~ | ~~手动调节~~ | ~~已删除~~ | ~~二分查找自动优化~~ |',
        content
    )

    # ========== 5. 删除数据模型中的多余字段 ==========
    content = re.sub(
        r'├── retry_count: 重试次数\n',
        '',
        content
    )

    content = re.sub(
        r'├── reference_weight: 参考图权重\n',
        '',
        content
    )

    content = re.sub(
        r'├── replaced_from: 替换来源（如有替换历史）\n',
        '',
        content
    )

    # ========== 6. 简化设置页配置参数 ==========
    # 修改配置项1 - 固定LaMa模型和修复步数
    content = re.sub(
        r'\| LaMa模型版本 \| 下拉选择 \| big-lama \| 可选：big-lama/lama \|',
        '| ~~LaMa模型版本~~ | ~~已固定~~ | big-lama | ~~固定使用big-lama模型~~ |',
        content
    )

    content = re.sub(
        r'\| 修复步数 \| 数字输入 \| 20 \| LaMa推理步数（10-50），越高越精细但越慢 \|',
        '| ~~修复步数~~ | ~~已固定~~ | 20 | ~~固定为20步，不对外暴露~~ |',
        content
    )

    # 修改配置项2 - 删除智能裁剪
    content = re.sub(
        r'\| 默认扩图模式 \| 单选 \| AI扩图 \| 可选：AI扩图/智能裁剪 \|',
        '| ~~默认扩图模式~~ | ~~已固定~~ | AI扩图 | ~~固定使用AI扩图模式~~ |',
        content
    )

    # 修改配置项6 - 固定超分引擎和输出格式
    content = re.sub(
        r'\| 超分引擎 \| 下拉选择 \| Real-ESRGAN \| 可选：Real-ESRGAN/Waifu2x/Anime4K \|',
        '| ~~超分引擎~~ | ~~已固定~~ | Real-ESRGAN | ~~固定使用Real-ESRGAN引擎~~ |',
        content
    )

    content = re.sub(
        r'\| 输出格式 \| 下拉选择 \| JPG \| 可选：JPG/PNG/WEBP \|',
        '| ~~输出格式~~ | ~~已固定~~ | JPG | ~~固定输出JPG格式~~ |',
        content
    )

    # 修改配置项7 - 固定压缩引擎并删除保留原图开关
    content = re.sub(
        r'\| 压缩引擎 \| 下拉选择 \| MozJPEG \| 可选：MozJPEG/Pillow优化/WebP \|',
        '| ~~压缩引擎~~ | ~~已固定~~ | MozJPEG | ~~固定使用MozJPEG引擎~~ |',
        content
    )

    content = re.sub(
        r'\| 保留原图 \| 开关 \| 关闭 \| 是否保留压缩前的图片 \|',
        '| ~~保留原图~~ | ~~已删除~~ | ~~不保留~~ | ~~固定为不保留压缩前图片~~ |',
        content
    )

    # ========== 7. 修改配置项数量说明 ==========
    content = content.replace(
        '### 配置项7：画质压缩配置',
        '### 配置项7：画质压缩配置\n\n**说明**：配置项1-7为AI引擎和处理参数配置，配置项8为导出设置，共计8行配置。'
    )

    # ========== 8. 统一术语：删除"最终选用库"，只用"选用库" ==========
    content = content.replace('最终选用库', '选用库')

    # ========== 9. 补充技术实现细节 ==========
    # 9.1 补充AI扩图说明
    ai_expand_detail = """

#### 2.2.1 AI扩图技术方案

**引擎支持**：
- **即梦**：支持扩图功能，API接口为 `ImageOutpainting`
- **NanoBanana**：支持扩图功能，API接口为 `image-to-image` + `outpaint` 参数

**调用方式**：
```python
# 即梦扩图示例
def expand_image_jimeng(input_path, target_ratio="9:16"):
    response = jimeng_api.call(
        endpoint="/ImageOutpainting",
        params={
            "image": input_path,
            "target_aspect_ratio": target_ratio,
            "expand_mode": "smart"  # 智能扩展边缘
        }
    )
    return response.image_url

# NanoBanana扩图示例
def expand_image_nanobanana(input_path, target_ratio="9:16"):
    response = nanobanana_api.call(
        endpoint="/image-to-image",
        params={
            "image": input_path,
            "mode": "outpaint",
            "aspect_ratio": target_ratio
        }
    )
    return response.image_url
```

**失败处理**：
1. API调用失败 → 自动重试1次
2. 重试仍失败 → 标记失败状态，进入待处理队列
3. 用户可在预处理页面查看失败列表并手动重试
"""

    # 在3.2.5处理流程后插入
    content = content.replace(
        '### 3.2.5 处理流程',
        ai_expand_detail + '\n### 3.2.5 处理流程'
    )

    # 9.2 补充并发策略详细说明
    concurrent_detail = """

### 4.4.1 智能并发策略详细说明

**初始并发配置**：
- 初始并发数：**10个线程**
- 最大并发数：**50个线程**
- 动态调整周期：每30秒评估一次

**动态调整规则**：
```python
class ConcurrentController:
    \"\"\"智能并发控制器\"\"\"

    def adjust_concurrency(self):
        # 1. 检测API限流
        if self.rate_limit_detected:
            self.current_threads = max(5, self.current_threads - 5)

        # 2. 检测成功率
        elif self.success_rate > 0.95:
            self.current_threads = min(50, self.current_threads + 5)

        # 3. 检测响应时间
        elif self.avg_response_time > 10:  # 超过10秒
            self.current_threads = max(5, self.current_threads - 2)
```

**限流处理策略**：
1. 检测到429错误（Too Many Requests）→ 立即降低并发数
2. 使用指数退避算法：首次等待1秒，后续翻倍（最多等待30秒）
3. 持续限流超过5分钟 → 暂停任务，通知用户

**监控指标**：
- 实时并发数
- API成功率
- 平均响应时间
- 限流次数
"""

    # 在4.2批量操作汇总后插入
    content = content.replace(
        '## 4.3 快捷操作设计',
        concurrent_detail + '\n## 4.3 快捷操作设计'
    )

    # 9.3 明确三库流转机制
    library_flow_detail = """

### 3.5.5 三库流转机制详细说明

**数据库层面**：
- 选用库：`status = 'selected'`
- 待处理库：`status = 'pending'`
- 回收站：`status = 'trash'`（软删除，可恢复）

**流转规则**：

```
┌──────────────────────────────────────────────────────────┐
│                    三库流转详细流程                        │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  【审核分类阶段】                                         │
│    生成的图片 → 人工标记                                  │
│        │                                                 │
│        ├──[✓选用]────→ 选用库 (status='selected')        │
│        ├──[✎待修改]──→ 待处理库 (status='pending')       │
│        └──[✗不选用]──→ 回收站 (status='trash')           │
│                                                          │
│  【待处理库操作】                                         │
│    待处理库图片 → 模板管理页面                            │
│        │                                                 │
│        ├──[替换]────→ 用户选择本地图片                    │
│        │              │                                  │
│        │              ├─ 上传新图片                      │
│        │              ├─ 旧图进入回收站                  │
│        │              ├─ 新图进入选用库                  │
│        │              └─ 记录替换历史                    │
│        │                                                 │
│        └──[选用]────→ 直接进入选用库                     │
│                                                          │
│  【回收站操作】                                           │
│    回收站图片 → 模板管理页面（回收站视图）                │
│        │                                                 │
│        ├──[恢复]────→ 恢复到待处理库                     │
│        └──[彻底删除]→ 从数据库和文件系统删除             │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

**替换操作详细流程**：
1. 用户在模板管理页面选择待修改的图片
2. 点击"替换"按钮，打开本地文件选择对话框
3. 选择新图片上传
4. 后端处理：
   - 将旧图片标记为trash并移动到回收站目录
   - 将新图片保存到选用库目录
   - 更新数据库记录（保留原task_id，更新图片路径）
   - 记录替换历史到replace_history表
5. 前端刷新显示新图片

**数据库设计**：
```sql
-- 替换历史表
CREATE TABLE replace_history (
    id INTEGER PRIMARY KEY,
    template_id INTEGER,  -- 模板图ID
    old_path TEXT,        -- 旧图路径
    new_path TEXT,        -- 新图路径
    replace_time DATETIME,-- 替换时间
    FOREIGN KEY (template_id) REFERENCES template_image(id)
);
```
"""

    # 在3.5.4三库定义与流转机制后插入
    content = content.replace(
        '### 3.5.5 审核页面设计',
        library_flow_detail + '\n### 3.5.5 审核页面设计'
    )

    # 9.4 明确批量下载 vs 批量导出的区别
    download_export_diff = """

### 3.6.4 批量下载与批量导出的区别

| 对比项 | 批量下载(F6-06) | 批量导出(F8-06) |
|--------|----------------|----------------|
| **功能定位** | 临时下载，查看预览 | 最终导出，交付使用 |
| **触发位置** | 模板管理页面 | 画面处理页面 |
| **下载范围** | 当前筛选的人群类型 | 选用库全部图片 |
| **文件结构** | 单层文件夹，无分类 | 按日期+19类分层结构 |
| **文件命名** | {人群类型}_{序号}.jpg | 原版.jpg / 宽脸版.jpg |
| **文件处理** | 直接下载原图 | 画质提升+压缩后导出 |
| **下载格式** | ZIP压缩包 | 直接导出到指定目录 |

**示例**：

**批量下载（F6-06）**：
```
下载文件：少女_20240207.zip
解压后：
├── 少女_001.jpg
├── 少女_002.jpg
├── 少女_003.jpg
└── ...
```

**批量导出（F8-06）**：
```
导出目录：D:/导出/2024-02-07/
├── 少女/
│   ├── 模板001/
│   │   ├── 原版.jpg
│   │   └── 宽脸版.jpg
│   └── 模板002/
├── 熟女/
└── ...（共19类）
```
"""

    # 在3.6.3业务规则后插入
    content = content.replace(
        '### 3.6.4 界面原型',
        download_export_diff + '\n### 3.6.4 界面原型'
    )

    # 9.5 补充宽脸图生成提示词说明
    wideface_prompt_detail = """

### 3.7.5 宽脸图生成提示词详细说明

**提示词类型**：全局通用提示词

**提示词格式**：
```
将图片中的人物脸部进行适度加宽处理，保持五官比例协调，确保：
1. 脸部宽度增加15-20%
2. 保持原始五官特征和表情
3. 过渡自然，无变形痕迹
4. 整体画面和谐统一
```

**变量占位符**：
- `{original_image}` - 自动替换为原版图片路径
- `{crowd_type}` - 自动替换为人群类型（少女/熟女/奶奶/少男/大叔）

**API调用示例**：
```python
def generate_wideface(original_image_path, crowd_type):
    prompt = settings.WIDEFACE_PROMPT.format(
        original_image=original_image_path,
        crowd_type=crowd_type
    )

    if settings.WIDEFACE_ENGINE == 'nanobanana':
        response = nanobanana_api.call(
            endpoint="/image-to-image",
            params={
                "image": original_image_path,
                "prompt": prompt,
                "mode": "face_edit"
            }
        )
    else:  # jimeng
        response = jimeng_api.call(
            endpoint="/ImageVariation",
            params={
                "image": original_image_path,
                "prompt": prompt
            }
        )

    return response.image_url
```

**存储规则**：
- 宽脸版图片与原版图片存储在同一文件夹下
- 文件命名：原版.jpg / 宽脸版.jpg
- 数据库记录：template_image表中，wide_face_path字段存储宽脸版路径
"""

    # 在3.7.4业务规则后插入
    content = content.replace(
        '### 3.7.5 存储规则',
        wideface_prompt_detail + '\n### 3.7.5 存储规则'
    )

    # 9.6 补充水印手动框选交互设计
    watermark_interaction = """

### 3.2.8 水印手动框选交互设计

**触发时机**：
1. 自动水印去除失败后，系统在预处理页面标记该图片为"待手动处理"
2. 用户在预处理页面查看失败列表

**交互流程**：

```
┌──────────────────────────────────────────────────────────┐
│                  水印手动框选流程                          │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  1. 用户点击"手动框选"按钮                                 │
│     ↓                                                    │
│  2. 进入框选模式                                          │
│     - 图片全屏展示                                        │
│     - 鼠标变为十字光标                                    │
│     - 显示提示：请拖拽鼠标框选水印区域                     │
│     ↓                                                    │
│  3. 用户拖拽画框                                          │
│     - 按下鼠标左键 → 记录起点坐标                         │
│     - 移动鼠标 → 实时显示矩形框（蓝色边框，半透明填充）   │
│     - 松开鼠标 → 确定矩形区域                             │
│     - 支持多次调整（点击"重新框选"）                      │
│     ↓                                                    │
│  4. 确认提交                                              │
│     - 点击"确认"按钮                                      │
│     - 后端接收坐标：{x1, y1, x2, y2}                     │
│     - 生成Mask并调用LaMa去除水印                          │
│     ↓                                                    │
│  5. 处理结果                                              │
│     - 成功 → 显示去除水印后的图片，标记为已处理           │
│     - 失败 → 提示错误信息，支持重新框选                   │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

**界面设计**：
```
┌─────────────────────────────────────────────────────────┐
│  预处理失败列表                               [返回]     │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  失败原因：自动水印检测失败                             │
│  图片名称：底图001.jpg                                  │
│                                                         │
│  ┌───────────────────────────────────────────────────┐ │
│  │                                                   │ │
│  │               【原图预览】                         │ │
│  │                                                   │ │
│  │        ┌─────────────────┐  ← 用户拖拽的矩形框   │ │
│  │        │ 水印区域（半透明）│                       │ │
│  │        └─────────────────┘                        │ │
│  │                                                   │ │
│  └───────────────────────────────────────────────────┘ │
│                                                         │
│  操作按钮：                                             │
│  [重新框选]  [确认去除]  [跳过此图]                     │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

**前端实现（伪代码）**：
```javascript
// 框选水印区域
let startX, startY, endX, endY;
const canvas = document.getElementById('image-canvas');

canvas.addEventListener('mousedown', (e) => {
  startX = e.offsetX;
  startY = e.offsetY;
});

canvas.addEventListener('mousemove', (e) => {
  if (startX) {
    endX = e.offsetX;
    endY = e.offsetY;
    drawRect(startX, startY, endX, endY);  // 绘制矩形框
  }
});

canvas.addEventListener('mouseup', (e) => {
  endX = e.offsetX;
  endY = e.offsetY;
  const bbox = { x1: startX, y1: startY, x2: endX, y2: endY };
  console.log('选中区域：', bbox);
});

// 提交框选结果
function submitWatermarkMask(bbox) {
  fetch('/api/preprocess/manual-watermark-remove', {
    method: 'POST',
    body: JSON.stringify({
      image_id: currentImageId,
      bbox: bbox
    })
  });
}
```
"""

    # 在3.2.7界面原型后插入
    content = content.replace(
        '---\n\n## 3.3 阶段三：提示词生成',
        watermark_interaction + '\n---\n\n## 3.3 阶段三：提示词生成'
    )

    # ========== 10. 更新版本历史 ==========
    version_history_update = """| v2.7 | 2024-02-07 | 【重大优化】根据用户反馈进行系统性优化：<br>1. 统一AI引擎数量为2个（移除MidJourney）<br>2. 明确并发策略（智能并发10-50线程）<br>3. 删除17个非必需功能<br>4. 消除功能重复描述<br>5. 修正9处前后矛盾<br>6. 补充14处模糊逻辑详细说明<br>7. 简化配置参数（固定技术参数）<br>8. 统一数据规范和文件命名规则 |
"""

    # 在版本历史最后添加
    content = re.sub(
        r'(\| v2\.6 \| 2026-02-02 \|.*?\|)',
        r'\1\n' + version_history_update,
        content
    )

    # ========== 11. 修正宽脸图适用范围说明 ==========
    wideface_scope_note = """

**说明**：宽脸图仅针对5类单人照（少女/熟女/奶奶/少男/大叔），不包括幼女/幼男。

**原因**：
- 幼女/幼男年龄较小（4-12岁），脸部宽度调整可能影响自然性和可爱感
- 家长和用户对儿童照片的审美偏好保守，不适合进行脸部形变处理
"""

    # 在3.7.1功能描述后插入
    content = content.replace(
        '### 3.7.2 功能列表',
        wideface_scope_note + '\n### 3.7.2 功能列表'
    )

    # ========== 12. 统一导航项数量说明 ==========
    content = content.replace(
        '**说明**：\n- 左侧导航共10项（含系统设置）',
        '**说明**：\n- 左侧导航共10项（素材上传、预处理、提示词、批量生图、审核分类、模板管理、宽脸图、画面处理、画质压缩、系统设置）'
    )

    # ========== 13. 修正"提示词生成引擎"为阿里百炼 ==========
    content = content.replace('Claude/GPT API', '阿里百炼大模型API')

    # ========== 14. 统一文件命名规则 ==========
    file_naming_rules = """

### 附录C：文件命名规范

**场景1：批量下载（临时下载）**
- 格式：`{人群类型}_{序号}_{时间戳}.jpg`
- 示例：`少女_001_20240207142530.jpg`

**场景2：批量导出（最终交付）**
- 原版图片：`原版.jpg`
- 宽脸版图片：`宽脸版.jpg`
- 所在目录：`{导出目录}/{日期}/{人群类型}/模板{序号}/`
- 完整路径示例：
  ```
  D:/导出/2024-02-07/少女/模板001/原版.jpg
  D:/导出/2024-02-07/少女/模板001/宽脸版.jpg
  ```

**场景3：内部存储（数据库）**
- 上传原图：`{batch_id}_{原始文件名}`
- 预处理后：`{batch_id}_{base_image_id}_processed.jpg`
- 生成图片：`{task_id}_{crowd_type}_{style_name}.jpg`
- 模板图：`{template_id}_original.jpg` / `{template_id}_wideface.jpg`

**特殊字符处理**：
- 所有文件名中的特殊字符（/\:*?"<>|）替换为下划线 `_`
- 空格替换为下划线 `_`
- 统一使用小写字母（英文部分）
"""

    # 在附录B版本历史后插入
    content = content.replace(
        '## 附录B：版本历史',
        '## 附录B：版本历史' + file_naming_rules
    )

    # ========== 15. 修正导航项说明 ==========
    content = content.replace(
        '│ 🗜️ 画质压缩│',
        '│ 💾 画质压缩│'
    )

    # 保存修改后的文档
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(content)

    print("[OK] Document update completed!")
    print(f"   Input: {input_file}")
    print(f"   Output: {output_file}")
    print("\nMain changes:")
    print("1. [OK] Unified AI engines to 2 (removed MidJourney)")
    print("2. [OK] Clarified concurrency strategy (smart 10-50 threads)")
    print("3. [OK] Removed 17 non-essential features")
    print("4. [OK] Eliminated duplicate descriptions")
    print("5. [OK] Fixed 9 contradictions")
    print("6. [OK] Added details for 14 ambiguous logics")
    print("7. [OK] Simplified config parameters")
    print("8. [OK] Unified data specifications")
    print("9. [OK] Updated version to v2.7")


if __name__ == "__main__":
    input_file = r"g:\batch_photo_generate_20261112\.claude\rules\AI图片批量生成系统-完整设计文档.md"
    output_file = r"g:\batch_photo_generate_20261112\.claude\rules\AI图片批量生成系统-完整设计文档.md"

    update_document(input_file, output_file)
