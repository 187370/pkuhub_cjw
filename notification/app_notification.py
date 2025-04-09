import os
import json
from datetime import datetime
from typing import List, Dict, Optional, Union


class AppNotificationManager:
    """
    应用内通知管理类 - 负责存储、加载和管理通知
    """

    _instance = None
    _initialized = False

    def __new__(cls):
        """实现单例模式"""
        if cls._instance is None:
            cls._instance = super(AppNotificationManager, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        """初始化通知管理器"""
        if self._initialized:
            return

        # 通知存储文件名
        self._notification_file = "notifications.json"
        self._initialized = True

    def get_notification_path(self, app_root_path: str) -> str:
        """
        获取通知存储文件的完整路径

        参数:
            app_root_path: 应用根目录
        返回:
            通知文件的完整路径
        """
        return os.path.join(app_root_path, self._notification_file)

    def load_notifications(self, app_root_path: str) -> List[Dict]:
        """
        加载所有通知

        参数:
            app_root_path: 应用根目录
        返回:
            通知列表
        """
        try:
            notification_path = self.get_notification_path(app_root_path)
            if os.path.exists(notification_path):
                with open(notification_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            return []
        except Exception as e:
            print(f"加载通知失败: {e}")
            return []

    def save_notifications(self, notifications: List[Dict], app_root_path: str) -> bool:
        """
        保存通知到文件

        参数:
            notifications: 通知列表
            app_root_path: 应用根目录
        返回:
            是否保存成功
        """
        try:
            notification_path = self.get_notification_path(app_root_path)
            with open(notification_path, "w", encoding="utf-8") as f:
                json.dump(notifications, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"保存通知失败: {e}")
            return False

    def create_notification(
        self,
        title: str,
        content: str,
        creator_id: int,
        target_role: str = "all",
        app_root_path: str = None,
    ) -> Dict:
        """
        创建新通知

        参数:
            title: 通知标题
            content: 通知内容
            creator_id: 创建者ID
            target_role: 目标角色 ('all' 或 'admin')
            app_root_path: 应用根目录

        返回:
            创建的通知字典
        """
        if not title.strip() or not content.strip():
            raise ValueError("标题和内容不能为空")

        # 创建新通知
        new_notification = {
            "id": str(datetime.now().timestamp()),
            "title": title.strip(),
            "content": content.strip(),
            "target_role": target_role,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "created_by": creator_id,
            "read_by": [],
        }

        if app_root_path:
            # 加载现有通知并添加新通知
            notifications = self.load_notifications(app_root_path)
            notifications.append(new_notification)

            # 保存更新后的通知
            self.save_notifications(notifications, app_root_path)

        return new_notification

    def mark_as_read(
        self, notification_id: str, user_id: int, app_root_path: str
    ) -> bool:
        """
        标记通知为已读

        参数:
            notification_id: 通知ID
            user_id: 用户ID
            app_root_path: 应用根目录

        返回:
            是否标记成功
        """
        notifications = self.load_notifications(app_root_path)

        for notification in notifications:
            if notification["id"] == notification_id:
                if "read_by" not in notification:
                    notification["read_by"] = []

                if user_id not in notification["read_by"]:
                    notification["read_by"].append(user_id)
                    self.save_notifications(notifications, app_root_path)
                    return True

        return False

    def get_user_notifications(
        self, user_id: int, is_admin: bool, app_root_path: str
    ) -> List[Dict]:
        """
        获取用户可见的通知

        参数:
            user_id: 用户ID
            is_admin: 用户是否为管理员
            app_root_path: 应用根目录

        返回:
            用户可见的通知列表，带有is_read标记
        """
        all_notifications = self.load_notifications(app_root_path)
        user_notifications = []

        for notification in all_notifications:
            # 检查是否是全体通知或针对特定角色
            if notification["target_role"] == "all" or (
                is_admin and notification["target_role"] == "admin"
            ):
                # 添加一个标记，指示当前用户是否已读该通知
                notification_copy = notification.copy()  # 创建副本以不影响原始数据
                notification_copy["is_read"] = user_id in notification.get(
                    "read_by", []
                )
                user_notifications.append(notification_copy)

        return user_notifications

    def get_unread_count(self, user_id: int, is_admin: bool, app_root_path: str) -> int:
        """
        获取用户未读通知数量

        参数:
            user_id: 用户ID
            is_admin: 用户是否为管理员
            app_root_path: 应用根目录

        返回:
            未读通知数量
        """
        all_notifications = self.load_notifications(app_root_path)
        unread_count = 0

        for notification in all_notifications:
            if notification["target_role"] == "all" or (
                is_admin and notification["target_role"] == "admin"
            ):
                if user_id not in notification.get("read_by", []):
                    unread_count += 1

        return unread_count

    def create_welcome_notification(self, app_root_path: str) -> bool:
        """
        创建欢迎通知(如果通知文件不存在)

        参数:
            app_root_path: 应用根目录

        返回:
            是否需要创建欢迎通知
        """
        notification_path = self.get_notification_path(app_root_path)
        if not os.path.exists(notification_path):
            welcome_notification = self.create_notification(
                title="欢迎使用PKUHUB",
                content="欢迎使用PKUHUB！\n\n这是一个由北大学生自主开发的学习资源共享网站，旨在促进校内知识流通，提高学习效率。\n\n如有任何问题或建议，请联系管理员。",
                creator_id=1,  # 假设ID为1的是管理员
                target_role="all",
            )

            with open(notification_path, "w", encoding="utf-8") as f:
                json.dump([welcome_notification], f, ensure_ascii=False, indent=2)

            return True
        return False

    def delete_notification(
        self, notification_id: str, user_id: int, app_root_path: str
    ) -> bool:
        """
        删除单个通知（只有管理员可以完全删除，普通用户只能删除已读的自己可见的通知）

        参数:
            notification_id: 通知ID
            user_id: 用户ID
            app_root_path: 应用根目录

        返回:
            是否删除成功
        """
        notifications = self.load_notifications(app_root_path)

        for i, notification in enumerate(notifications):
            if notification["id"] == notification_id:
                # 检查是否是管理员发布的通知，普通用户不能删除
                if notification.get(
                    "created_by"
                ) == user_id or user_id in notification.get("read_by", []):
                    # 从列表中删除通知
                    del notifications[i]
                    self.save_notifications(notifications, app_root_path)
                    return True

        return False

    def delete_all_read_notifications(
        self, user_id: int, is_admin: bool, app_root_path: str
    ) -> int:
        """
        删除用户的所有已读通知

        参数:
            user_id: 用户ID
            is_admin: 用户是否为管理员
            app_root_path: 应用根目录

        返回:
            删除的通知数量
        """
        notifications = self.load_notifications(app_root_path)
        original_count = len(notifications)

        # 过滤出未读通知和不可见的通知
        filtered_notifications = []
        for notification in notifications:
            # 检查通知是否为该用户可见
            is_visible = notification["target_role"] == "all" or (
                is_admin and notification["target_role"] == "admin"
            )

            # 检查是否已读
            is_read = user_id in notification.get("read_by", [])

            # 保留未读的通知或不可见的通知
            if not is_visible or not is_read:
                filtered_notifications.append(notification)

        # 保存过滤后的通知列表
        if len(filtered_notifications) < original_count:
            self.save_notifications(filtered_notifications, app_root_path)
            return original_count - len(filtered_notifications)

        return 0


# 创建全局通知管理器实例
notification_manager = AppNotificationManager()
