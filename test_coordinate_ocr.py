#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试坐标OCR脚本
使用本地测试图片，转换为base64格式，构造符合n8n工作流格式的请求并发送到webhook

测试数据格式说明:
- 图片路径: ./10023044/25033359/11532_21010106_0.png
- 10023044: subject_id
- 25033359: block_id
- 11532: 学校ID
- 21010106: 考号
- 0: 图片索引

用法:
    python test_coordinate_ocr.py --subject_id 10023044 --block_id 25033359 --image_dir ./10023044/25033359

注意:
    脚本会将本地图片转换为base64编码格式，然后发送到webhook进行处理
"""

import json
import os
import sys
import requests
import argparse
import base64
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
import time


# 默认配置（与n8n工作流中的pinData保持一致）
DEFAULT_CONFIG = {
    "model_name": "doubao-seed-1.8",
    "model_names": [
        "doubao-seed-1-6-vision-250815",
        "doubao-seed-1.6-251015",
        "doubao-seed-1.8"
    ],
    "agent_id": "ocr_model_x",
    "taskKey": "",
    "key": "",
    "grade": "",
    "problem": "",
    "answer": "",
    "totalScore": 0,
    "subject_name": "化学",
    "question_type": "解答题",
    "prompt": "【注意事项】\\n一、结构：识别电子排布式（3dⁿ4sⁿ）、电极反应式（含NiO(OH)、e⁻）、溶度积分析、pH、化学方程式、晶胞计算式。\\n二、核心：化学符号（Ni、Cd）、离子（Ni²⁺、OH⁻）、Ksp、⇌、Nₐ、a/c晶胞参数。\\n三、易混：手写上下标（如3d⁸）、O/0、l/1、e⁻与减号、Ksp大小写。\\n四、连贯：保持反应式结构、晶胞公式分子分母完整。"
}

# Webhook URL
WEBHOOK_URL = "https://n8n.iyunxiao.com/webhook/test/answer_coordinate"


def parse_upload_key_from_filename(filename):
    """
    从文件名解析uploadKey信息
    文件名格式: 11532_21010106_0.png
    - 11532: 学校ID
    - 21010106: 考号
    - 0: 图片索引

    Returns:
        tuple: (school_id, kaohao, index)
    """
    # 去掉扩展名
    name_without_ext = Path(filename).stem

    # 分割
    parts = name_without_ext.split('_')
    if len(parts) >= 2:
        school_id = parts[0]
        kaohao = parts[1]
        index = parts[2] if len(parts) > 2 else "0"
        return school_id, kaohao, index

    return None, None, None


def image_to_base64(image_path):
    """
    将本地图片转换为base64编码

    Args:
        image_path: 图片文件路径

    Returns:
        str: base64编码的图片字符串
    """
    with open(image_path, 'rb') as f:
        image_data = f.read()
        base64_str = base64.b64encode(image_data).decode('utf-8')
        return base64_str


def create_webhook_data(subject_id, block_id, kaohao, image_base64, config=None):
    """
    创建符合n8n工作流期望的webhook数据格式（使用base64）

    Args:
        subject_id: 科目ID
        block_id: 题块ID
        kaohao: 考号
        image_base64: 图片的base64编码
        config: 配置字典

    Returns:
        list: 符合webhook格式的数据
    """
    if config is None:
        config = DEFAULT_CONFIG

    upload_key = f"{subject_id}-{block_id}-{kaohao}"

    # 构建符合n8n工作流期望的格式（参考pinData中的body结构）
    # 使用data URI格式的base64图片
    data_uri = f"data:image/png;base64,{image_base64}"

    webhook_data = [{
        "model_name": config['model_name'],
        "model_names": config['model_names'],
        "agent_id": config['agent_id'],
        "subjectId": subject_id,
        "blockId": block_id,
        "taskKey": config['taskKey'],
        "key": config['key'],
        "grade": config['grade'],
        "problem": config['problem'],
        "answer": config['answer'],
        "totalScore": config['totalScore'],
        "subject_name": config['subject_name'],
        "question_type": config['question_type'],
        "prompt": config['prompt'],
        "students": [
            {
                "uploadKey": upload_key,
                "files": [data_uri],  # 使用base64 data URI
                "kaohao": kaohao,
                "from": ""
            }
        ]
    }]

    return webhook_data


def send_to_webhook(kaohao, webhook_data, webhook_url, timeout=120):
    """
    发送数据到webhook

    Args:
        kaohao: 考号
        webhook_data: webhook数据
        webhook_url: webhook URL
        timeout: 超时时间

    Returns:
        dict: webhook响应结果，失败返回None
    """
    try:
        print(f"  发送请求: {kaohao}")
        response = requests.post(
            webhook_url,
            headers={"Content-Type": "application/json"},
            json=webhook_data,
            timeout=timeout
        )

        response.raise_for_status()
        return response.json()

    except requests.exceptions.Timeout:
        print(f"  ❌ 请求超时")
        return None
    except requests.exceptions.RequestException as e:
        print(f"  ❌ 请求失败: {e}")
        # 打印响应内容（如果有）
        if hasattr(e.response, 'text'):
            print(f"  响应内容: {e.response.text[:200]}")
        return None
    except Exception as e:
        print(f"  ❌ 处理失败: {e}")
        return None


def batch_process_images(subject_id, block_id, image_dir, output_dir, webhook_url, config=None, workers=5, max_count=None):
    """
    批量处理图片目录并发送到webhook（使用base64编码）

    Args:
        subject_id: 科目ID
        block_id: 题块ID
        image_dir: 图片目录
        output_dir: 输出目录
        webhook_url: webhook URL
        config: 配置字典
        workers: 并发线程数
        max_count: 最大处理数量
    """
    if config is None:
        config = DEFAULT_CONFIG.copy()

    image_dir = Path(image_dir)

    if not image_dir.exists():
        raise ValueError(f"图片目录不存在: {image_dir}")

    # 创建带科目ID和题块ID的子目录
    output_dir = os.path.join(output_dir, f"{subject_id}_{block_id}")
    os.makedirs(output_dir, exist_ok=True)

    # 创建输出目录
    os.makedirs(output_dir, exist_ok=True)

    # 获取所有图片文件
    image_files = list(image_dir.glob("*.png")) + list(image_dir.glob("*.jpg")) + list(image_dir.glob("*.jpeg"))

    if not image_files:
        raise ValueError(f"在 {image_dir} 中未找到图片文件")

    # 按考号分组图片
    kaohao_groups = {}

    for img_file in image_files:
        school_id, kaohao, index = parse_upload_key_from_filename(img_file.name)

        if not kaohao:
            print(f"警告: 无法从文件名解析考号: {img_file.name}")
            continue

        if kaohao not in kaohao_groups:
            kaohao_groups[kaohao] = {
                'school_id': school_id,
                'kaohao': kaohao,
                'image_file': img_file
            }

    # 如果指定了最大数量，只取前N个
    kaohao_list = list(kaohao_groups.keys())
    if max_count is not None and max_count > 0:
        kaohao_list = kaohao_list[:max_count]
        print(f"⚠️  限制处理数量: {max_count}")

    total = len(kaohao_list)

    print(f"📁 找到 {total} 个学生的图片")
    print(f"🌐 Webhook: {webhook_url}")
    print(f"🚀 并发线程数: {workers}")
    print("-" * 50)

    # 统计
    success_count = 0
    failed_count = 0
    results = []
    lock = Lock()

    def process_single_student(kaohao):
        """处理单个学生"""
        nonlocal success_count, failed_count
        student_data = kaohao_groups[kaohao]
        img_file = student_data['image_file']

        print(f"  处理图片: {img_file.name}")

        # 将图片转换为base64
        try:
            image_base64 = image_to_base64(img_file)
            print(f"  Base64编码完成，长度: {len(image_base64)} 字符")
        except Exception as e:
            print(f"  ❌ 图片编码失败: {e}")
            with lock:
                failed_count += 1
                results.append({
                    "kaohao": kaohao,
                    "success": False,
                    "result": None,
                    "error": f"图片编码失败: {str(e)}"
                })
            return kaohao, False

        # 创建webhook数据
        webhook_data = create_webhook_data(
            subject_id=subject_id,
            block_id=block_id,
            kaohao=kaohao,
            image_base64=image_base64,
            config=config
        )

        # 保存输入数据（用于调试，不包含完整base64以节省空间）
        input_file = os.path.join(output_dir, f"{kaohao}_input.json")
        input_debug_data = json.loads(json.dumps(webhook_data))
        # 将base64截断用于调试显示
        if input_debug_data[0]["students"][0]["files"]:
            original_b64 = input_debug_data[0]["students"][0]["files"][0]
            if original_b64.startswith("data:image/png;base64,"):
                input_debug_data[0]["students"][0]["files"][0] = original_b64[:50] + "...(truncated)"
        with open(input_file, 'w', encoding='utf-8') as f:
            json.dump(input_debug_data, f, ensure_ascii=False, indent=2)

        # 发送到webhook
        result = send_to_webhook(kaohao, webhook_data, webhook_url)

        with lock:
            if result:
                success_count += 1

                # 保存结果
                output_file = os.path.join(output_dir, f"{kaohao}_result.json")
                result_data = {
                    "kaohao": kaohao,
                    "image_file": str(img_file.name),
                    "ocr_results": {
                        "result": result.get("result", ""),
                        "webhook_response": result
                    }
                }
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(result_data, f, ensure_ascii=False, indent=2)

                # 提取结果
                ocr_result = result.get("result", "")
                results.append({
                    "kaohao": kaohao,
                    "success": True,
                    "result": ocr_result
                })
                print(f"✅ [{success_count + failed_count}/{total}] {kaohao} - 结果长度: {len(ocr_result)} 字符")
            else:
                failed_count += 1
                results.append({
                    "kaohao": kaohao,
                    "success": False,
                    "result": None
                })
                print(f"❌ [{success_count + failed_count}/{total}] {kaohao} - 失败")

        return kaohao, result is not None

    # 使用线程池并发处理
    start_time = time.time()

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(process_single_student, kaohao): kaohao for kaohao in kaohao_list}

        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                print(f"❌ 处理时出错: {e}")

    elapsed_time = time.time() - start_time

    # 打印总结
    print("\n" + "=" * 50)
    print("📊 处理完成")
    print(f"  总数: {total}")
    print(f"  ✅ 成功: {success_count}")
    print(f"  ❌ 失败: {failed_count}")
    if total > 0:
        print(f"  成功率: {success_count/total*100:.1f}%")
        print(f"  ⏱️  总耗时: {elapsed_time:.1f}秒")
        print(f"  ⚡ 平均速度: {total/elapsed_time:.2f} 个/秒")
    print("=" * 50)

    # 保存汇总结果
    summary_file = os.path.join(output_dir, "_summary.json")
    with open(summary_file, 'w', encoding='utf-8') as f:
        json.dump({
            "subject_id": subject_id,
            "block_id": block_id,
            "total": total,
            "success": success_count,
            "failed": failed_count,
            "success_rate": f"{success_count/total*100:.1f}%" if total > 0 else "N/A",
            "elapsed_time": f"{elapsed_time:.1f}s",
            "avg_speed": f"{total/elapsed_time:.2f} items/s" if elapsed_time > 0 else "N/A",
            "results": results
        }, f, ensure_ascii=False, indent=2)
    print(f"\n📄 汇总结果已保存到: {summary_file}")


def main():
    parser = argparse.ArgumentParser(
        description='测试坐标OCR脚本',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 使用示例URL测试
  python test_coordinate_ocr.py --subject_id 10023044 --block_id 25033359 --image_dir ./10023044/25033359

  # 限制处理数量
  python test_coordinate_ocr.py --subject_id 10023044 --block_id 25033359 --image_dir ./10023044/25033359 --max_count 2

  # 指定输出目录
  python test_coordinate_ocr.py --subject_id 10023044 --block_id 25033359 --image_dir ./10023044/25033359 --output_dir ./test_output
        """
    )

    parser.add_argument('--subject_id', required=True, help='科目ID')
    parser.add_argument('--block_id', required=True, help='题块ID')
    parser.add_argument('--image_dir', required=True, help='图片目录路径')
    parser.add_argument('--output_dir', default='./test_output', help='输出目录路径（默认: ./test_output）')
    parser.add_argument('--webhook_url', default=WEBHOOK_URL, help=f'Webhook URL（默认: {WEBHOOK_URL}）')
    parser.add_argument('--config', help='配置文件路径（JSON格式）')
    parser.add_argument('--workers', type=int, default=5, help='并发线程数（默认: 5）')
    parser.add_argument('--max_count', type=int, help='最大处理数量')

    args = parser.parse_args()

    # 加载配置
    config = DEFAULT_CONFIG.copy()
    if args.config:
        with open(args.config, 'r', encoding='utf-8') as f:
            user_config = json.load(f)
            config.update(user_config)

    # 执行批量处理
    batch_process_images(
        subject_id=args.subject_id,
        block_id=args.block_id,
        image_dir=args.image_dir,
        output_dir=args.output_dir,
        webhook_url=args.webhook_url,
        config=config,
        workers=args.workers,
        max_count=args.max_count
    )


if __name__ == "__main__":
    main()
