"""
通知模块 - 提供邮件发送和验证码管理功能

主要组件:
1. MailNotifier - 发送邮件通知
2. 验证码相关功能 - 生成、发送、验证和管理验证码
3. 应用内通知功能 - 管理应用内的通知系统
"""

# 从base.py导入邮件通知器和异常类
from .base import (
    MailNotifier,
    NotificationError,
    AuthenticationError,
    DeliveryError,
    ConfigurationError,
)

# 从verification_code.py导入验证码相关功能
from .verification_code import (
    code_generator,
    send_verification_codes,
    verify_code,
    code_manager,
)

# 从app_notification.py导入应用内通知功能
from .app_notification import (
    AppNotificationManager,
    notification_manager,
)

# 指定导出的符号，控制from notification import *的行为
__all__ = [
    # 邮件通知相关
    "MailNotifier",
    "NotificationError",
    "AuthenticationError",
    "DeliveryError",
    "ConfigurationError",
    # 验证码相关
    "code_generator",
    "send_verification_codes",
    "verify_code",
    "code_manager",
    # 应用内通知相关
    "AppNotificationManager",
    "notification_manager",
]
