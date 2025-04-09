from flask import Blueprint

# 导入所有蓝图模块
from .admin import admin_bp
from .auth import auth_bp
from .browse import browse_bp
from .errors import errors_bp
from .material import material_bp
from .profile import profile_bp
from .search import search_bp
from blueprints.utils_bp import utils_bp
# 创建一个蓝图列表，方便在主应用中注册
all_blueprints = [
    admin_bp,
    auth_bp,
    browse_bp,
    errors_bp,
    material_bp,
    profile_bp,
    search_bp,
]
