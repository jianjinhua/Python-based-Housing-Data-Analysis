from app import create_app, db
from app.models import User, House

app = create_app()

# 替换 @app.before_first_request 装饰器
# 使用 with app.app_context() 代替

with app.app_context():
    db.create_all()
    
    # 创建默认管理员账户（如果不存在）
    if not User.query.filter_by(username='admin').first():
        admin = User(username='admin', email='admin@example.com')
        admin.set_password('123456')
        db.session.add(admin)
        db.session.commit()

if __name__ == '__main__':
    app.run(debug=True)