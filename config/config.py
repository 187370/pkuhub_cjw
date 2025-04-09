import os
import secrets
import yaml
import logging
from datetime import timedelta


def load_yaml_config():
    """从YAML文件加载配置"""
    # 获取项目根目录
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(base_dir, "config", "config.yaml")

    try:
        with open(config_path, "r", encoding="utf-8") as file:
            return yaml.safe_load(file), base_dir
    except FileNotFoundError:
        logging.error(f"配置文件 {config_path} 不存在！")
        # 创建默认配置文件
        default_config = {
            "database": {"uri": "sqlite:///pkuhub.db", "track_modifications": False},
            "upload": {
                "folder": "static/uploads",
                "avatar_folder": "static/avatars",
                "max_content_length": 52428800,
            },
            "mail": {
                "server": "smtp.gmail.com",
                "port": 587,
                "use_tls": True,
                "username": "你的邮箱地址",
                "password": "你的邮箱密码",
                "default_sender": "你的邮箱地址",
            },
            "admin": {"emails": ["管理员邮箱地址"]},
            "session": {
                "cookie": {"secure": False, "httponly": True, "samesite": "Lax"}
            },
            "csrf": {"time_limit": 3600, "ssl_strict": False},
        }

        try:
            os.makedirs(os.path.dirname(config_path), exist_ok=True)
            with open(config_path, "w", encoding="utf-8") as file:
                yaml.dump(
                    default_config, file, default_flow_style=False, allow_unicode=True
                )
            logging.info(f"已创建默认配置文件 {config_path}")
            return default_config, base_dir
        except Exception as e:
            logging.error(f"创建默认配置文件失败: {str(e)}")
            return default_config, base_dir


class Config:
    # 加载YAML配置
    _yaml_config, BASE_DIR = load_yaml_config()

    # 密钥
    SECRET_KEY = secrets.token_hex(16)

    # 数据库配置
    SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(
        BASE_DIR, _yaml_config["database"]["uri"].replace("sqlite:///", "")
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = _yaml_config["database"]["track_modifications"]

    # 上传文件配置
    UPLOAD_FOLDER = os.path.join(BASE_DIR, _yaml_config["upload"]["folder"])
    AVATAR_FOLDER = os.path.join(BASE_DIR, _yaml_config["upload"]["avatar_folder"])
    MAX_CONTENT_LENGTH = _yaml_config["upload"]["max_content_length"]

    # 初始管理员邮箱
    ADMIN_EMAILS = _yaml_config["admin"]["emails"]

    # 会话配置
    SESSION_COOKIE_SECURE = _yaml_config["session"]["cookie"]["secure"]
    SESSION_COOKIE_HTTPONLY = _yaml_config["session"]["cookie"]["httponly"]
    SESSION_COOKIE_SAMESITE = _yaml_config["session"]["cookie"]["samesite"]

    # 域名配置（可选）
    if "domain" in _yaml_config["session"]["cookie"]:
        SESSION_COOKIE_DOMAIN = _yaml_config["session"]["cookie"]["domain"]

    # CSRF配置
    WTF_CSRF_TIME_LIMIT = _yaml_config["csrf"]["time_limit"]
    WTF_CSRF_SSL_STRICT = _yaml_config["csrf"]["ssl_strict"]

    # 设置"记住我"的 Cookie 有效期为 30 天
    REMEMBER_COOKIE_DURATION = timedelta(days=30)

    # 可选：设置记住我的安全性配置
    REMEMBER_COOKIE_SECURE = False  # 如果使用 HTTPS，设为 True
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_REFRESH_EACH_REQUEST = True  # 每次请求都刷新 Cookie
