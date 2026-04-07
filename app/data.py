from app.models import House
from app import db
import pandas as pd
import numpy as np
import re
import json


def clean_price(price_str):
    """清洗价格数据，提取数字部分"""
    if not price_str or price_str == '未知':
        return None
    # 移除"万"字和其他非数字字符，保留小数点和数字
    match = re.search(r'(\d+(\.\d+)?)', price_str)
    if match:
        return float(match.group(1))
    return None


def clean_unit_price(price_str):
    """清洗单价数据，提取数字部分"""
    if not price_str or price_str == '未知':
        return None
    # 单价通常包含"元/㎡"等文字，需要提取纯数字
    match = re.search(r'(\d+(,\d+)*(\.\d+)?)', price_str)
    if match:
        # 移除逗号
        price_num = match.group(1).replace(',', '')
        return float(price_num)
    return None


def clean_area(area_str):
    """清洗面积数据，提取数字部分"""
    if not area_str or area_str == '未知':
        return None
    match = re.search(r'(\d+(\.\d+)?)', area_str)
    if match:
        return float(match.group(1))
    return None


def get_price_stats():
    """获取价格统计数据"""
    houses = House.query.all()

    # 转换为DataFrame进行数据分析
    df = pd.DataFrame([{
        'total_price': clean_price(h.total_price),
        'unit_price': clean_unit_price(h.unit_price),
        'area': clean_area(h.area),
        'room_type': h.room_type,
        'direction': h.direction,
        'floor': h.floor,
        'address': h.address
    } for h in houses])

    # 过滤掉无效数据
    df = df.dropna(subset=['total_price', 'unit_price'])

    if len(df) == 0:
        return {
            'avg_total_price': 0,
            'avg_unit_price': 0,
            'max_total_price': 0,
            'min_total_price': 0,
            'price_distribution': {},
            'unit_price_distribution': {}
        }

    # 计算统计数据
    stats = {
        'avg_total_price': round(df['total_price'].mean(), 2),
        'avg_unit_price': round(df['unit_price'].mean(), 2),
        'max_total_price': round(df['total_price'].max(), 2),
        'min_total_price': round(df['total_price'].min(), 2),
        'price_distribution': df['total_price'].value_counts(bins=10).to_dict(),
        'unit_price_distribution': df['unit_price'].value_counts(bins=10).to_dict()
    }

    return stats


def get_area_stats():
    """获取面积统计数据"""
    houses = House.query.all()

    # 转换为DataFrame进行数据分析
    df = pd.DataFrame([{
        'area': clean_area(h.area),
        'room_type': h.room_type
    } for h in houses])

    # 过滤掉无效数据
    df = df.dropna(subset=['area'])

    if len(df) == 0:
        return {
            'avg_area': 0,
            'max_area': 0,
            'min_area': 0,
            'area_distribution': {},
            'room_type_distribution': {}
        }

    # 计算统计数据
    stats = {
        'avg_area': round(df['area'].mean(), 2),
        'max_area': round(df['area'].max(), 2),
        'min_area': round(df['area'].min(), 2),
        'area_distribution': df['area'].value_counts(bins=10).to_dict(),
        'room_type_distribution': df['room_type'].value_counts().head(10).to_dict()
    }

    return stats


def get_location_stats():
    """获取位置统计数据"""
    houses = House.query.all()

    # 转换为DataFrame进行数据分析
    df = pd.DataFrame([{
        'address': h.address,
        'total_price': clean_price(h.total_price),
        'unit_price': clean_unit_price(h.unit_price)
    } for h in houses])

    # 过滤掉无效数据
    df = df.dropna(subset=['total_price', 'unit_price'])

    if len(df) == 0:
        return {
            'district_avg_price': {},
            'district_count': {}
        }

    # 提取区域信息 - 根据58同城的地址格式调整
    def extract_district(address):
        if not address or address == '未知':
            return '未知'
        # 58同城地址通常格式：区域 小区名 等
        parts = address.split()
        return parts[0] if parts else '未知'

    df['district'] = df['address'].apply(extract_district)

    # 计算各区域均价
    district_avg_price = df.groupby('district')['unit_price'].mean().round(2).to_dict()
    district_count = df.groupby('district').size().to_dict()

    stats = {
        'district_avg_price': district_avg_price,
        'district_count': district_count
    }

    return stats


def get_tags_stats():
    """获取房源标签统计数据"""
    houses = House.query.all()

    # 统计各标签出现次数
    tag_counts = {}
    for house in houses:
        if house.tags and house.tags != '无标签':
            try:
                # 58同城的标签可能是空格分隔的文本
                if house.tags.startswith('['):
                    tags = json.loads(house.tags)
                else:
                    tags = house.tags.split()

                for tag in tags:
                    tag = tag.strip()
                    if tag and tag != '无标签':
                        if tag in tag_counts:
                            tag_counts[tag] += 1
                        else:
                            tag_counts[tag] = 1
            except:
                # 如果解析失败，尝试简单分割
                tags = house.tags.split()
                for tag in tags:
                    tag = tag.strip()
                    if tag and tag != '无标签':
                        if tag in tag_counts:
                            tag_counts[tag] += 1
                        else:
                            tag_counts[tag] = 1

    # 按出现次数排序
    sorted_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)

    # 取前30个最常见的标签
    top_tags = sorted_tags[:30] if len(sorted_tags) > 30 else sorted_tags

    # 准备返回数据
    tags_data = {
        'labels': [tag[0] for tag in top_tags],
        'counts': [tag[1] for tag in top_tags],
    }

    return tags_data


def get_dashboard_data():
    """获取仪表盘数据"""
    from app.models import House
    from sqlalchemy import func

    # 获取基本统计数据
    total_houses = House.query.count()

    # 计算平均价格和面积（需要转换数值）
    houses_with_price = House.query.filter(
        House.total_price != '未知',
        House.unit_price != '未知'
    ).all()

    if houses_with_price:
        total_prices = [clean_price(h.total_price) for h in houses_with_price if clean_price(h.total_price)]
        unit_prices = [clean_unit_price(h.unit_price) for h in houses_with_price if clean_unit_price(h.unit_price)]
        areas = [clean_area(h.area) for h in houses_with_price if clean_area(h.area)]

        avg_price = round(sum(total_prices) / len(total_prices), 2) if total_prices else 0
        avg_unit_price = round(sum(unit_prices) / len(unit_prices), 2) if unit_prices else 0
        avg_area = round(sum(areas) / len(areas), 2) if areas else 0
    else:
        avg_price = avg_unit_price = avg_area = 0

    # 获取户型分布
    room_type_counts = {}
    for room_type, count in db.session.query(House.room_type, func.count(House.id)).group_by(House.room_type).all():
        room_type_counts[room_type or '未知'] = count

    # 获取朝向分布
    direction_counts = {}
    for direction, count in db.session.query(House.direction, func.count(House.id)).group_by(House.direction).all():
        direction_counts[direction or '未知'] = count

    # 获取楼层分布
    floor_counts = {}
    for floor, count in db.session.query(House.floor, func.count(House.id)).group_by(House.floor).all():
        floor_counts[floor or '未知'] = count

    # 获取标签分布
    tag_counts = {}
    houses = House.query.all()
    for house in houses:
        if house.tags and house.tags != '无标签':
            try:
                if house.tags.startswith('['):
                    tags = json.loads(house.tags)
                else:
                    tags = house.tags.split()

                for tag in tags:
                    tag = tag.strip()
                    if tag and tag != '无标签':
                        if tag in tag_counts:
                            tag_counts[tag] += 1
                        else:
                            tag_counts[tag] = 1
            except:
                tags = house.tags.split()
                for tag in tags:
                    tag = tag.strip()
                    if tag and tag != '无标签':
                        if tag in tag_counts:
                            tag_counts[tag] += 1
                        else:
                            tag_counts[tag] = 1

    # 按出现次数排序并取前15个
    sorted_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)
    top_tags = sorted_tags[:15] if len(sorted_tags) > 15 else sorted_tags

    tags_stats = {
        'labels': [tag[0] for tag in top_tags],
        'counts': [tag[1] for tag in top_tags],
    }

    # 返回完整的仪表盘数据
    return {
        'total_houses': total_houses,
        'avg_price': avg_price,
        'avg_unit_price': avg_unit_price,
        'avg_area': avg_area,
        'room_type_counts': room_type_counts,
        'direction_counts': direction_counts,
        'floor_counts': floor_counts,
        'tags_stats': tags_stats
    }


def get_feature_analysis():
    """分析房屋特征与价格的关系"""
    from app.models import House
    import pandas as pd
    import numpy as np

    # 获取所有房源数据
    houses = House.query.all()

    # 准备数据
    data = []
    for house in houses:
        # 使用清洗函数获取数值
        area = clean_area(house.area)
        total_price = clean_price(house.total_price)
        unit_price = clean_unit_price(house.unit_price)

        if area and total_price and unit_price:
            # 提取房型中的室数
            room_count = 0
            if house.room_type:
                match = re.search(r'(\d+)室', house.room_type)
                if match:
                    room_count = int(match.group(1))

            # 朝向分类
            direction_type = "其他"
            if house.direction:
                if '南' in house.direction:
                    if '北' in house.direction:
                        direction_type = "南北通透"
                    else:
                        direction_type = "朝南"
                elif '东' in house.direction:
                    direction_type = "朝东"
                elif '西' in house.direction:
                    direction_type = "朝西"
                elif '北' in house.direction:
                    direction_type = "朝北"

            # 楼层分类
            floor_type = "其他"
            if house.floor:
                if '低' in house.floor:
                    floor_type = "低楼层"
                elif '中' in house.floor:
                    floor_type = "中楼层"
                elif '高' in house.floor:
                    floor_type = "高楼层"

            data.append({
                'area': float(area),
                'total_price': float(total_price),
                'unit_price': float(unit_price),
                'room_count': room_count,
                'direction': direction_type,
                'floor': floor_type
            })

    if not data:
        return {
            'success': False,
            'message': '没有足够的数据进行分析'
        }

    # 转换为DataFrame进行分析
    df = pd.DataFrame(data)

    # 1. 房型与均价分析
    room_price = df.groupby('room_count').agg({
        'total_price': ['mean', 'median', 'count'],
        'unit_price': ['mean', 'median']
    }).reset_index()
    room_price.columns = ['room_count', 'avg_price', 'median_price', 'count', 'avg_unit_price', 'median_unit_price']
    room_price = room_price.sort_values('room_count').to_dict('records')

    # 2. 朝向与均价分析
    direction_price = df.groupby('direction').agg({
        'total_price': ['mean', 'median', 'count'],
        'unit_price': ['mean', 'median']
    }).reset_index()
    direction_price.columns = ['direction', 'avg_price', 'median_price', 'count', 'avg_unit_price', 'median_unit_price']
    direction_price = direction_price.sort_values('avg_price', ascending=False).to_dict('records')

    # 3. 楼层与均价分析
    floor_price = df.groupby('floor').agg({
        'total_price': ['mean', 'median', 'count'],
        'unit_price': ['mean', 'median']
    }).reset_index()
    floor_price.columns = ['floor', 'avg_price', 'median_price', 'count', 'avg_unit_price', 'median_unit_price']
    floor_price = floor_price.sort_values('avg_price', ascending=False).to_dict('records')

    # 4. 面积区间分析 - 修复这部分
    # 定义面积区间
    area_bins = [0, 50, 70, 90, 110, 130, 150, 200, float('inf')]
    area_labels = ['<50㎡', '50-70㎡', '70-90㎡', '90-110㎡', '110-130㎡', '130-150㎡', '150-200㎡', '>200㎡']

    df['area_range'] = pd.cut(df['area'], bins=area_bins, labels=area_labels)

    # 分组计算统计量
    area_grouped = df.groupby('area_range').agg({
        'total_price': ['mean', 'median', 'count'],
        'unit_price': ['mean', 'median']
    }).reset_index()

    # 重命名列
    area_grouped.columns = ['area_range', 'avg_price', 'median_price', 'count', 'avg_unit_price', 'median_unit_price']

    # 处理可能的NaN值
    area_grouped = area_grouped.fillna({
        'avg_price': 0,
        'median_price': 0,
        'avg_unit_price': 0,
        'median_unit_price': 0,
        'count': 0
    })

    # 转换为字典列表
    area_price = area_grouped.to_dict('records')

    # 5. 计算相关性
    correlation = df[['area', 'total_price', 'unit_price']].corr().to_dict()

    return {
        'success': True,
        'room_price': room_price,
        'direction_price': direction_price,
        'floor_price': floor_price,
        'area_price': area_price,
        'correlation': correlation,
        'total_count': len(df)
    }
