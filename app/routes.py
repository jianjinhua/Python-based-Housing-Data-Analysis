from flask import Blueprint, render_template, jsonify, request, flash, redirect, url_for, session, Response, stream_with_context
from flask_login import login_required, current_user
from app.models import House, db
from app.data import get_price_stats, get_area_stats, get_location_stats, get_dashboard_data
import json
import time
import threading
import os
import sys
import subprocess
from datetime import datetime
import traceback
from DrissionPage import WebPage  # 修改为WebPage
import re
import queue
from app import create_app
from urllib.parse import urlparse

# 添加SVM模型相关的导入
from sklearn.svm import SVR
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
import numpy as np
import pandas as pd
import joblib
import os.path

main_bp = Blueprint('main', __name__)

# 创建一个全局变量来存储爬虫状态和输出
spider_status = {
    'running': False,
    'output_queue': queue.Queue(),
    'stop_flag': False,
    'total_count': 0,
    'current_count': 0
}
# 在爬虫函数之前添加URL简化函数
def simplify_url(full_url):
    """简化URL，只保留到.html或.shtml为止"""
    if not full_url or full_url == "未知":
        return "未知"

    # 如果是相对路径，转换为绝对路径
    if full_url.startswith('//'):
        full_url = 'https:' + full_url
    elif full_url.startswith('/'):
        full_url = 'https://cs.58.com' + full_url

    # 解析URL
    parsed = urlparse(full_url)

    # 提取路径并简化
    path = parsed.path

    # 多种URL格式处理
    simplified_path = path

    # 处理 .shtml 结尾的URL
    if '.shtml' in path:
        shtml_index = path.find('.shtml')
        simplified_path = path[:shtml_index + 6]  # 包含.shtml
    # 处理 .html 结尾的URL
    elif '.html' in path:
        html_index = path.find('.html')
        simplified_path = path[:html_index + 5]  # 包含.html
    # 处理数字ID格式的URL（如：/3087843605322752x）
    elif re.search(r'/\d+[a-z]?$', path):
        # 保持原样，不截断
        simplified_path = path
    else:
        # 其他格式保持原样
        simplified_path = path

    # 构建简化后的URL
    simplified_url = f"https://{parsed.netloc}{simplified_path}"

    return simplified_url

# 爬虫函数 - 按页数爬取
def crawl_houses(pages):
    try:
        # 重置爬虫状态
        spider_status['running'] = True
        spider_status['stop_flag'] = False
        spider_status['total_count'] = pages
        spider_status['current_count'] = 0

        # 清空输出队列
        while not spider_status['output_queue'].empty():
            spider_status['output_queue'].get()

        # 输出爬虫启动信息
        spider_status['output_queue'].put("爬虫启动中...\n")
        spider_status['output_queue'].put(f"计划爬取页数: {pages}\n")

        # 创建浏览器对象
        spider_status['output_queue'].put("正在初始化浏览器...\n")
        page = WebPage()

        # 访问58同城网站
        base_url = 'https://cs.58.com/ershoufang/'

        spider_status['output_queue'].put(f"正在访问: {base_url}\n")
        page.get(base_url)

        # 等待页面加载
        time.sleep(2)

        # 存储所有房源信息
        houses_data = []
        current_page = 1
        seen_urls = set()  # 用于URL去重

        # 循环爬取直到达到目标页数
        while current_page <= pages and not spider_status['stop_flag']:
            spider_status['output_queue'].put(f"\n正在爬取第 {current_page}/{pages} 页\n")
            spider_status['current_count'] = current_page

            # 方法1：直接排除热门楼盘模块
            # 找到主列表容器，排除热门推荐部分
            main_list = page.ele('.list-main') or page.ele('.list-left') or page.ele('#esfMain')

            if not main_list:
                spider_status['output_queue'].put("未找到主列表容器\n")
                break

            # 获取所有房源元素，但排除热门楼盘相关的元素
            house_items = []

            # 方法1A：使用CSS选择器排除热门楼盘
            try:
                # 排除包含热门楼盘特征的div
                house_items = main_list.eles(
                    '.property:not([class*="HotLoupans"]):not([class*="xfrecommend"]):not([class*="recommend"])')
            except:
                pass

            # 方法1B：如果上面没找到，尝试其他选择器
            if not house_items:
                try:
                    house_items = main_list.eles('.property') or main_list.eles('.property-ex').eles('css:.property:not(.HotLoupans *)')
                    spider_status['output_queue'].put(f"使用普通选择器，找到 {len(house_items)} 个房源\n")
                except:
                    house_items = []
            # 方法2：手动过滤热门楼盘（如果仍有热门楼盘）
            if house_items:
                filtered_house_items = []
                for item in house_items:
                    try:
                        # 检查是否在热门楼盘容器内
                        hot_loupan_parent = item.parent('.HotLoupans') or item.parent('.xfrecommend')
                        if hot_loupan_parent:
                            continue  # 跳过热门楼盘

                        # 检查是否有热门楼盘的特征class
                        class_attr = item.attr('class') or ""
                        if any(keyword in class_attr for keyword in ['HotLoupans', 'xfrecommend', 'recommend']):
                            continue

                        filtered_house_items.append(item)
                    except:
                        filtered_house_items.append(item)  # 如果检查出错，保留该元素

                house_items = filtered_house_items
                spider_status['output_queue'].put(f"手动过滤后剩余 {len(house_items)} 个有效房源\n")

            if not house_items:
                spider_status['output_queue'].put("未找到房源数据，可能已到达最后一页或页面结构变化\n")
                break

            spider_status['output_queue'].put(f"本页找到 {len(house_items)} 个有效房源\n")

            # 记录本页成功解析的房源数量
            page_houses_count = 0
            # 遍历每个房源
            for i, item in enumerate(house_items):
                if spider_status['stop_flag']:
                    break

                try:
                    # 提取房源名称
                    title_ele = (item.ele('.property-content-title-name', timeout=1) or
                                 item.ele('tag:h3', timeout=1) or
                                 item.ele('css:[class*="title"]', timeout=1))
                    house_name = title_ele.text if title_ele else f"房源_{current_page}_{i}"

                    # 提取房源链接并简化
                    link_ele = item.ele('tag:a', timeout=1)
                    house_url = "未知"
                    if link_ele:
                        raw_url = link_ele.attr('href') or ""
                        house_url = simplify_url(raw_url)

                    # URL去重
                    if house_url in seen_urls:
                        spider_status['output_queue'].put(f"  - 跳过重复房源: {house_name}\n")
                        continue
                    seen_urls.add(house_url)

                    # 提取地址信息
                    address_ele = (item.ele('.property-content-info-comm-address', timeout=1) or
                                   item.ele('.property-content-info-comm-name', timeout=1) or
                                   item.ele('css:[class*="address"]', timeout=1))
                    address = address_ele.text if address_ele else "未知"

                    # 提取房屋详细信息
                    info_texts = []
                    info_container = item.ele('.property-content-info', timeout=1)
                    if info_container:
                        info_elements = info_container.eles('tag:p', timeout=1) or info_container.eles('tag:span', timeout=1)
                        if info_elements:
                            info_texts = [elem.text for elem in info_elements if elem.text]

                    house_info = " ".join(info_texts)

                    # 解析房屋信息
                    floor = "未知"
                    room_type = "未知"
                    area = "未知"
                    direction = "未知"

                    # 使用正则表达式解析房屋信息
                    if house_info:
                        # 解析户型 (如: 3室2厅2卫)
                        room_pattern = r'(\d+室\d*厅*\d*卫*)'
                        room_match = re.search(room_pattern, house_info)
                        room_type = room_match.group(1) if room_match else "未知"

                        # 解析面积 (如: 129㎡)
                        area_pattern = r'(\d+(?:\.\d+)?)\s*㎡'
                        area_match = re.search(area_pattern, house_info)
                        area = area_match.group(1) + "㎡" if area_match else "未知"

                        # 解析朝向 (如: 南北)
                        direction_pattern = r'(南北|东西|东南|西南|东北|西北|东|南|西|北)'
                        direction_match = re.search(direction_pattern, house_info)
                        direction = direction_match.group(1) if direction_match else "未知"

                        # 解析楼层 (如: 低层(共7层))
                        floor_pattern = r'([高|中|低|顶]层\(共\d+层\))'
                        floor_match = re.search(floor_pattern, house_info)
                        if floor_match:
                            floor = floor_match.group(1)
                        else:
                            # 尝试其他楼层格式
                            floor_pattern2 = r'(\w+层)'
                            floor_match2 = re.search(floor_pattern2, house_info)
                            floor = floor_match2.group(1) if floor_match2 else "未知"

                    # 提取房屋标签
                    tags = "无标签"
                    tag_elements = item.eles('.property-content-info-tag', timeout=1) or item.eles('css:[class*="tag"]', timeout=1)
                    if tag_elements:
                        tags = " ".join([tag.text for tag in tag_elements if tag.text])

                    # 提取价格信息
                    total_price = "未知"
                    unit_price = "未知"

                    total_price_ele = (item.ele('.property-price-total-num', timeout=1) or
                                       item.ele('css:[class*="price"]', timeout=1) or
                                       item.ele('css:[class*="total"]', timeout=1))
                    if total_price_ele:
                        total_price = total_price_ele.text + "万"

                    unit_price_ele = (item.ele('.property-price-average', timeout=1) or
                                      item.ele('css:[class*="unit"]', timeout=1) or
                                      item.ele('css:[class*="average"]', timeout=1))
                    if unit_price_ele:
                        unit_price = unit_price_ele.text

                    # 创建房源对象
                    house = {
                        'house_name': house_name,
                        'house_url': house_url,
                        'address': address,
                        'floor': floor,
                        'room_type': room_type,
                        'area': area,
                        'direction': direction,
                        'tags': tags,
                        'total_price': total_price,
                        'unit_price': unit_price,
                        'crawl_time': datetime.now()
                    }

                    houses_data.append(house)
                    page_houses_count += 1  # 计数本页成功解析的房源
                    spider_status['output_queue'].put(f"  - 已解析: {house_name}\n")
                    spider_status['output_queue'].put(f"    简化链接: {house_url}\n")

                except Exception as e:
                    spider_status['output_queue'].put(f"  - 解析房源时出错: {str(e)}\n")

            # 插入提示：此页保存XX条数据
            spider_status['output_queue'].put(f"\n*** 此页成功保存 {page_houses_count} 条房源数据 ***\n")

            # 尝试翻到下一页
            try:
                # 多种方式查找下一页按钮
                next_selectors = [
                    'text:下一页',
                    '.next',
                    '.page-next',
                    'a:contains(下一页)',
                    '[class*="next"]',
                    'a[href*="pn"]'
                ]

                next_page = None
                for selector in next_selectors:
                    try:
                        next_page = page.ele(selector, timeout=1)
                        if next_page:
                            break
                    except:
                        continue

                if not next_page:
                    spider_status['output_queue'].put("未找到下一页按钮，可能已到达最后一页\n")
                    break

                # 检查下一页按钮是否可用
                class_attr = next_page.attr('class') or ""
                style_attr = next_page.attr('style') or ""

                if 'disabled' in class_attr or 'none' in style_attr:
                    spider_status['output_queue'].put("已到达最后一页\n")
                    break

                spider_status['output_queue'].put("点击下一页...\n")
                next_page.click()

                # 等待页面加载完成
                time.sleep(3)
                current_page += 1

            except Exception as e:
                spider_status['output_queue'].put(f"翻页失败: {str(e)}\n")
                # 尝试直接构造URL翻页
                try:
                    next_page_url = f"{base_url}pn{current_page + 1}/"
                    spider_status['output_queue'].put(f"尝试直接访问: {next_page_url}\n")
                    page.get(next_page_url)
                    time.sleep(2)
                    current_page += 1
                except:
                    spider_status['output_queue'].put("所有翻页方式都失败，停止爬取\n")
                    break

        # 关闭浏览器
        page.quit()

        # 保存数据到数据库
        if houses_data:
            spider_status['output_queue'].put(f"\n爬取完成，共获取 {len(houses_data)} 条房源数据，正在保存到数据库...\n")

            # 导入Flask应用
            app = create_app()

            # 使用应用上下文
            with app.app_context():
                saved_count = 0
                for house_data in houses_data:
                    try:
                        # 创建House对象
                        house = House(
                            house_name=house_data['house_name'],
                            house_url=house_data['house_url'],
                            address=house_data['address'],
                            floor=house_data['floor'],
                            room_type=house_data['room_type'],
                            area=house_data['area'],
                            direction=house_data['direction'],
                            tags=house_data['tags'],
                            total_price=house_data['total_price'],
                            unit_price=house_data['unit_price'],
                            crawl_time=datetime.now()
                        )
                        db.session.add(house)
                        saved_count += 1
                    except Exception as e:
                        spider_status['output_queue'].put(f"保存单条数据失败: {str(e)}\n")
                        continue

                try:
                    db.session.commit()
                    spider_status['output_queue'].put(f"成功保存 {saved_count} 条数据到数据库\n")
                except Exception as e:
                    db.session.rollback()
                    spider_status['output_queue'].put(f"数据库提交失败: {str(e)}\n")
        else:
            spider_status['output_queue'].put("\n未获取到任何房源数据\n")

        spider_status['output_queue'].put(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 爬虫任务完成\n")
        page.quit()

    except Exception as e:
        error_msg = f"爬虫运行出错: {str(e)}\n{traceback.format_exc()}"
        spider_status['output_queue'].put(error_msg)

    finally:
        # 标记爬虫已停止
        spider_status['running'] = False


# 数据管理页面路由
@main_bp.route('/data_management')
@login_required
def data_management():
    # 获取最新的数据更新时间
    latest_house = House.query.order_by(House.crawl_time.desc()).first()
    last_update_time = latest_house.crawl_time if latest_house else None

    # 获取数据总量
    total_houses = House.query.count()

    return render_template('data_management.html',
                           last_update_time=last_update_time,
                           total_houses=total_houses,
                           spider_running=spider_status['running'])


# 启动爬虫的路由
@main_bp.route('/start_spider', methods=['POST'])
@login_required
def start_spider():
    if spider_status['running']:
        flash('爬虫已经在运行中', 'warning')
        return redirect(url_for('main.data_management'))

    pages = int(request.form.get('pages', 5))  # 获取页数参数，默认5页

    # 启动爬虫线程
    spider_thread = threading.Thread(target=crawl_houses, args=(pages,))
    spider_thread.daemon = True
    spider_thread.start()

    flash(f'爬虫已启动，计划爬取 {pages} 页数据，请在下方查看进度', 'success')
    return redirect(url_for('main.data_management'))


# 停止爬虫的路由
@main_bp.route('/stop_spider', methods=['POST'])
@login_required
def stop_spider():
    if not spider_status['running']:
        flash('没有正在运行的爬虫', 'warning')
        return redirect(url_for('main.data_management'))

    # 设置停止标志
    spider_status['stop_flag'] = True
    flash('已发送停止信号，爬虫将在完成当前任务后停止', 'info')
    return redirect(url_for('main.data_management'))


# 获取爬虫输出的API
@main_bp.route('/api/spider_output')
@login_required
def api_spider_output():
    # 获取所有输出
    output = []
    while not spider_status['output_queue'].empty():
        output.append(spider_status['output_queue'].get())

    # 获取进度信息
    progress = {
        'running': spider_status['running'],
        'total': spider_status['total_count'],
        'current': spider_status['current_count'],
        'percent': int(spider_status['current_count'] / max(1, spider_status['total_count']) * 100)
    }

    return jsonify({
        'output': ''.join(output),
        'progress': progress
    })

@main_bp.route('/')
def index():
    return render_template('index.html')

@main_bp.route('/dashboard')
@login_required
def dashboard():
    dashboard_data = get_dashboard_data()
    return render_template('dashboard.html', data=dashboard_data)

@main_bp.route('/analysis/price')
@login_required
def price_analysis():
    price_stats = get_price_stats()
    return render_template('analysis/price.html', stats=price_stats)

@main_bp.route('/analysis/area')
@login_required
def area_analysis():
    area_stats = get_area_stats()
    return render_template('analysis/area.html', stats=area_stats)

@main_bp.route('/analysis/location')
@login_required
def location_analysis():
    # 获取所有标签
    all_tags = {}
    for house in House.query.all():
        if house.tags:
            try:
                # 尝试解析JSON格式的标签
                tags = json.loads(house.tags)
                for tag in tags:
                    tag = tag.strip()
                    if tag:
                        all_tags[tag] = all_tags.get(tag, 0) + 1
            except json.JSONDecodeError:
                # 如果JSON解析失败，尝试使用逗号分割
                tags = house.tags.split(',')
                for tag in tags:
                    tag = tag.strip()
                    if tag:
                        all_tags[tag] = all_tags.get(tag, 0) + 1
    
    # 只保留出现频率最高的30个标签
    sorted_tags = dict(sorted(all_tags.items(), key=lambda x: x[1], reverse=True)[:30])
    
    stats = {
        'tags_count': sorted_tags
    }
    
    return render_template('analysis/location.html', stats=stats)

@main_bp.route('/api/houses')
@login_required
def api_houses():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    
    pagination = House.query.paginate(page=page, per_page=per_page, error_out=False)
    houses = pagination.items
    
    return jsonify({
        'total': pagination.total,
        'pages': pagination.pages,
        'current_page': pagination.page,
        'houses': [{
            'id': h.id,
            'house_name': h.house_name,
            'house_url': h.house_url,
            'address': h.address,
            'floor': h.floor,  # 添加楼层信息
            'room_type': h.room_type,
            'area': h.area,
            'direction': h.direction,
            'total_price': h.total_price,
            'unit_price': h.unit_price
        } for h in houses]
    })

@main_bp.route('/api/price_stats')
@login_required
def api_price_stats():
    return jsonify(get_price_stats())

@main_bp.route('/api/area_stats')
@login_required
def api_area_stats():
    return jsonify(get_area_stats())

@main_bp.route('/api/location_stats')
@login_required
def api_location_stats():
    return jsonify(get_location_stats())

@main_bp.route('/api/tags_stats')
@login_required
def api_tags_stats():
    from app.data import get_tags_stats
    return jsonify(get_tags_stats())

# 添加数据查询功能
@main_bp.route('/search_houses')
@login_required
def search_houses():
    keyword = request.args.get('keyword', '')
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    query = House.query
    if keyword:
        query = query.filter(
            db.or_(
                House.house_name.contains(keyword),
                House.address.contains(keyword),
                House.room_type.contains(keyword)
            )
        )
    
    pagination = query.order_by(House.id.desc()).paginate(page=page, per_page=per_page)
    houses = pagination.items
    
    # 预处理数据，确保数值字段是浮点数类型
    for house in houses:
        try:
            if house.area is not None:
                house.area = float(house.area)
            if house.total_price is not None:
                house.total_price = float(house.total_price)
            if house.unit_price is not None:
                house.unit_price = float(house.unit_price)
            # 不再生成URL，直接使用数据库中的house_url字段
        except (ValueError, TypeError):
            # 如果转换失败，保持原样
            pass
    
    return render_template(
        'search_houses.html',
        houses=houses,
        pagination=pagination,
        keyword=keyword
    )

# 清空数据的路由
@main_bp.route('/clear_data', methods=['POST'])
@login_required
def clear_data():
    try:
        # 删除所有房源数据
        House.query.delete()
        db.session.commit()
        flash('数据已成功清空！', 'success')
        return redirect(url_for('main.data_management'))
    except Exception as e:
        db.session.rollback()
        flash(f'清空数据时出错: {str(e)}', 'danger')
        return redirect(url_for('main.data_management'))

@main_bp.route('/debug/tags')
@login_required
def debug_tags():
    from app.models import House
    import json
    
    # 统计各标签出现次数
    tag_counts = {}
    houses = House.query.all()
    
    for house in houses:
        if house.tags:
            try:
                tags = json.loads(house.tags)
                for tag in tags:
                    if tag in tag_counts:
                        tag_counts[tag] += 1
                    else:
                        tag_counts[tag] = 1
            except Exception as e:
                continue
    
    # 返回JSON格式的标签统计
    return jsonify({
        'total_houses': len(houses),
        'houses_with_tags': sum(1 for h in houses if h.tags),
        'unique_tags': len(tag_counts),
        'tag_counts': tag_counts
    })

# 添加预测模型训练和保存函数
def train_price_prediction_model():
    try:
        # 创建Flask应用上下文
        app = create_app()
        with app.app_context():
            # 获取所有房源数据
            houses = House.query.all()

            # 检查是否有足够的数据
            if len(houses) < 50:
                return False, "训练数据不足，至少需要50条房源数据"

            # 准备训练数据
            X = []
            y = []

            for house in houses:
                # 使用清洗方法获取数值数据
                area = house.get_numeric_area()
                total_price = house.get_numeric_total_price()
                cleaned_floor = house.get_cleaned_floor()

                # 跳过缺失关键数据的记录
                if not area or not total_price:
                    continue

                # 特征: 面积、房型(提取数字)、朝向(编码)、楼层(编码)
                features = []

                # 添加面积特征 - 使用清洗后的数值
                features.append(float(area))

                # 提取房型中的室数
                room_count = 0
                if house.room_type:
                    match = re.search(r'(\d+)室', house.room_type)
                    if match:
                        room_count = int(match.group(1))
                features.append(room_count)

                # 朝向编码 (简单处理，可以根据实际情况扩展)
                direction_code = 0
                if house.direction:
                    if '东' in house.direction:
                        direction_code += 1
                    if '南' in house.direction:
                        direction_code += 2
                    if '西' in house.direction:
                        direction_code += 4
                    if '北' in house.direction:
                        direction_code += 8
                features.append(direction_code)

                # 楼层编码 - 使用清洗后的楼层数据
                floor_code = 0
                if cleaned_floor:
                    if '低' in cleaned_floor:
                        floor_code = 1
                    elif '中' in cleaned_floor:
                        floor_code = 2
                    elif '高' in cleaned_floor:
                        floor_code = 3
                    # 可以添加更多楼层类型的判断
                    elif '顶层' in cleaned_floor:
                        floor_code = 4
                    elif '底层' in cleaned_floor:
                        floor_code = 0
                features.append(floor_code)

                # 添加到训练数据 - 使用清洗后的总价
                X.append(features)
                y.append(float(total_price))

            # 检查是否有足够的有效数据
            if len(X) < 30:
                return False, f"有效数据不足，只有 {len(X)} 条有效记录，至少需要30条"

            # 转换为numpy数组
            X = np.array(X)
            y = np.array(y)

            # 划分训练集和测试集
            X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

            # 标准化特征
            scaler = StandardScaler()
            X_train_scaled = scaler.fit_transform(X_train)
            X_test_scaled = scaler.transform(X_test)

            # 训练SVM模型
            svm_model = SVR(kernel='rbf', C=100, gamma=0.1, epsilon=.1)
            svm_model.fit(X_train_scaled, y_train)

            # 评估模型
            train_score = svm_model.score(X_train_scaled, y_train)
            test_score = svm_model.score(X_test_scaled, y_test)

            # 保存模型和缩放器
            model_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'models')
            if not os.path.exists(model_dir):
                os.makedirs(model_dir)

            joblib.dump(svm_model, os.path.join(model_dir, 'price_prediction_model.pkl'))
            joblib.dump(scaler, os.path.join(model_dir, 'price_prediction_scaler.pkl'))

            return True, {
                'train_score': round(train_score, 4),
                'test_score': round(test_score, 4),
                'train_samples': len(X_train),
                'test_samples': len(X_test),
                'total_features': len(X[0]) if len(X) > 0 else 0,
                'feature_names': ['面积(㎡)', '房间数', '朝向编码', '楼层编码']
            }
    except Exception as e:
        return False, f"模型训练失败: {str(e)}"


# 添加预测函数
def predict_house_price(area, room_count, direction, floor):
    try:
        # 模型文件路径
        model_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'models')
        model_path = os.path.join(model_dir, 'price_prediction_model.pkl')
        scaler_path = os.path.join(model_dir, 'price_prediction_scaler.pkl')

        # 检查模型文件是否存在
        if not os.path.exists(model_path) or not os.path.exists(scaler_path):
            return False, "预测模型不存在，请先训练模型"

        # 加载模型和缩放器
        model = joblib.load(model_path)
        scaler = joblib.load(scaler_path)

        # 准备特征 - 注意这里的参数顺序要与训练时一致
        features = np.array([[float(area), int(room_count), int(direction), int(floor)]])

        # 标准化特征
        features_scaled = scaler.transform(features)

        # 预测价格
        predicted_price = model.predict(features_scaled)[0]

        return True, round(predicted_price, 2)
    except Exception as e:
        return False, f"预测失败: {str(e)}"

# 添加预测页面路由
@main_bp.route('/prediction')
@login_required
def price_prediction():
    # 检查模型是否存在
    model_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'models')
    model_path = os.path.join(model_dir, 'price_prediction_model.pkl')
    model_exists = os.path.exists(model_path)

    # 获取数据统计信息
    stats = {
        'area': {
            'min': 0,
            'max': 0,
            'avg': 0
        },
        'room_counts': {},
        'direction_options': [
            {'value': 0, 'label': '其他'},
            {'value': 2, 'label': '朝南'},
            {'value': 1, 'label': '朝东'},
            {'value': 4, 'label': '朝西'},
            {'value': 8, 'label': '朝北'},
            {'value': 3, 'label': '东南'},
            {'value': 6, 'label': '西南'},
            {'value': 10, 'label': '南北'}
        ],
        'floor_options': [
            {'value': 0, 'label': '其他'},
            {'value': 1, 'label': '低楼层'},
            {'value': 2, 'label': '中楼层'},
            {'value': 3, 'label': '高楼层'}
        ]
    }

    try:
        app = create_app()
        with app.app_context():
            # 使用清洗后的数据计算统计信息
            valid_houses = [h for h in House.query.all() if h.get_numeric_area() and h.get_numeric_total_price()]

            if valid_houses:
                areas = [h.get_numeric_area() for h in valid_houses]
                stats['area'] = {
                    'min': round(min(areas), 2),
                    'max': round(max(areas), 2),
                    'avg': round(sum(areas) / len(areas), 2)
                }

            # 房型统计
            room_counts = {}
            for house in valid_houses:
                if house.room_type:
                    match = re.search(r'(\d+)室', house.room_type)
                    if match:
                        room_count = int(match.group(1))
                        room_counts[room_count] = room_counts.get(room_count, 0) + 1

            if room_counts:
                stats['room_counts'] = dict(sorted(room_counts.items()))

    except Exception as e:
        print(f"获取统计数据时出错: {str(e)}")

    return render_template('prediction.html', model_exists=model_exists, stats=stats)

# 添加训练模型的API
@main_bp.route('/api/train_model', methods=['POST'])
@login_required
def api_train_model():
    success, result = train_price_prediction_model()
    
    if success:
        return jsonify({
            'success': True,
            'message': '模型训练成功',
            'data': result
        })
    else:
        return jsonify({
            'success': False,
            'message': result
        })

# 添加预测API
@main_bp.route('/api/predict_price', methods=['POST'])
@login_required
def api_predict_price():
    # 获取请求参数
    area = request.form.get('area', 0)
    room_count = request.form.get('room_count', 0)
    direction = request.form.get('direction', 0)
    floor = request.form.get('floor', 0)
    
    # 验证参数
    try:
        area = float(area)
        room_count = int(room_count)
        direction = int(direction)
        floor = int(floor)
    except ValueError:
        return jsonify({
            'success': False,
            'message': '参数格式错误'
        })
    
    # 调用预测函数
    success, result = predict_house_price(area, room_count, direction, floor)
    
    if success:
        return jsonify({
            'success': True,
            'predicted_price': round(result, 2)
        })
    else:
        return jsonify({
            'success': False,
            'message': result
        })

@main_bp.route('/analysis/features')
@login_required
def feature_analysis():
    """房屋特征分析页面"""
    from app.data import get_feature_analysis
    feature_stats = get_feature_analysis()
    return render_template('analysis/features.html', stats=feature_stats)

@main_bp.route('/api/feature_stats')
@login_required
def api_feature_stats():
    """房屋特征分析API"""
    from app.data import get_feature_analysis
    return jsonify(get_feature_analysis())