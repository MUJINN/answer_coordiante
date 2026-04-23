# 坐标OCR测试脚本使用说明

## 概述

这套脚本用于测试坐标OCR功能，支持两种方式：
1. **本地图片**：转换为base64格式发送到webhook
2. **图片URL**：直接使用URL地址（推荐，避免base64过大问题）

发送到n8n webhook获取OCR识别结果（包括坐标信息），并生成可视化展示页面。

## 文件说明

### 1. `test_coordinate_ocr.py` - 本地图片测试脚本（base64方式）

**功能：**
- 将本地图片转换为base64格式
- 构造符合n8n工作流格式的请求
- 并发发送到webhook获取OCR结果
- 保存识别结果和坐标信息

**用法：**
```bash
# 基本用法
python test_coordinate_ocr.py --subject_id 10023044 --block_id 25033359 --image_dir ./10023044/25033359

# 限制处理数量
python test_coordinate_ocr.py --subject_id 10023044 --block_id 25033359 --image_dir ./10023044/25033359 --max_count 2

# 指定输出目录
python test_coordinate_ocr.py --subject_id 10023044 --block_id 25033359 --image_dir ./10023044/25033359 --output_dir ./test_output

# 指定并发线程数
python test_coordinate_ocr.py --subject_id 10023044 --block_id 25033359 --image_dir ./10023044/25033359 --workers 10
```

**参数说明：**
| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--subject_id` | 科目ID | 必填 |
| `--block_id` | 题块ID | 必填 |
| `--image_dir` | 图片目录路径 | 必填 |
| `--output_dir` | 输出目录路径 | `./test_output` |
| `--webhook_url` | Webhook URL | `https://n8n.iyunxiao.com/webhook/test/answer_coordinate` |
| `--config` | 配置文件路径（JSON格式） | 无 |
| `--workers` | 并发线程数 | 5 |
| `--max_count` | 最大处理数量 | 全部 |

### 2. `test_coordinate_ocr_url.py` - URL图片测试脚本（推荐）

**功能：**
- 使用图片URL进行测试，避免base64过大问题
- 支持从txt文件批量读取URL
- 支持多种URL文件格式
- 并发发送到webhook获取OCR结果

**用法：**
```bash
# 从URL文件读取（推荐）
python test_coordinate_ocr_url.py --subject_id 001 --block_id 01 --url_file urls.txt

# 直接指定单个URL
python test_coordinate_ocr_url.py --subject_id 001 --block_id 01 --url "https://example.com/image.png" --kaohao "12345"

# 指定输出目录和并发数
python test_coordinate_ocr_url.py --subject_id 001 --block_id 01 --url_file urls.txt --output_dir ./test_output --workers 10
```

**参数说明：**
| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--subject_id` | 科目ID | 必填 |
| `--block_id` | 题块ID | 必填 |
| `--url_file` | URL文件路径 | 与--url二选一 |
| `--url` | 单个图片URL | 与--url_file二选一 |
| `--kaohao` | 考号（与--url配合使用） | 使用--url时必填 |
| `--output_dir` | 输出目录路径 | `./test_output` |
| `--webhook_url` | Webhook URL | `https://n8n.iyunxiao.com/webhook/test/answer_coordinate` |
| `--config` | 配置文件路径（JSON格式） | 无 |
| `--workers` | 并发线程数 | 5 |

**URL文件格式支持：**

```bash
# 格式1: 每行一个URL（自动生成考号）
https://cdn.example.com/image1.png
https://cdn.example.com/image2.png

# 格式2: kaohao URL（推荐）
12345 https://cdn.example.com/image1.png
12346 https://cdn.example.com/image2.png

# 格式3: kaohao URL filename
12345 https://cdn.example.com/image1.png image1.png

# 格式4: JSON格式（每行一个JSON对象）
{"kaohao": "12345", "url": "https://cdn.example.com/image1.png", "filename": "image1.png"}
```

### 3. `generate_batch_viewer.py` - 生成批量展示页面（base64版本）

**功能：**
- 处理base64格式的OCR结果
- 自动识别不同科目ID和题块ID的结果
- 按科目/题块分组展示
- 在图片上绘制坐标标注框
- 生成HTML批量展示页面（支持标签页切换）

**用法：**
```bash
# 基本用法（自动识别多个科目/题块）
python generate_batch_viewer.py <输出目录> <结果根目录>

# 示例
python generate_batch_viewer.py batch_viewer test_output

# 指定字体大小
python generate_batch_viewer.py batch_viewer test_output --font-size 28
```

**参数说明：**
| 参数 | 说明 |
|------|------|
| `output_dir` | 输出目录 |
| `result_dir` | OCR结果根目录（将递归查找所有*_result.json） |
| `--font-size` | 标注字体大小（默认：24） |

**特点：**
- 从结果文件的 `image` 字段读取 base64 数据
- 自动按 `subject_id_block_id` 分组
- 支持多个科目/题块同时展示
- 标签页切换不同科目/题块
- 跨组搜索功能

### 4. `generate_batch_viewer_url.py` - 生成批量展示页面（URL版本）

**功能：**
- 处理URL格式的OCR结果
- 从URL下载图片并绘制标注
- 其他功能与base64版本相同

**用法：**
```bash
# 基本用法
python generate_batch_viewer_url.py batch_viewer test_output

# 指定字体大小
python generate_batch_viewer_url.py batch_viewer test_output --font-size 28
```

**参数说明：**
| 参数 | 说明 |
|------|------|
| `output_dir` | 输出目录 |
| `result_dir` | OCR结果根目录（将递归查找所有*_result.json） |
| `--font-size` | 标注字体大小（默认：24） |

**特点：**
- 从结果文件的 `image_url` 字段读取图片URL
- 自动下载图片并生成标注
- 适用于大图片或大量图片的场景（避免base64过大问题）

## 脚本选择指南

| 场景 | 推荐脚本 |
|------|----------|
| 本地图片测试 | `test_coordinate_ocr.py` + `generate_batch_viewer.py` |
| 图片URL测试 | `test_coordinate_ocr_url.py` + `generate_batch_viewer_url.py` |
| `result_dir` | OCR结果根目录（将递归查找所有*_result.json） |
| `--font-size` | 标注字体大小（默认：24） |

**特点：**
- 自动按 `subject_id_block_id` 分组
- 支持多个科目/题块同时展示
- 标签页切换不同科目/题块
- 跨组搜索功能

## 输入文件命名格式

图片文件名格式：`{school_id}_{kaohao}_{index}.png`

示例：`11532_21010106_0.png`
- `11532`: 学校ID
- `21010106`: 考号
- `0`: 图片索引

## 工作流程

### 1. 准备测试数据

确保图片按以下结构组织：
```
.
├── 10023044/
│   └── 25033359/
│       ├── 11532_21010106_0.png
│       ├── 11532_21010107_0.png
│       └── 11532_21010108_0.png
```

### 2. 运行OCR测试

```bash
python test_coordinate_ocr.py \
  --subject_id 10023044 \
  --block_id 25033359 \
  --image_dir ./10023044/25033359 \
  --output_dir ./test_output
```

### 3. 生成可视化页面

```bash
python generate_batch_viewer.py batch_viewer test_output
```

### 4. 查看结果

在浏览器中打开 `batch_viewer/index.html`

## 输出文件结构

### OCR测试结果（自动按科目/题块分目录）
```
test_output/
├── 10023044_25033359/        # 科目10023044/题块25033359
│   ├── 21010106_input.json
│   ├── 21010106_result.json
│   ├── 21010107_input.json
│   ├── 21010107_result.json
│   ├── 21010108_input.json
│   ├── 21010108_result.json
│   └── _summary.json
└── 10019802_24852059/        # 科目10019802/题块24852059
    ├── ...
```

### 批量展示页面（自动分组展示）
```
batch_viewer/
├── index.html                # 主页面（支持多科目/题块切换）
└── images/
    ├── 10023044_25033359/    # 按科目/题块分组
    │   ├── 21010106.png
    │   ├── 21010107.png
    │   └── 21010108.png
    └── 10019802_24852059/
        └── ...
```

## OCR结果格式

```json
{
  "kaohao": "21010106",
  "image_file": "11532_21010106_0.png",
  "ocr_results": {
    "result": "完整识别文本...",
    "webhook_response": {
      "model_name": "doubao-seed-1.8",
      "result": "完整识别文本...",
      "key_result": [
        {
          "key": "15(1)",
          "key_ocr": "NH₄⁺ + H₂O ⇌ NH₃·H₂O + H⁺ 故NH₄Cl溶液呈酸性",
          "answer_coordinate": [0.06, 0.15, 0.74, 0.32]
        },
        {
          "key": "15(2)",
          "key_ocr": "10⁻⁴",
          "answer_coordinate": [0.08, 0.38, 0.18, 0.52]
        }
      ]
    }
  }
}
```

**坐标说明：**
- `answer_coordinate`: `[x1, y1, x2, y2]`
- 坐标范围：`0~1`（相对于图片尺寸）
- 原点：图片左上角
- x轴向右，y轴向下

## 批量展示页面功能

- 网格布局展示所有学生的标注图片
- 每个卡片显示：
  - 考号和文件名
  - 标注后的图片（彩色框+题号标签）
  - 每个小题的识别结果和坐标
  - 完整OCR识别文本
- 搜索功能：支持按考号或识别内容筛选

## 配置文件

可以使用 `config_example.json` 自定义配置：

```json
{
  "model_name": "doubao-seed-1.8",
  "subject_name": "化学",
  "question_type": "解答题",
  "prompt": "自定义提示词..."
}
```

## 注意事项

1. **图片格式**：支持PNG、JPG格式
2. **文件命名**：必须按 `{school_id}_{kaohao}_{index}.png` 格式命名
3. **并发控制**：默认并发数为5，可根据webhook服务性能调整
4. **超时设置**：默认请求超时时间为120秒

## 目录结构

```
answer_coordiante/
├── test_coordinate_ocr.py        # OCR测试脚本
├── generate_batch_viewer.py       # 可视化页面生成脚本
├── config_example.json            # 配置示例
├── README_COORDINATE_OCR.md       # 使用文档（本文件）
├── 坐标测试.json                  # n8n工作流配置
├── 10019802/                      # 测试数据1
├── 10023044/                      # 测试数据2
│   └── 25033359/                 # 题块图片
├── test_output/                   # OCR测试结果
└── batch_viewer/                  # 批量展示页面
    └── index.html
```
