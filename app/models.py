import re

from app import db, login_manager
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import json


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, index=True)
    email = db.Column(db.String(120), unique=True, index=True)
    password_hash = db.Column(db.String(128))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


class House(db.Model):
    __tablename__ = 'houses'

    id = db.Column(db.Integer, primary_key=True)
    house_name = db.Column(db.String(500))  # 增加长度
    house_url = db.Column(db.String(500))
    address = db.Column(db.Text)
    floor = db.Column(db.Text)
    room_type = db.Column(db.Text)
    area = db.Column(db.Text)  # 保持文本类型，包含单位
    direction = db.Column(db.Text)
    tags = db.Column(db.Text)
    total_price = db.Column(db.Text)  # 保持文本类型，包含单位
    unit_price = db.Column(db.Text)  # 保持文本类型，包含单位
    crawl_time = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'house_name': self.house_name,
            'house_url': self.house_url,
            'address': self.address,
            'floor': self.floor,
            'room_type': self.room_type,
            'area': self.area,
            'direction': self.direction,
            'tags': self.tags,
            'total_price': self.total_price,
            'unit_price': self.unit_price,
            'crawl_time': self.crawl_time.strftime('%Y-%m-%d %H:%M:%S') if self.crawl_time else None
        }

    def get_numeric_area(self):
        """提取面积的数值部分"""
        if not self.area or self.area == '未知':
            return None
        try:
            match = re.search(r'(\d+(?:\.\d+)?)', self.area)
            return float(match.group(1)) if match else None
        except:
            return None

    def get_numeric_total_price(self):
        """提取总价的数值部分（万元）"""
        if not self.total_price or self.total_price == '未知':
            return None
        try:
            match = re.search(r'(\d+(?:\.\d+)?)', self.total_price)
            return float(match.group(1)) if match else None
        except:
            return None

    def get_numeric_unit_price(self):
        """提取单价的数值部分（元/㎡）"""
        if not self.unit_price or self.unit_price == '未知':
            return None
        try:
            # 移除逗号等分隔符
            price_str = re.sub(r'[^\d.]', '', self.unit_price)
            return float(price_str) if price_str else None
        except:
            return None

    def get_cleaned_floor(self):
        """清洗楼层数据，保留括号前的内容"""
        if not self.floor or self.floor == '未知':
            return None
        try:
            # 分割字符串，取括号前的内容
            if '(' in self.floor:
                return self.floor.split('(')[0].strip()
            else:
                return self.floor.strip()
        except:
            return self.floor