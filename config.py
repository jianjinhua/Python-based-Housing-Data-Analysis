import os
import secrets

class Config:
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))

    # MySQL配置 - 确保与spider.py中的配置一致
    SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://root:123456@localhost:3306/hy_houses'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    SECRET_KEY = secrets.token_hex(16)
    DEBUG = True