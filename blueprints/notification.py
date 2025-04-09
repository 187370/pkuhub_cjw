from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from permission import admin_required
from datetime import datetime
import json
import os
from flask import current_app

# 创建蓝图
notification_bp = Blueprint("notification", __name__)

# 通知存储路径
NOTIFICATION_FILE = "notifications.json"


def get_notification_path():
    """获取通知存储文件的完整路径"""
    return os.path.join(current_app.root_path, NOTIFICATION_FILE)


def load_notifications():
    """加载所有通知"""
    try:
        if os.path.exists(get_notification_path()):
            with open(get_notification_path(), "r", encoding="utf-8") as f:
                return json.load(f)
        return []
    except Exception as e:
        print(f"加载通知失败: {e}")
        return []


def save_notifications(notifications):
    """保存通知到文件"""
    try:
        with open(get_notification_path(), "w", encoding="utf-8") as f:
            json.dump(notifications, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"保存通知失败: {e}")
        return False


@notification_bp.route("/notifications")
@login_required
def view_notifications():
    """查看所有通知"""
    all_notifications = load_notifications()
    # 过滤出当前用户可见的通知(全部通知、指向特定角色的通知或关注通知)
    user_notifications = []
    for notification in all_notifications:
        # 检查是否是全体通知或针对特定角色
        if notification["target_role"] == "all" or (
            current_user.is_admin and notification["target_role"] == "admin"
        ) or (
            notification["target_role"] == "followers" and 
            current_user.id in notification.get("for_users", [])
        ):
            # 添加一个标记，指示当前用户是否已读该通知
            notification["is_read"] = current_user.id in notification.get("read_by", [])
            user_notifications.append(notification)

    return render_template("notifications.html", notifications=user_notifications)


@notification_bp.route("/notifications/create", methods=["GET", "POST"])
@login_required
@admin_required
def create_notification():
    """创建新通知"""
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        content = request.form.get("content", "").strip()
        target_role = request.form.get("target_role", "all")

        if not title or not content:
            flash("标题和内容不能为空")
            return redirect(url_for("notification.create_notification"))

        # 创建新通知
        new_notification = {
            "id": str(datetime.now().timestamp()),
            "title": title,
            "content": content,
            "target_role": target_role,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "created_by": current_user.id,
            "read_by": [],  # 记录已读用户的ID
        }

        # 加载现有通知并添加新通知
        notifications = load_notifications()
        notifications.append(new_notification)

        if save_notifications(notifications):
            flash("通知发布成功！")
        else:
            flash("通知发布失败，请重试")

        return redirect(url_for("notification.view_notifications"))

    return render_template("create_notification.html")


@notification_bp.route("/notifications/<notification_id>/mark_read", methods=["POST"])
@login_required
def mark_read(notification_id):
    """标记通知为已读"""
    notifications = load_notifications()

    for notification in notifications:
        if notification["id"] == notification_id:
            if "read_by" not in notification:
                notification["read_by"] = []

            if current_user.id not in notification["read_by"]:
                notification["read_by"].append(current_user.id)
                save_notifications(notifications)
                return jsonify({"success": True})

    return jsonify({"success": False, "message": "通知不存在"})


@notification_bp.route("/notifications/unread_count")
@login_required
def unread_count():
    """获取未读通知数量"""
    all_notifications = load_notifications()
    unread_count = 0

    for notification in all_notifications:
        if (notification["target_role"] == "all" or 
            (current_user.is_admin and notification["target_role"] == "admin") or
            (notification["target_role"] == "followers" and current_user.id in notification.get("for_users", []))
        ):
            if current_user.id not in notification.get("read_by", []):
                unread_count += 1

    return jsonify({"count": unread_count})
