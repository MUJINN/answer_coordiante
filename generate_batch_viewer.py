#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
坐标OCR批量展示查看器生成脚本
支持多个科目/题块的结果，生成分类展示页面

用法:
    python generate_batch_viewer.py <output_dir> <result_base_dir>

示例:
    python generate_batch_viewer.py batch_viewer test_output
"""

import json
import os
import sys
import argparse
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import base64
from io import BytesIO


def base64_to_image(base64_string):
    """将base64字符串转换为PIL Image对象"""
    if base64_string.startswith('data:image/png;base64,'):
        base64_string = base64_string.replace('data:image/png;base64,', '')
    elif base64_string.startswith('data:image/jpeg;base64,'):
        base64_string = base64_string.replace('data:image/jpeg;base64,', '')

    image_data = base64.b64decode(base64_string)
    image = Image.open(BytesIO(image_data))
    return image


def load_all_results_grouped(result_dir):
    """加载所有OCR结果文件，按subject_id和block_id分组"""
    result_path = Path(result_dir)
    grouped = {}

    # 递归查找所有 *_result.json 文件
    for json_file in result_path.rglob('*_result.json'):
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                kaohao = data.get('kaohao', '')

                # 从目录名或文件中提取subject_id和block_id
                # 目录格式可能是: test_output/10023044_25033359/ 或类似
                path_parts = json_file.relative_to(result_path).parts

                subject_id = None
                block_id = None

                # 尝试从父目录名解析（格式：subjectid_blockid）
                if len(path_parts) >= 2:
                    dir_name = path_parts[-2]  # 倒数第二个部分是目录名
                    if '_' in dir_name:
                        parts = dir_name.split('_')
                        if len(parts) >= 2:
                            subject_id = parts[0]
                            block_id = parts[1]

                # 如果目录名解析失败，尝试从webhook响应中获取
                if not subject_id or not block_id:
                    webhook_response = data.get('ocr_results', {}).get('webhook_response', {})
                    subject_id = webhook_response.get('subjectId', subject_id)
                    block_id = webhook_response.get('blockId', block_id)

                if kaohao and subject_id and block_id:
                    key = f"{subject_id}_{block_id}"
                    if key not in grouped:
                        grouped[key] = {
                            'subject_id': subject_id,
                            'block_id': block_id,
                            'results': []
                        }
                    grouped[key]['results'].append({
                        'kaohao': kaohao,
                        'file': json_file,
                        'data': data
                    })
        except Exception as e:
            print(f"警告: 加载 {json_file} 失败: {e}")

    # 对每个组内的结果按考号排序
    for key in grouped:
        grouped[key]['results'].sort(key=lambda x: x['kaohao'])

    return grouped


def draw_annotations_on_image(image, key_results, font_size=24):
    """在图片上绘制标注"""
    if image.mode != 'RGB':
        image = image.convert('RGB')

    draw_image = image.copy()
    draw = ImageDraw.Draw(draw_image)

    # 尝试加载字体
    try:
        font_paths = [
            '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
            '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
            '/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc',
            '/System/Library/Fonts/PingFang.ttc',
            'C:\\Windows\\Fonts\\msyh.ttc',
            'C:\\Windows\\Fonts\\simhei.ttf',
        ]

        font = None
        for font_path in font_paths:
            if os.path.exists(font_path):
                try:
                    font = ImageFont.truetype(font_path, font_size)
                    break
                except:
                    continue

        if font is None:
            font = ImageFont.load_default()
    except:
        font = ImageFont.load_default()

    img_width, img_height = image.size

    colors = [
        '#FF0000', '#0000FF', '#00AA00', '#FF8800',
        '#8800FF', '#00AAAA', '#FF00FF', '#AAAA00',
    ]

    for i, item in enumerate(key_results):
        key = item.get('key', '')
        coord = item.get('answer_coordinate', [])

        if not coord or len(coord) != 4:
            continue

        x1 = int(coord[0] * img_width)
        y1 = int(coord[1] * img_height)
        x2 = int(coord[2] * img_width)
        y2 = int(coord[3] * img_height)

        color = colors[i % len(colors)]
        draw.rectangle([x1, y1, x2, y2], outline=color, width=3)

        # 绘制标签
        label = key
        label_x = x1
        label_y = max(0, y1 - font_size - 6)

        try:
            bbox = draw.textbbox((label_x, label_y), label, font=font)
            draw.rectangle([bbox[0]-2, bbox[1]-2, bbox[2]+2, bbox[3]+2], fill=color)
        except:
            text_width = len(label) * font_size // 2
            draw.rectangle([label_x, label_y, label_x + text_width + 4, label_y + font_size + 4], fill=color)

        draw.text((label_x + 2, label_y + 2), label, fill='white', font=font)

    return draw_image


def generate_batch_viewer_html(grouped_data, output_dir, font_size=24):
    """生成批量展示查看器HTML页面"""

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # 收集所有组的信息
    groups_list = []
    for key in sorted(grouped_data.keys()):
        groups_list.append({
            'key': key,
            'subject_id': grouped_data[key]['subject_id'],
            'block_id': grouped_data[key]['block_id'],
            'results': grouped_data[key]['results']
        })

    total_results = sum(len(g['results']) for g in grouped_data.values())

    print(f"📁 找到 {len(groups_list)} 个科目/题块组合，共 {total_results} 个结果")

    # 为每个组生成标注图片
    all_images_data = {}

    for group_info in groups_list:
        group_key = group_info['key']
        subject_id = group_info['subject_id']
        block_id = group_info['block_id']
        results = group_info['results']

        print(f"\n  处理 {subject_id} / {block_id}: {len(results)} 个结果")

        # 创建该组的图片目录
        group_images_dir = output_path / 'images' / group_key
        group_images_dir.mkdir(parents=True, exist_ok=True)

        group_data = []

        for result in results:
            kaohao = result['kaohao']
            data = result['data']

            webhook_response = data.get('ocr_results', {}).get('webhook_response', {})
            image_data = webhook_response.get('image', [])
            key_results = webhook_response.get('key_result', [])
            ocr_result = webhook_response.get('result', '')

            # 解析图片数据
            if isinstance(image_data, str):
                try:
                    image_data = json.loads(image_data)
                except:
                    continue

            if not image_data or not isinstance(image_data, list):
                continue

            base64_string = image_data[0]
            if not base64_string:
                continue

            try:
                # 转换并绘制标注
                image = base64_to_image(base64_string)
                annotated = draw_annotations_on_image(image, key_results, font_size)

                # 保存图片
                img_file = group_images_dir / f'{kaohao}.png'
                annotated.save(img_file, 'PNG')

                # 准备数据
                group_data.append({
                    'kaohao': kaohao,
                    'image': f'images/{group_key}/{kaohao}.png',
                    'image_file': data.get('image_file', ''),
                    'key_results': key_results,
                    'ocr_result': ocr_result
                })

                print(f"    ✅ {kaohao}")
            except Exception as e:
                print(f"    ❌ {kaohao}: {e}")

        all_images_data[group_key] = {
            'subject_id': subject_id,
            'block_id': block_id,
            'data': group_data
        }

    # 生成HTML
    html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>坐标OCR批量展示 - {len(groups_list)}个科目/题块</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #f5f5f5;
            padding: 20px;
        }}

        .header {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }}

        .header h1 {{
            color: #333;
            margin-bottom: 10px;
        }}

        .header .stats {{
            color: #666;
            font-size: 14px;
            margin-bottom: 15px;
        }}

        .group-tabs {{
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
            margin-bottom: 20px;
        }}

        .group-tab {{
            padding: 10px 20px;
            background: white;
            border: 2px solid #ddd;
            border-radius: 6px;
            cursor: pointer;
            transition: all 0.2s;
            font-size: 14px;
        }}

        .group-tab:hover {{
            border-color: #007bff;
        }}

        .group-tab.active {{
            background: #007bff;
            color: white;
            border-color: #007bff;
        }}

        .controls {{
            margin-top: 15px;
            display: flex;
            gap: 10px;
            align-items: center;
            flex-wrap: wrap;
        }}

        .controls input {{
            padding: 8px 12px;
            border: 1px solid #ddd;
            border-radius: 4px;
            font-size: 14px;
            width: 250px;
        }}

        .group-section {{
            display: none;
        }}

        .group-section.active {{
            display: block;
        }}

        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(450px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }}

        .card {{
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            overflow: hidden;
            transition: transform 0.2s, box-shadow 0.2s;
        }}

        .card:hover {{
            transform: translateY(-4px);
            box-shadow: 0 4px 16px rgba(0,0,0,0.15);
        }}

        .card-header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 12px 15px;
            font-weight: bold;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}

        .card-kaohao {{
            font-size: 18px;
        }}

        .card-file {{
            font-size: 12px;
            opacity: 0.8;
        }}

        .card-image {{
            width: 100%;
            text-align: center;
            background: #f8f9fa;
            padding: 10px;
        }}

        .card-image img {{
            max-width: 100%;
            height: auto;
            border-radius: 4px;
            border: 1px solid #ddd;
        }}

        .card-results {{
            padding: 15px;
        }}

        .result-item {{
            display: flex;
            align-items: center;
            padding: 8px 0;
            border-bottom: 1px solid #eee;
        }}

        .result-item:last-child {{
            border-bottom: none;
        }}

        .result-key {{
            display: inline-block;
            padding: 4px 10px;
            border-radius: 4px;
            background: #007bff;
            color: white;
            font-weight: bold;
            font-size: 12px;
            margin-right: 10px;
            min-width: 60px;
            text-align: center;
        }}

        .result-text {{
            flex: 1;
            font-size: 14px;
            color: #333;
        }}

        .result-coord {{
            font-family: monospace;
            font-size: 11px;
            color: #999;
            background: #f0f0f0;
            padding: 2px 6px;
            border-radius: 3px;
            margin-left: 8px;
        }}

        .card-ocr {{
            padding: 15px;
            border-top: 1px solid #eee;
            background: #f8f9fa;
        }}

        .card-ocr h4 {{
            font-size: 13px;
            color: #666;
            margin-bottom: 8px;
        }}

        .card-ocr pre {{
            white-space: pre-wrap;
            word-wrap: break-word;
            font-size: 12px;
            color: #333;
            line-height: 1.5;
            max-height: 100px;
            overflow-y: auto;
        }}

        .no-results {{
            text-align: center;
            padding: 40px;
            color: #999;
            font-size: 16px;
        }}

        @media (max-width: 768px) {{
            .grid {{
                grid-template-columns: 1fr;
            }}
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>📍 坐标OCR批量展示</h1>
        <div class="stats">共 {len(groups_list)} 个科目/题块组合，{total_results} 个结果</div>

        <div class="group-tabs">
"""

    # 生成分组标签页按钮
    for i, group_info in enumerate(groups_list):
        group_key = group_info['key']
        subject_id = group_info['subject_id']
        block_id = group_info['block_id']
        count = len(group_info['results'])
        active_class = 'active' if i == 0 else ''

        html_content += f"""
            <div class="group-tab {active_class}" onclick="switchGroup('{group_key}')">
                {subject_id} / {block_id} ({count}个)
            </div>
"""

    html_content += """
        </div>

        <div class="controls">
            <input type="text" id="searchInput" placeholder="搜索考号或识别内容..." onkeyup="filterCards()">
        </div>
    </div>
"""

    # 为每个组生成卡片HTML（存储在字典中）
    all_cards_html = {}
    for i, group_info in enumerate(groups_list):
        group_key = group_info['key']
        group_data = all_images_data[group_key]

        cards_html = ''
        for item in group_data['data']:
            # 生成结果列表
            results_html = ''
            if item['key_results']:
                for kr in item['key_results']:
                    coord = kr.get('answer_coordinate', [])
                    coord_str = f"[{coord[0]:.2f},{coord[1]:.2f},{coord[2]:.2f},{coord[3]:.2f}]" if coord and len(coord) == 4 else ""

                    results_html += f"""
                        <div class="result-item">
                            <span class="result-key">{kr.get('key', '')}</span>
                            <span class="result-text">{kr.get('key_ocr', '')}</span>
                            {f'<span class="result-coord">{coord_str}</span>' if coord_str else ''}
                        </div>
                    """
            else:
                results_html = '<div style="color:#999;font-size:13px;">无坐标数据</div>'

            # OCR结果（截断显示）
            ocr_text = item['ocr_result'][:150] + ('...' if len(item['ocr_result']) > 150 else '')
            ocr_text = ocr_text.replace('<', '&lt;').replace('>', '&gt;')

            cards_html += f"""
            <div class="card" data-kaohao="{item['kaohao']}" data-search="{item['kaohao']} {item['ocr_result']}">
                <div class="card-header">
                    <span class="card-kaohao">📋 考号: {item['kaohao']}</span>
                    <span class="card-file">{item['image_file']}</span>
                </div>
                <div class="card-image">
                    <img src="{item['image']}" alt="考号 {item['kaohao']}" loading="lazy">
                </div>
                <div class="card-results">
                    {results_html}
                </div>
                <div class="card-ocr">
                    <h4>完整识别结果:</h4>
                    <pre>{ocr_text}</pre>
                </div>
            </div>
"""
        all_cards_html[group_key] = cards_html

    # 生成所有组的HTML section
    for i, group_info in enumerate(groups_list):
        group_key = group_info['key']
        active_class = 'active' if i == 0 else ''
        cards_html = all_cards_html.get(group_key, '')

        html_content += f"""
    <div class="group-section {active_class}" id="group-{group_key}">
        <div class="grid" id="grid-{group_key}">
            {cards_html}
        </div>
    </div>
"""

    # 生成数据JSON
    groups_json = json.dumps({k: {'subject_id': v['subject_id'], 'block_id': v['block_id'], 'count': len(v['results'])}
                                     for k, v in grouped_data.items()}, ensure_ascii=False)

    html_content += f"""
    <script>
        const groupsData = {groups_json};
        let currentGroup = '{groups_list[0]['key'] if groups_list else ''}';

        function switchGroup(groupKey) {{
            // 隐藏所有组
            document.querySelectorAll('.group-section').forEach(el => el.classList.remove('active'));
            document.querySelectorAll('.group-tab').forEach(el => el.classList.remove('active'));

            // 显示选中的组
            document.getElementById('group-' + groupKey).classList.add('active');
            event.target.classList.add('active');

            currentGroup = groupKey;

            // 重新应用搜索过滤
            filterCards();
        }}

        function filterCards() {{
            const searchInput = document.getElementById('searchInput').value.toLowerCase();
            const currentGrid = document.getElementById('grid-' + currentGroup);

            if (!currentGrid) return;

            const cards = currentGrid.querySelectorAll('.card');

            cards.forEach(card => {{
                const searchData = card.getAttribute('data-search').toLowerCase();
                if (searchData.includes(searchInput)) {{
                    card.style.display = '';
                }} else {{
                    card.style.display = 'none';
                }}
            }});

            // 更新显示统计
            const visibleCards = currentGrid.querySelectorAll('.card:not([style*="display: none"])').length;
            const totalCards = cards.length;

            const statsDiv = document.querySelector('.stats');
            if (searchInput) {{
                statsDiv.textContent = `显示 {{当前组}} {{visible}} / {{total}} 个结果`;
                statsDiv.textContent = statsDiv.textContent.replace('{{当前组}}', groupsData[currentGroup].subject_id + '/' + groupsData[currentGroup].block_id);
                statsDiv.textContent = statsDiv.textContent.replace('{{visible}}', visible);
                statsDiv.textContent = statsDiv.textContent.replace('{{total}}', totalCards);
            }} else {{
                statsDiv.textContent = `共 {len(groups_list)} 个科目/题块组合，{total_results} 个结果`;
            }}
        }}
    </script>
</body>
</html>"""

    html_file = output_path / 'index.html'
    with open(html_file, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"\n✅ 批量展示查看器已生成:")
    print(f"   📁 目录: {output_dir}")
    print(f"   📄 主页: {html_file}")
    print(f"   📊 科目/题块: {len(groups_list)} 个")
    print(f"   📊 总结果: {total_results} 个")
    print(f"\n💡 使用浏览器打开 {html_file} 查看结果")
    print(f"💡 支持按科目/题块分组展示，支持搜索考号或识别内容进行筛选")


def main():
    parser = argparse.ArgumentParser(
        description='生成坐标OCR批量展示查看器',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 从test_output目录生成批量查看器（自动识别不同科目/题块）
  python generate_batch_viewer.py batch_viewer test_output

  # 指定字体大小
  python generate_batch_viewer.py batch_viewer test_output --font-size 28
        """
    )

    parser.add_argument('output_dir', help='输出目录')
    parser.add_argument('result_dir', help='OCR结果根目录（将递归查找所有*_result.json）')
    parser.add_argument('--font-size', type=int, default=24, help='标注字体大小（默认: 24）')

    args = parser.parse_args()

    # 加载所有结果（按subject_id和block_id分组）
    print("📁 加载OCR结果...")
    grouped_data = load_all_results_grouped(args.result_dir)

    if not grouped_data:
        print("❌ 错误: 未找到OCR结果文件")
        return

    # 生成查看器
    generate_batch_viewer_html(grouped_data, args.output_dir, args.font_size)


if __name__ == "__main__":
    main()
