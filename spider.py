# import re
# import pandas as pd
# import time
# import sqlite3
# from DrissionPage import WebPage
# import mysql.connector
# from mysql.connector import Error
# from urllib.parse import urljoin, urlparse
#
#
# def init_mysql_database():
#     """初始化MySQL数据库"""
#     try:
#         # 请根据您的MySQL配置修改这些参数
#         conn = mysql.connector.connect(
#             host='localhost',
#             user='root',
#             password='123456',
#             database='hy_houses'
#         )
#
#         if conn.is_connected():
#             cursor = conn.cursor()
#
#             # 创建房源信息表
#             cursor.execute('''
#             CREATE TABLE IF NOT EXISTS houses (
#                 id INT AUTO_INCREMENT PRIMARY KEY,
#                 house_name VARCHAR(500),
#                 house_url VARCHAR(500),
#                 address TEXT,
#                 floor TEXT,
#                 room_type TEXT,
#                 area TEXT,
#                 direction TEXT,
#                 tags TEXT,
#                 total_price TEXT,
#                 unit_price TEXT,
#                 crawl_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
#             )
#             ''')
#
#             conn.commit()
#             print("MySQL数据库连接成功")
#             return conn
#
#     except Error as e:
#         print(f"MySQL数据库连接错误: {e}")
#         return None
#
#
# def save_to_mysql_database(conn, houses_data):
#     """将房源数据保存到MySQL数据库"""
#     try:
#         cursor = conn.cursor()
#
#         for house in houses_data:
#             cursor.execute('''
#             INSERT INTO houses (
#                 house_name, house_url, address, floor, room_type,
#                 area, direction, tags, total_price, unit_price
#             ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
#             ''', (
#                 house['房源名称'], house['房源链接'], house['地址'],
#                 house['楼层'], house['户型'], house['面积'],
#                 house['朝向'], house['标签'], house['总价'], house['单价']
#             ))
#
#         conn.commit()
#         print(f"成功将 {len(houses_data)} 条数据保存到MySQL数据库")
#
#     except Error as e:
#         print(f"保存到MySQL数据库时出错: {e}")
#
#
# def init_sqlite_database():
#     """备用SQLite数据库初始化"""
#     import os
#     current_dir = os.path.dirname(os.path.abspath(__file__))
#     db_path = os.path.join(current_dir, 'ershoufang.db')
#
#     conn = sqlite3.connect(db_path)
#     cursor = conn.cursor()
#
#     cursor.execute('''
#     CREATE TABLE IF NOT EXISTS houses (
#         id INTEGER PRIMARY KEY AUTOINCREMENT,
#         house_name TEXT,
#         house_url TEXT,
#         address TEXT,
#         floor TEXT,
#         room_type TEXT,
#         area TEXT,
#         direction TEXT,
#         tags TEXT,
#         total_price TEXT,
#         unit_price TEXT,
#         crawl_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
#     )
#     ''')
#
#     conn.commit()
#     print("SQLite数据库连接成功")
#     return conn
#
#
#
# def simplify_url(full_url):
#     """简化URL，只保留到.html为止"""
#     if not full_url or full_url == "未知":
#         return "未知"
#
#     # 如果是相对路径，转换为绝对路径
#     if full_url.startswith('//'):
#         full_url = 'https:' + full_url
#     elif full_url.startswith('/'):
#         full_url = 'https://cs.58.com' + full_url
#
#     # 解析URL
#     parsed = urlparse(full_url)
#
#     # 提取路径并简化
#     path = parsed.path
#     if '.shtml' in path:
#         # 找到.shtml的位置，截取到此处
#         shtml_index = path.find('.shtml')
#         simplified_path = path[:shtml_index + 6]  # 包含.shtml
#     else:
#         simplified_path = path
#
#     # 构建简化后的URL
#     simplified_url = f"https://{parsed.netloc}{simplified_path}"
#
#     return simplified_url
#
#
# def crawl_58_houses(max_houses=100):
#     """爬取58同城衡阳二手房数据"""
#     # 创建WebPage对象
#     page = WebPage()
#
#     # 访问58同城衡阳二手房网站
#     base_url = 'https://cs.58.com/ershoufang/'
#     page.get(base_url)
#
#     # 初始化数据库
#     conn = init_mysql_database()
#     use_mysql = True
#
#     # 存储所有房源信息
#     houses_data = []
#     current_page = 1
#     seen_urls = set()  # 用于去重
#
#     # 循环爬取直到达到目标数量
#     while len(houses_data) < max_houses:
#         print(f"正在爬取第 {current_page} 页，当前已爬取 {len(houses_data)}/{max_houses} 条数据")
#         time.sleep(2)
#
#         try:
#             # 方法1：直接排除热门楼盘模块
#             # 找到主列表容器，排除热门推荐部分
#             main_list = page.ele('.list-main') or page.ele('.list-left') or page.ele('#esfMain')
#
#             if not main_list:
#                 print("未找到主列表容器")
#                 break
#
#             # 获取所有房源元素，但排除热门楼盘相关的元素
#             house_items = []
#
#             # 方法1A：使用CSS选择器排除热门楼盘
#             try:
#                 # 排除包含热门楼盘特征的div
#                 house_items = main_list.eles(
#                     '.property:not([class*="HotLoupans"]):not([class*="xfrecommend"]):not([class*="recommend"])')
#             except:
#                 pass
#
#             # 如果上面没找到，尝试其他选择器
#             if not house_items:
#                 house_items = main_list.eles('.property') or main_list.eles('.property-ex')
#
#             if not house_items:
#                 print("未找到房源数据，可能已到达最后一页或页面结构变化")
#                 break
#
#             print(f"本页找到 {len(house_items)} 个有效房源")
#
#             # 存储本页爬取的数据
#             page_houses_data = []
#
#             # 遍历每个有效房源
#             for i, item in enumerate(house_items):
#                 try:
#                     # 如果已经达到最大数量，提前结束
#                     if len(houses_data) >= max_houses:
#                         break
#
#                     # 提取房源名称
#                     title_ele = (item.ele('.property-content-title-name', timeout=1) or
#                                  item.ele('tag:h3', timeout=1) or
#                                  item.ele('css:[class*="title"]', timeout=1))
#                     house_name = title_ele.text if title_ele else f"房源_{current_page}_{i}"
#
#                     # 提取房源链接并简化
#                     link_ele = item.ele('tag:a', timeout=1)
#                     house_url = "未知"
#                     if link_ele:
#                         raw_url = link_ele.attr('href') or ""
#                         house_url = simplify_url(raw_url)
#
#                     # URL去重
#                     if house_url in seen_urls:
#                         print(f"跳过重复房源: {house_name}")
#                         continue
#                     seen_urls.add(house_url)
#
#                     # 提取地址信息
#                     address_ele = (item.ele('.property-content-info-comm-address', timeout=1) or
#                                    item.ele('.property-content-info-comm-name', timeout=1) or
#                                    item.ele('css:[class*="address"]', timeout=1))
#                     address = address_ele.text if address_ele else "未知"
#
#                     # 提取房屋详细信息
#                     info_texts = []
#                     info_container = item.ele('.property-content-info', timeout=1)
#                     if info_container:
#                         info_elements = info_container.eles('tag:p', timeout=1) or info_container.eles('tag:span',
#                                                                                                        timeout=1)
#                         if info_elements:
#                             info_texts = [elem.text for elem in info_elements if elem.text]
#
#                     house_info = " ".join(info_texts)
#
#                     # 解析房屋信息
#                     floor = "未知"
#                     room_type = "未知"
#                     area = "未知"
#                     direction = "未知"
#
#                     # 使用正则表达式解析房屋信息
#                     if house_info:
#                         # 解析户型 (如: 3室2厅2卫)
#                         room_pattern = r'(\d+室\d*厅*\d*卫*)'
#                         room_match = re.search(room_pattern, house_info)
#                         room_type = room_match.group(1) if room_match else "未知"
#
#                         # 解析面积 (如: 129㎡)
#                         area_pattern = r'(\d+(?:\.\d+)?)\s*㎡'
#                         area_match = re.search(area_pattern, house_info)
#                         area = area_match.group(1) + "㎡" if area_match else "未知"
#
#                         # 解析朝向 (如: 南北)
#                         direction_pattern = r'(南北|东西|东南|西南|东北|西北|东|南|西|北)'
#                         direction_match = re.search(direction_pattern, house_info)
#                         direction = direction_match.group(1) if direction_match else "未知"
#
#                         # 解析楼层 (如: 低层(共7层))
#                         floor_pattern = r'([高|中|低|顶]层\(共\d+层\))'
#                         floor_match = re.search(floor_pattern, house_info)
#                         if floor_match:
#                             floor = floor_match.group(1)
#                         else:
#                             # 尝试其他楼层格式
#                             floor_pattern2 = r'(\w+层)'
#                             floor_match2 = re.search(floor_pattern2, house_info)
#                             floor = floor_match2.group(1) if floor_match2 else "未知"
#
#                     # 提取房屋标签
#                     tags = "无标签"
#                     tag_elements = item.eles('.property-content-info-tag', timeout=1) or item.eles('css:[class*="tag"]',
#                                                                                                    timeout=1)
#                     if tag_elements:
#                         tags = " ".join([tag.text for tag in tag_elements if tag.text])
#
#                     # 提取价格信息
#                     total_price = "未知"
#                     unit_price = "未知"
#
#                     total_price_ele = (item.ele('.property-price-total-num', timeout=1) or
#                                        item.ele('css:[class*="price"]', timeout=1) or
#                                        item.ele('css:[class*="total"]', timeout=1))
#                     if total_price_ele:
#                         total_price = total_price_ele.text + "万"
#
#                     unit_price_ele = (item.ele('.property-price-average', timeout=1) or
#                                       item.ele('css:[class*="unit"]', timeout=1) or
#                                       item.ele('css:[class*="average"]', timeout=1))
#                     if unit_price_ele:
#                         unit_price = unit_price_ele.text
#
#                     # 整合房源信息
#                     house_data = {
#                         '房源名称': house_name,
#                         '房源链接': house_url,
#                         '地址': address,
#                         '楼层': floor,
#                         '户型': room_type,
#                         '面积': area,
#                         '朝向': direction,
#                         '标签': tags,
#                         '总价': total_price,
#                         '单价': unit_price
#                     }
#
#                     page_houses_data.append(house_data)
#                     houses_data.append(house_data)
#                     print(f"成功爬取: {house_name}")
#                     print(f"简化链接: {house_url}")
#
#                 except Exception as e:
#                     print(f"爬取单个房源失败: {e}")
#                     continue
#
#             # 每爬取一页数据就保存到数据库
#             if page_houses_data:
#                 if use_mysql:
#                     save_to_mysql_database(conn, page_houses_data)
#                 print(f"第 {current_page} 页数据保存完成")
#
#             # 如果已经达到最大数量，提前结束
#             if len(houses_data) >= max_houses:
#                 print(f"已达到最大爬取数量 {max_houses}，停止爬取")
#                 break
#
#             # 翻页逻辑
#             try:
#                 # 等待页面稳定
#                 time.sleep(1)
#
#                 # 多种方式查找下一页按钮
#                 next_selectors = [
#                     'text:下一页',
#                     '.next',
#                     '.page-next',
#                     'a:contains(下一页)',
#                     '[class*="next"]',
#                     'a[href*="pn"]'
#                 ]
#
#                 next_page = None
#                 for selector in next_selectors:
#                     try:
#                         next_page = page.ele(selector, timeout=1)
#                         if next_page:
#                             break
#                     except:
#                         continue
#
#                 if not next_page:
#                     print("未找到下一页按钮，可能已到达最后一页")
#                     break
#
#                 # 检查下一页按钮是否可用
#                 class_attr = next_page.attr('class') or ""
#                 style_attr = next_page.attr('style') or ""
#
#                 if 'disabled' in class_attr or 'none' in style_attr:
#                     print("已到达最后一页")
#                     break
#
#                 print("点击下一页...")
#                 next_page.click()
#
#                 # 等待页面加载完成
#                 time.sleep(3)
#
#                 current_page += 1
#
#             except Exception as e:
#                 print(f"翻页失败: {e}")
#                 # 尝试直接构造URL翻页
#                 try:
#                     next_page_url = f"{base_url}pn{current_page + 1}/"
#                     print(f"尝试直接访问: {next_page_url}")
#                     page.get(next_page_url)
#                     time.sleep(2)
#                     current_page += 1
#                 except:
#                     print("所有翻页方式都失败，停止爬取")
#                     break
#
#         except Exception as e:
#             print(f"爬取页面失败: {e}")
#             break
#
#     print(f"爬取完成，共爬取 {len(houses_data)} 条有效房源信息，已保存到数据库")
#
#     # 关闭数据库连接
#     if conn:
#         conn.close()
#         print("数据库连接已关闭")
#     page.quit()
#     return houses_data
#
#
# if __name__ == "__main__":
#     # 爬取58同城二手房数据
#     houses_data = crawl_58_houses(200)  # 先测试50条
