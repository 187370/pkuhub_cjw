from flask import current_app
from functools import wraps
from flask_login import current_user
from flask import abort


# 管理员权限验证装饰器
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)  # 无权限访问
        return f(*args, **kwargs)

    return decorated_function
