from flask import Flask
from flask_wtf.csrf import CSRFProtect  # CSRF保护模块
from flask_login import LoginManager, current_user  # 添加current_user导入
import os  # 操作系统接口
from datetime import datetime, timedelta  # 时间处理模块
from markupsafe import Markup  # 安全HTML字符串处理
from config.config import Config  # 从config.config导入Config
import importlib.util
import sys
from flask_migrate import Migrate
from database import db, Department, Course
# 全局变量存储数据库实例和模型
db = None
User = None


# 创建 Flask 应用
def create_app(config_object=Config):
    app = Flask(__name__)
    app.config.from_object(config_object)

    # 初始化 CSRF 保护
    csrf = CSRFProtect(app)

    # 初始化数据库 - 智能检测并使用已有实例
    initialize_database(app)

    # 初始化课程数据
    initialize_course_data(app)

    # 添加数据库迁移支持
    migrate = Migrate(app, db)

    # 初始化登录管理器
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"  # 设置登录视图端点
    login_manager.remember_cookie_duration = timedelta(days=7)  # 设置7天免登录

    # 创建必要的文件夹
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)  # 上传文件目录
    os.makedirs(app.config["AVATAR_FOLDER"], exist_ok=True)  # 用户头像目录

    # 确保默认头像存在
    from utils.other import ensure_default_avatar

    with app.app_context():
        ensure_default_avatar()


    # 导入各个功能模块的蓝图
    from blueprints.auth import auth_bp
    from blueprints.profile import profile_bp
    from blueprints.material import material_bp
    from blueprints.browse import browse_bp
    from blueprints.search import search_bp
    from blueprints.admin import admin_bp
    from blueprints.errors import errors_bp
    from blueprints.about import about_bp
    from blueprints.notification import notification_bp  # 添加这一行
    from blueprints.ranking import ranking_bp  # 确保导入排行榜蓝图
    from blueprints.utils_bp import utils_bp  # 导入其他蓝图

    # 将蓝图注册到应用
    app.register_blueprint(auth_bp)
    app.register_blueprint(profile_bp)
    app.register_blueprint(material_bp)
    app.register_blueprint(browse_bp)
    app.register_blueprint(search_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(errors_bp)
    app.register_blueprint(about_bp)
    app.register_blueprint(notification_bp)  # 添加这一行
    app.register_blueprint(ranking_bp)  # 注册排行榜蓝图
    app.register_blueprint(utils_bp, url_prefix='/utils')  # 注册其他蓝图

    # 导入并应用用户关注功能 - 在所有数据库表都创建好之后再初始化
    with app.app_context():
        db.create_all()  # 确保创建了所有表，包括新添加的UserFollow表

    # 用户加载函数
    @login_manager.user_loader
    def load_user(user_id):
        global User, db
        user = User.query.get(int(user_id))
        # 自动提升配置中的管理员邮箱为管理员
        if (
            user
            and user.email in app.config.get("ADMIN_EMAILS", [])
            and not user.is_admin
        ):
            user.is_admin = True
            db.session.commit()
            print(f"已将用户 {user.username} ({user.email}) 设置为管理员")
        return user

    # 全局上下文处理器
    @app.context_processor
    def inject_now():
        return {"now": datetime.now()}  # 在所有模板中注入当前时间

    # 注入未读通知数到所有模板
    @app.context_processor
    def inject_unread_notifications():
        from blueprints.notification import load_notifications

        unread_count = 0
        if current_user.is_authenticated:
            all_notifications = load_notifications()
            for notification in all_notifications:
                if notification["target_role"] == "all" or (
                    current_user.is_admin and notification["target_role"] == "admin"
                ):
                    if current_user.id not in notification.get("read_by", []):
                        unread_count += 1
        return {"unread_count": unread_count}

    # 注册自定义过滤器
    @app.template_filter("time_since")
    def time_since(dt):
        """返回友好的时间差显示"""
        now = datetime.now()
        diff = now - dt

        if diff.days < 1:
            if diff.seconds < 60:
                return f"{diff.seconds}秒前"
            elif diff.seconds < 3600:
                return f"{diff.seconds // 60}分钟前"
            else:
                return f"{diff.seconds // 3600}小时前"
        elif diff.days < 30:
            return f"{diff.days}天前"
        elif diff.days < 365:
            return f"{diff.days // 30}个月前"
        else:
            return f"{diff.days // 365}年前"

    # 注册自定义过滤器
    @app.template_filter("nl2br")
    def nl2br(value):
        """将换行符转换为HTML中的<br>标签"""
        if isinstance(value, str):
            return Markup(value.replace("\n", "<br>"))
        return value

    return app


def initialize_database(app):
    """智能初始化数据库，避免重复创建实例"""
    global db, User

    # 检查是否已有数据库实例
    if db is None:
        try:
            # 首先尝试从 database 包导入
            if importlib.util.find_spec("database"):
                from database.base import db as db_instance
                from database import User as UserModel

                print("使用 database 包中的数据库实例")
                db = db_instance
                User = UserModel

                try:
                    # 初始化数据库 - 修改调用顺序
                    print("正在初始化SQLAlchemy...")
                    db.init_app(app)  # 先将app与db实例关联
                    print("SQLAlchemy初始化完成，开始创建表结构...")

                    # 显式在应用上下文中执行数据库初始化
                    with app.app_context():
                        from database import Department

                        try:
                            from sqlalchemy import text  # 导入 text 函数
                            from sqlalchemy import inspect  # 导入 inspect 函数

                            # 检查数据库连接
                            with db.engine.connect() as connection:
                                # SQLAlchemy 2.0 API 方式
                                result = connection.execute(text("SELECT 1"))
                                value = result.scalar()  # 获取结果中的第一个值
                                print(f"数据库连接正常，测试结果: {value}")
                                
                            # 获取检查器实例并检查表结构
                            inspector = inspect(db.engine)
                            tables = inspector.get_table_names()
                            print(f"当前数据库表: {tables}")
                            
                            # 创建所有基本表
                            print("创建基础表...")
                            db.create_all()
                            print("数据库表创建成功")
                            
                            # 看是否有User表，如果有并获取其列结构
                            if 'user' in tables:
                                columns = [c['name'] for c in inspector.get_columns('user')]
                                print(f"User表结构: {columns}")
                            
                            # 导入UserFollow模型
                            print("初始化用户关注功能...")
                            
                            # 确保UserFollow表存在
                            db.create_all()
                                        
                            # 检查是否需要添加学院数据
                            try:
                                dept_count = Department.query.count()
                                print(f"当前学院数量: {dept_count}")
                                if dept_count == 0:
                                    print("开始添加初始学院数据...")
                                    setup_initial_departments(db)
                            except Exception as e:
                                print(f"检查/添加学院数据失败: {str(e)}")

                        except Exception as e:
                            print(f"数据库连接测试失败: {str(e)}")
                            import traceback

                            traceback.print_exc()  # 打印详细的错误堆栈信息

                        # 创建所有表
                        db.create_all()
                        print("数据库表创建成功")

                        # 检查是否需要添加学院数据
                        try:
                            dept_count = Department.query.count()
                            print(f"当前学院数量: {dept_count}")
                            if dept_count == 0:
                                print("开始添加初始学院数据...")
                                setup_initial_departments(db)
                        except Exception as e:
                            print(f"检查/添加学院数据失败: {str(e)}")

                except Exception as e:
                    print(f"数据库初始化失败: {str(e)}")
            else:
                # 如果没有 database 包，则使用 database 模块
                from database import db as db_instance, User as UserModel

                print("使用 database 模块中的数据库实例")
                db = db_instance
                User = UserModel

                # 初始化数据库
                print("正在初始化SQLAlchemy...")
                db.init_app(app)
                print("SQLAlchemy初始化完成")

                # 尝试初始化表结构和基础数据
                try:
                    with app.app_context():
                        print("开始创建数据库表...")
                        db.create_all()
                        print("数据库表创建成功")

                        # 检查是否需要添加学院数据
                        try:
                            from database import Department

                            dept_count = Department.query.count()
                            print(f"当前学院数量: {dept_count}")
                            if dept_count == 0:
                                print("开始添加初始学院数据...")
                                setup_initial_departments(db)
                        except Exception as e:
                            print(f"检查/添加学院数据失败: {str(e)}")

                        # 创建上传文件夹
                        uploads_dir = app.config["UPLOAD_FOLDER"]
                        avatar_dir = app.config.get(
                            "AVATAR_FOLDER", app.config["UPLOAD_FOLDER"] + "/avatars"
                        )

                        os.makedirs(uploads_dir, exist_ok=True)
                        os.makedirs(avatar_dir, exist_ok=True)

                        print(f"上传目录创建成功: {uploads_dir}")
                        print(f"头像目录创建成功: {avatar_dir}")
                except Exception as e:
                    print(f"初始化表结构和基础数据失败: {str(e)}")
                    import traceback

                    traceback.print_exc()

        except ImportError as e:
            print(f"数据库初始化失败，模块导入错误: {str(e)}")
            sys.exit(1)
        except Exception as e:
            print(f"数据库初始化过程中发生未知错误: {str(e)}")
            import traceback

            traceback.print_exc()
            sys.exit(1)
    else:
        print("使用现有数据库实例")


def setup_initial_departments(db):
    """设置初始学院数据"""
    from database.models import Department

    departments = [
        Department(name="数学科学学院"),
        Department(name="物理学院"),
        Department(name="化学与分子工程学院"),
        Department(name="生命科学学院"),
        Department(name="地球与空间科学学院"),
        Department(name="心理与认知科学学院"),
        Department(name="信息科学技术学院"),
        Department(name="工学院"),
        Department(name="元培学院"),
        Department(name="光华管理学院"),
        Department(name="经济学院"),
        Department(name="法学院"),
        Department(name="国家发展研究院"),
        Department(name="教育学院"),
        Department(name="新闻与传播学院"),
        Department(name="医学部"),
    ]

    db.session.add_all(departments)
    try:
        db.session.commit()
        print(f"已添加 {len(departments)} 个学院数据")
    except Exception as e:
        db.session.rollback()
        print(f"添加学院数据失败: {str(e)}")


def initialize_course_data(app):
    """从 course_data.json 初始化课程数据"""
    import json
    import os

    
    print("=" * 50)
    print("课程数据初始化工具")
    print("=" * 50)
    
    try:
        with app.app_context():
            # 检查是否需要初始化课程数据
            course_count = Course.query.count()
            print(f"当前数据库中已有课程数量: {course_count}")
            
            # 读取课程数据
            json_path = os.path.join(app.root_path, 'course_data.json')
            if not os.path.exists(json_path):
                print(f"✗ 课程数据文件不存在: {json_path}")
                return
                
            with open(json_path, 'r', encoding='utf-8') as f:
                courses_data = json.load(f)
            print(f"✓ 成功读取课程数据，共 {len(courses_data)} 条记录")
            
            # 从数据中获取所有的院系名称
            departments = set()
            for course in courses_data:
                if 'department' in course and course['department']:
                    departments.add(course['department'])
            
            print(f"→ 发现 {len(departments)} 个院系")
            
            # 确保所有院系都存在
            department_map = {}
            for dept_name in departments:
                dept = Department.query.filter_by(name=dept_name).first()
                if not dept:
                    dept = Department(name=dept_name, description=f"{dept_name}院系")
                    db.session.add(dept)
                    print(f"+ 创建新院系: {dept_name}")
                department_map[dept_name] = dept
            
            # 提交院系更改
            db.session.commit()
            print("✓ 院系数据处理完成")
            
            # 统计信息
            created = 0
            updated = 0
            skipped = 0
            errors = 0
            total = len(courses_data)
            
            # 批量处理，提高效率
            batch_size = 100
            current_batch = 0
            
            print("\n开始导入课程数据...")
            
            for i, course_data in enumerate(courses_data, 1):
                try:
                    # 必要字段检查
                    code = course_data.get('code')
                    name = course_data.get('course')
                    dept_name = course_data.get('department')
                    
                    if not code or not name or not dept_name:
                        print(f"! 跳过记录 #{i}: 缺少必要字段(code={code}, name={name}, department={dept_name})")
                        skipped += 1
                        continue
                    
                    # 如果院系不存在于映射中
                    if dept_name not in department_map:
                        print(f"! 跳过记录 #{i}: 未知院系 '{dept_name}'")
                        skipped += 1
                        continue
                    
                    # 检查课程是否已存在
                    existing_course = Course.query.filter_by(code=code).first()
                    
                    # 处理学分和课时
                    try:
                        credit_value = course_data.get('credit', '0')
                        if isinstance(credit_value, str):
                            credit_value = credit_value.replace(',', '.').strip()
                        credits = int(float(credit_value) * 100)
                    except (ValueError, TypeError):
                        print(f"! 警告: 记录 #{i} ({name}) 的学分格式无效: '{course_data.get('credit')}'，使用默认值0")
                        credits = 0
                    
                    try:
                        hours_value = course_data.get('hours', 0)
                        hours = int(hours_value)
                    except (ValueError, TypeError):
                        print(f"! 警告: 记录 #{i} ({name}) 的课时格式无效: '{course_data.get('hours')}'，使用默认值0")
                        hours = 0
                    
                    course_type = course_data.get('type', '未分类')
                    description = course_data.get('description', '')
                    
                    if existing_course:
                        # 更新现有课程
                        existing_course.name = name
                        existing_course.department_id = department_map[dept_name].id
                        existing_course.credits = credits
                        existing_course.type = course_type
                        existing_course.hours = hours
                        existing_course.description = description
                        updated += 1
                    else:
                        # 创建新课程
                        new_course = Course(
                            name=name,
                            code=code,
                            credits=credits,
                            type=course_type,
                            hours=hours,
                            description=description,
                            department_id=department_map[dept_name].id
                        )
                        db.session.add(new_course)
                        created += 1
                    
                    # 批量提交
                    current_batch += 1
                    if current_batch >= batch_size:
                        db.session.commit()
                        print(f"→ 进度: {i}/{total} 条记录处理完成 (新增: {created}, 更新: {updated}, 跳过: {skipped}, 错误: {errors})")
                        current_batch = 0
                    
                except Exception as e:
                    errors += 1
                    print(f"✗ 处理记录 #{i} 出错: {str(e)}")
            
            # 提交剩余的记录
            if current_batch > 0:
                db.session.commit()
            
            print("\n" + "=" * 50)
            print("课程数据导入完成")
            print(f"总记录数: {total}")
            print(f"新增课程: {created}")
            print(f"更新课程: {updated}")
            print(f"跳过记录: {skipped}")
            print(f"错误记录: {errors}")
            print("=" * 50)
    
    except Exception as e:
        print(f"初始化课程数据失败: {str(e)}")
        import traceback
        traceback.print_exc()
