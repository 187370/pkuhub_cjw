import os
from flask import current_app
from functools import wraps
from flask_login import current_user
from flask import abort, session, request
import uuid
from PIL import Image  # 添加缺少的PIL导入


# 管理员权限验证装饰器
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)  # 无权限访问
        return f(*args, **kwargs)

    return decorated_function


# 确保默认头像文件存在
def ensure_default_avatar():
    """确保默认头像文件存在"""
    default_avatar_path = os.path.join(
        current_app.config["AVATAR_FOLDER"], "default_avatar.png"
    )
    if not os.path.exists(default_avatar_path):
        try:
            # 创建一个简单的灰色头像，添加"PKU"文字
            img = Image.new("RGB", (200, 200), color=(200, 200, 200))

            # 可选：添加更好的默认头像设计
            from PIL import ImageDraw, ImageFont

            draw = ImageDraw.Draw(img)
            try:
                # 尝试加载字体（如果不可用会使用默认字体）
                font = ImageFont.truetype("arial.ttf", 60)
            except IOError:
                font = ImageFont.load_default()

            # 在头像中心添加文字"PKU"
            w, h = img.size
            text = "PKU"
            text_w, text_h = (
                draw.textsize(text, font=font)
                if hasattr(draw, "textsize")
                else (60, 60)
            )
            draw.text(
                ((w - text_w) // 2, (h - text_h) // 2),
                text,
                fill=(144, 0, 35),
                font=font,
            )

            os.makedirs(os.path.dirname(default_avatar_path), exist_ok=True)
            img.save(default_avatar_path)
            print(f"已创建默认头像: {default_avatar_path}")

            # 复制一份到pkuhub-logo.jpg作为网站logo
            logo_path = os.path.join(
                current_app.config["AVATAR_FOLDER"], "pkuhub-8人.jpg"
            )
            if not os.path.exists(logo_path):
                img.save(logo_path)
                print(f"已创建网站logo: {logo_path}")

        except Exception as e:
            print(f"创建默认头像失败: {str(e)}")
            print("请手动创建默认头像文件")


# 处理头像上传和裁剪
def handle_avatar_upload(avatar_file, user_id):
    """处理头像上传、裁剪和保存"""
    try:
        # 生成唯一文件名
        _, ext = os.path.splitext(avatar_file.filename)
        avatar_filename = f"{uuid.uuid4().hex}{ext}"

        # 创建用户的头像目录（如果不存在）
        avatar_folder = os.path.join(current_app.config["AVATAR_FOLDER"], str(user_id))
        os.makedirs(avatar_folder, exist_ok=True)

        # 保存上传的文件
        avatar_path = os.path.join(avatar_folder, avatar_filename)
        avatar_file.save(avatar_path)

        # 使用PIL处理图片
        img = Image.open(avatar_path)
        # 裁剪为正方形
        width, height = img.size
        size = min(width, height)
        left = (width - size) // 2
        top = (height - size) // 2
        right = left + size
        bottom = top + size
        img = img.crop((left, top, right, bottom))
        # 调整大小
        img = img.resize((200, 200), Image.Resampling.LANCZOS)
        # 保存处理后的图片
        img.save(avatar_path)

        # 返回数据库需要保存的路径（相对路径）
        return f"{user_id}/{avatar_filename}"
    except Exception as e:
        print(f"处理头像时出错: {str(e)}")
        return None


def is_remembered_login():
    """检测用户是否通过记住我功能自动登录"""
    if not current_user.is_authenticated:
        return False

    # 检查是否有活跃会话但没有显式登录记录
    return "_remember_me" in request.cookies and "logged_in" not in session
