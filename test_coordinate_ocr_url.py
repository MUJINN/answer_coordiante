#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
坐标OCR测试脚本 - URL版本
使用图片URL进行测试，避免base64过大问题

用法:
    python test_coordinate_ocr_url.py --subject_id 001 --block_id 01 --url_file urls.txt
    python test_coordinate_ocr_url.py --subject_id 001 --block_id 01 --url "https://example.com/image.png" --kaohao "12345"
"""

import argparse
import json
import os
import sys
import time
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from datetime import datetime


def create_webhook_data(subject_id, block_id, kaohao, image_url, config=None):
    """创建webhook请求数据 - 使用URL"""
    default_config = {
        'model_name': 'doubao-seed-1.8',
        'subject_name': '数学',
        'question_type': '解答题',
        'prompt': ''
    }

    if config:
        default_config.update(config)

    webhook_data = [{
        "model_name": default_config['model_name'],
        "model_names": [
            "doubao-seed-1-6-vision-250815",
            "doubao-seed-1.6-251015",
            "doubao-seed-1.8"
        ],
        "agent_id": "ocr_model_x",
        "subjectId": subject_id,
        "blockId": block_id,
        "taskKey": "",
        "key": "",
        "grade": "",
        "problem": "",
        "answer": "",
        "totalScore": 0,
        "subject_name": default_config['subject_name'],
        "question_type": default_config['question_type'],
        "prompt": default_config['prompt'],
        "students": [{
            "uploadKey": f"{subject_id}-{block_id}-{kaohao}",
            "files": [image_url],
            "kaohao": kaohao,
            "from": ""
        }]
    }]
    return webhook_data


def send_webhook_request(webhook_url, data, timeout=120):
    """发送webhook请求"""
    headers = {
        'Content-Type': 'application/json'
    }

    try:
        response = requests.post(
            webhook_url,
            headers=headers,
            json=data,
            timeout=timeout
        )
        return response
    except Exception as e:
        return None


def parse_url_file(url_file):
    """
    解析URL文件

    支持的格式:
    1. 每行一个URL: https://example.com/image1.png
    2. kaohao URL格式: 12345 https://example.com/image1.png
    3. kaohao URL filename格式: 12345 https://example.com/image1.png image1.png
    4. JSON格式: {"kaohao": "12345", "url": "https://example.com/image1.png", "filename": "image1.png"}
    """
    items = []

    with open(url_file, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            # 尝试解析为JSON
            try:
                data = json.loads(line)
                if isinstance(data, dict):
                    kaohao = data.get('kaohao', data.get('kaohao', ''))
                    url = data.get('url', data.get('url', ''))
                    filename = data.get('filename', data.get('filename', ''))
                    if kaohao and url:
                        items.append({'kaohao': str(kaohao), 'url': url, 'filename': filename})
                    continue
            except json.JSONDecodeError:
                pass

            # 解析纯文本格式
            parts = line.split()
            if len(parts) == 1:
                # 只有一个URL，生成默认kaohao
                url = parts[0]
                kaohao = f"auto_{line_num:04d}"
                items.append({'kaohao': kaohao, 'url': url, 'filename': ''})
            elif len(parts) == 2:
                # kaohao url
                kaohao = parts[0]
                url = parts[1]
                items.append({'kaohao': kaohao, 'url': url, 'filename': ''})
            elif len(parts) >= 3:
                # kaohao url filename
                kaohao = parts[0]
                url = parts[1]
                filename = parts[2]
                items.append({'kaohao': kaohao, 'url': url, 'filename': filename})

    return items


def batch_process_urls(subject_id, block_id, url_items, output_dir, webhook_url, config=None, workers=5):
    """批量处理URL"""

    # 创建带科目ID和题块ID的子目录
    output_dir = os.path.join(output_dir, f"{subject_id}_{block_id}")
    os.makedirs(output_dir, exist_ok=True)

    total = len(url_items)
    success_count = 0
    failed_count = 0
    results = []

    print(f"📁 找到 {total} 个URL")
    print(f"🌐 Webhook: {webhook_url}")
    print(f"🚀 并发线程数: {workers}")
    print("-" * 50)

    start_time = time.time()

    def process_single_url(item):
        kaohao = item['kaohao']
        url = item['url']
        filename = item.get('filename', os.path.basename(url))

        # 创建webhook数据
        webhook_data = create_webhook_data(subject_id, block_id, kaohao, url, config)

        # 保存输入数据
        input_file = os.path.join(output_dir, f'{kaohao}_input.json')
        with open(input_file, 'w', encoding='utf-8') as f:
            json.dump(webhook_data, f, ensure_ascii=False, indent=2)

        # 发送请求
        print(f"  处理URL: {filename}")
        print(f"  考号: {kaohao}")
        print(f"  URL: {url[:80]}{'...' if len(url) > 80 else ''}")

        response = send_webhook_request(webhook_url, webhook_data)

        if response and response.status_code == 200:
            result_data = response.json()
            # 保存结果
            result = {
                'kaohao': kaohao,
                'image_file': filename,
                'image_url': url,
                'ocr_results': {
                    'webhook_response': result_data[0] if isinstance(result_data, list) else result_data
                }
            }

            result_file = os.path.join(output_dir, f'{kaohao}_result.json')
            with open(result_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)

            print(f"  ✅ {kaohao} - 成功")
            return {'success': True, 'kaohao': kaohao, 'result': result}
        else:
            error_msg = "Unknown error"
            if response:
                try:
                    error_data = response.json()
                    error_msg = error_data.get('message', str(response.status_code))
                except:
                    error_msg = f"HTTP {response.status_code}"

            print(f"  ❌ {kaohao} - 失败: {error_msg}")
            return {'success': False, 'kaohao': kaohao, 'error': error_msg}

    # 使用线程池并发处理
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(process_single_url, item): item for item in url_items}

        for i, future in enumerate(as_completed(futures), 1):
            try:
                result = future.result()
                results.append(result)

                if result['success']:
                    success_count += 1
                else:
                    failed_count += 1

                print(f"❌ [{i}/{total}] {result['kaohao']} - {'成功' if result['success'] else '失败'}")

            except Exception as e:
                item = futures[future]
                kaohao = item['kaohao']
                print(f"  ❌ [{i}/{total}] {kaohao} - 异常: {e}")
                failed_count += 1
                results.append({'success': False, 'kaohao': kaohao, 'error': str(e)})

            print()

    end_time = time.time()
    elapsed_time = end_time - start_time

    # 保存汇总结果
    summary = {
        'subject_id': subject_id,
        'block_id': block_id,
        'timestamp': datetime.now().isoformat(),
        'total': total,
        'success': success_count,
        'failed': failed_count,
        'success_rate': f"{success_count/total*100:.1f}%" if total > 0 else "0%",
        'elapsed_time': f"{elapsed_time:.2f}s",
        'avg_speed': f"{total/elapsed_time:.2f} req/s" if elapsed_time > 0 else "0",
        'results': results
    }

    summary_file = os.path.join(output_dir, '_summary.json')
    with open(summary_file, 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print("=" * 50)
    print("📊 处理完成")
    print(f"  总数: {total}")
    print(f"  ✅ 成功: {success_count}")
    print(f"  ❌ 失败: {failed_count}")
    print(f"  成功率: {success_count/total*100:.1f}%" if total > 0 else "  成功率: 0%")
    print(f"  ⏱️  总耗时: {elapsed_time:.2f}秒")
    print(f"  ⚡ 平均速度: {total/elapsed_time:.2f} 个/秒" if elapsed_time > 0 else "  ⚡ 平均速度: N/A")
    print("=" * 50)
    print(f"\n📄 汇总结果已保存到: {summary_file}\n")


    return summary


def main():
    parser = argparse.ArgumentParser(
        description='测试坐标OCR - URL版本',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 从URL文件读取
  python test_coordinate_ocr_url.py --subject_id 001 --block_id 01 --url_file urls.txt

  # 直接指定单个URL
  python test_coordinate_ocr_url.py --subject_id 001 --block_id 01 --url "https://example.com/image.png" --kaohao "12345"

  # 指定输出目录
  python test_coordinate_ocr_url.py --subject_id 001 --block_id 01 --url_file urls.txt --output_dir ./test_output

  # 指定并发线程数
  python test_coordinate_ocr_url.py --subject_id 001 --block_id 01 --url_file urls.txt --workers 10

URL文件格式支持:
  1. 每行一个URL:
     https://cdn.example.com/image1.png
     https://cdn.example.com/image2.png

  2. kaohao URL格式:
     12345 https://cdn.example.com/image1.png
     12346 https://cdn.example.com/image2.png

  3. kaohao URL filename格式:
     12345 https://cdn.example.com/image1.png image1.png
     12346 https://cdn.example.com/image2.png image2.png

  4. JSON格式（每行一个JSON对象）:
     {"kaohao": "12345", "url": "https://cdn.example.com/image1.png", "filename": "image1.png"}
        """
    )

    parser.add_argument('--subject_id', required=True, help='科目ID')
    parser.add_argument('--block_id', required=True, help='题块ID')
    parser.add_argument('--url_file', help='URL文件路径（每行一个URL或 kaohao URL 格式）')
    parser.add_argument('--url', help='单个图片URL')
    parser.add_argument('--kaohao', help='考号（与--url配合使用）')
    parser.add_argument('--output_dir', default='./test_output', help='输出目录路径（默认：./test_output）')
    parser.add_argument('--webhook_url', default='https://n8n.iyunxiao.com/webhook/test/answer_coordinate',
                       help='Webhook URL')
    parser.add_argument('--config', help='配置文件路径（JSON格式）')
    parser.add_argument('--workers', type=int, default=5, help='并发线程数（默认：5）')

    args = parser.parse_args()

    # 验证参数
    if not args.url_file and not args.url:
        parser.print_help()
        print("\n❌ 错误: 必须指定 --url_file 或 --url")
        sys.exit(1)

    if args.url and not args.kaohao:
        parser.print_help()
        print("\n❌ 错误: 使用 --url 时必须指定 --kaohao")
        sys.exit(1)

    # 加载配置
    config = None
    if args.config:
        with open(args.config, 'r', encoding='utf-8') as f:
            config = json.load(f)

    # 准备URL列表
    url_items = []

    if args.url_file:
        # 从文件读取URL
        if not os.path.exists(args.url_file):
            print(f"❌ 错误: URL文件不存在: {args.url_file}")
            sys.exit(1)
        url_items = parse_url_file(args.url_file)
        if not url_items:
            print(f"❌ 错误: URL文件为空或格式不正确: {args.url_file}")
            sys.exit(1)
        print(f"📄 从文件读取到 {len(url_items)} 个URL")
    else:
        # 单个URL
        url_items = [{
            'kaohao': args.kaohao,
            'url': args.url,
            'filename': os.path.basename(args.url)
        }]

    # 批量处理
    try:
        batch_process_urls(
            subject_id=args.subject_id,
            block_id=args.block_id,
            url_items=url_items,
            output_dir=args.output_dir,
            webhook_url=args.webhook_url,
            config=config,
            workers=args.workers
        )
    except KeyboardInterrupt:
        print("\n\n⚠️  用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
