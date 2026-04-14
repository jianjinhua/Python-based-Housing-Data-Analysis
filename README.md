项目技术栈
后端：Python、Flask、SQLAlchemy
前端：Bootstrap、ECharts
数据库：MySQL
爬虫：Requests、BeautifulSoup
部署指南
环境要求
Python 3.8+
pip 包管理工具
MySQL 5.7+ 或 8.0+
Git（可选，用于获取源码）
部署步骤
1. 获取源码
git clone https://gitee.com/honii11/zhuge.git
cd zhuge

或直接下载源码包解压

2. 创建虚拟环境
python -m venv venv
venv\Scripts\activate
3. 安装依赖
pip install -r requirements.txt
4. 配置 MySQL 数据库

先在 MySQL 中创建数据库，例如：

CREATE DATABASE zhuge DEFAULT CHARACTER SET utf8mb4;

然后修改项目配置（一般是 config.py 或 .env），将数据库连接改为：

SQLALCHEMY_DATABASE_URI = "mysql+pymysql://用户名:密码@localhost:3306/zhuge"

如果未安装驱动，请先安装：

pip install pymysql
5. 初始化数据库
flask db init
flask db migrate -m "initial migration"
flask db upgrade
6. 启动应用
flask run

或使用生产环境启动：

python run.py
7. 访问应用

打开浏览器访问：

http://localhost:5000
爬取数据

系统启动后，需要先爬取数据才能进行分析：

登录系统
进入「爬虫管理」页面
设置爬取参数（城市、页数等）
点击「开始爬取」
注意事项
首次使用需要注册账号
爬取数据可能需要一定时间，请耐心等待
爬取过程中请遵守相关网站的 robots 协议
使用 MySQL 时，请确保数据库服务已启动且连接配置正确
