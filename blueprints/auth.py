import asyncio
from sre_constants import SUCCESS
from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    request,
    flash,
    jsonify,
    session,
)

from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash  # 添加这一行
import database
from database.models import User  # 添加这一行，因为reset_password中直接引用了User模型
from utils.forms import (
    LoginForm,
    RegisterForm,
    RequestResetPasswordForm,
    ResetPasswordForm,
)
import notification

# 邮件工具：生成验证码、发送邮件、保存验证码、验证码校验功能
from datetime import datetime

# 时间处理：获取当前时间

# 创建蓝图
auth_bp = Blueprint("auth", __name__)


# 登录路由
@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        users = database.get_user(method="email", key=form.email.data)
        user = users[0] if users else None
        if not user:
            flash("账户不存在")
            return render_template("login.html", form=form)

        if user and user.check_password(form.password.data):
            # 这里使用了 remember 参数
            login_user(user, remember=form.remember.data)
            next_page = request.args.get("next")
            return redirect(next_page or url_for("browse.index"))
        if not user.check_password(form.password.data):
            flash("邮箱或密码不正确")
    elif request.method == "POST":
        print("表单验证失败，可能是CSRF问题")
        if "csrf_token" not in request.form:
            print("CSRF令牌缺失")
            flash("安全验证失败，请刷新页面重试")
        else:
            print(f"表单错误: {form.errors}")
    return render_template("login.html", form=form)


# 注册路由
@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        # 检查邮箱是否结尾是stu.pku.edu.cn
        if not form.email.data.endswith("@stu.pku.edu.cn") or form.email.data.endswith(
            "@pku.edu.cn"
        ):
            flash("请使用北京大学学生邮箱(@stu.pku.edu.cn 或 @pku.edu.cn)")
            return render_template("register.html", form=form)

        # 检查用户是否已经存在
        existing_email = database.get_user(method="email", key=form.email.data)
        if existing_email:
            flash("该邮箱已被注册")
            return render_template("register.html", form=form)

        # 检查用户名是否重复
        existing_username = database.get_user(method="username", key=form.username.data)
        if existing_username:
            flash("该用户名已被使用")
            return render_template("register.html", form=form)

        # 启用验证码验证
        if not notification.verify_code(form.email.data, form.verification_code.data):
            flash("验证码不正确或已过期")
            return render_template("register.html", form=form)

        # 创建新用户
        new_user = database.create_user(
            username=form.username.data,
            email=form.email.data,
            password=form.password.data,  # 直接传递密码，不需要预先哈希
            is_email_verified=True,  # 已通过验证码验证
        )

        flash("注册成功！请登录")
        return redirect(url_for("auth.login"))
    return render_template("register.html", form=form)


# 删除这个异步包装函数，直接使用同步版本
def send_verification_codes_sync(email_list, subject="验证码 - PKUHUB", timeout=60):
    """同步调用验证码发送函数

    参数:
        email_list: 接收验证码的邮箱列表
        subject: 邮件标题
        timeout: 发送超时时间（秒）

    返回:
        包含(success, email, code)三元组的列表
    """
    # 直接调用同步函数，不需要asyncio
    return notification.send_verification_codes(email_list, subject, timeout)


@auth_bp.route("/send_verification_code", methods=["POST"])
def send_verification_code():
    data = request.get_json()
    email = data.get("email")
    username = data.get("username")  # 可选，如果前端传递了用户名

    # 验证邮箱格式
    if not email or not (
        email.endswith("@stu.pku.edu.cn") or email.endswith("@pku.edu.cn")
    ):
        return jsonify({"success": False, "message": "请使用北京大学邮箱"})

    # 检查是否已被注册
    existing_user = database.get_user(method="email", key=email)
    if existing_user:
        return jsonify({"success": False, "message": "该邮箱已被注册"})
    
    # 如果提供了用户名，也检查用户名
    if username:
        existing_username = database.get_user(method="username", key=username)
        if existing_username:
            return jsonify({"success": False, "message": "该用户名已被使用"})

    # 检查是否短时间内多次请求验证码（防止频繁请求攻击）
    last_request_time_key = f"last_verification_request_{email}"
    if last_request_time_key in session:
        last_time = session[last_request_time_key]
        elapsed_seconds = datetime.now().timestamp() - last_time
        if elapsed_seconds < 60:  # 1分钟内不能重复请求
            remaining = int(60 - elapsed_seconds)
            return jsonify(
                {"success": False, "message": f"请求过于频繁，请在{remaining}秒后重试"}
            )

    # 记录本次请求时间
    session[last_request_time_key] = datetime.now().timestamp()

    # 使用同步函数发送验证码
    results = send_verification_codes_sync([email])

    # 检查结果
    if results and len(results) > 0:
        success, _, _ = results[0]  # 获取第一个结果，因为只发送了一封邮件
        if success:
            return jsonify({"success": True})

    return jsonify({"success": False, "message": "发送邮件失败，请稍后重试"})


# 添加邮箱检查路由
@auth_bp.route("/check_email", methods=["POST"])
def check_email():
    """检查邮箱是否已被注册"""
    data = request.get_json()
    email = data.get("email")
    
    # 验证邮箱格式
    if not email or not (
        email.endswith("@stu.pku.edu.cn") or email.endswith("@pku.edu.cn")
    ):
        return jsonify({"available": False, "message": "请使用北京大学邮箱"})
    
    # 检查是否已被注册
    existing_user = database.get_user(method="email", key=email)
    is_available = not existing_user
    
    return jsonify({
        "available": is_available,
        "message": "此邮箱可以使用" if is_available else "该邮箱已被注册"
    })


# 添加用户名检查路由
@auth_bp.route("/check_username", methods=["POST"])
def check_username():
    """检查用户名是否已被使用"""
    data = request.get_json()
    username = data.get("username")
    
    if not username:
        return jsonify({"available": False, "message": "请输入用户名"})
    
    # 检查用户名是否已被使用
    existing_user = database.get_user(method="username", key=username)
    is_available = not existing_user
    
    return jsonify({
        "available": is_available,
        "message": "此用户名可以使用" if is_available else "该用户名已被使用"
    })


# 忘记密码路由
@auth_bp.route("/forgot_password", methods=["GET", "POST"])
def forgot_password():
    """忘记密码页面 - 请求验证码"""
    # 如果用户已经登录，重定向到主页
    if current_user.is_authenticated:
        return redirect(url_for("browse.index"))

    form = RequestResetPasswordForm()

    if form.validate_on_submit():
        email = form.email.data

        # 检查邮箱格式
        if not (email.endswith("@stu.pku.edu.cn") or email.endswith("@pku.edu.cn")):
            flash("请使用北京大学邮箱")
            return render_template("forgot_password.html", form=form)

        # 检查该邮箱是否注册
        user = database.get_user(method="email", key=email)
        if not user:
            flash("该邮箱尚未注册")
            return render_template("forgot_password.html", form=form)

        # 检查是否短时间内多次请求验证码
        last_request_time_key = f"last_reset_request_{email}"
        if last_request_time_key in session:
            last_time = session[last_request_time_key]
            elapsed_seconds = datetime.now().timestamp() - last_time
            if elapsed_seconds < 60:  # 1分钟内不能重复请求
                remaining = int(60 - elapsed_seconds)
                flash(f"请求过于频繁，请在{remaining}秒后重试")
                return render_template("forgot_password.html", form=form)

        # 记录本次请求时间
        session[last_request_time_key] = datetime.now().timestamp()

        # 使用同步函数发送验证码
        results = send_verification_codes_sync(
            [email], subject="重置密码验证码 - PKUHUB"
        )

        if results and len(results) > 0:
            success, _, _ = results[0]
            if success:
                flash("验证码已发送到您的邮箱，请查收并完成密码重置")
                return redirect(url_for("auth.reset_password", email=email))

        flash("发送验证码失败，请稍后重试")

    return render_template("forgot_password.html", form=form)


# 重置密码路由
@auth_bp.route("/reset_password", methods=["GET", "POST"])
def reset_password():
    """重置密码页面 - 使用验证码设置新密码"""
    # 如果用户已经登录，重定向到主页
    if current_user.is_authenticated:
        return redirect(url_for("browse.index"))

    # 从URL参数获取邮箱(如果有)
    email = request.args.get("email", "")

    form = ResetPasswordForm()
    if email:
        form.email.data = email

    if form.validate_on_submit():
        email = form.email.data
        code = form.verification_code.data

        # 验证邮箱是否存在
        user = database.get_user(method="email", key=email)
        if not user:
            flash("该邮箱尚未注册")
            return render_template("reset_password.html", form=form)

        # 验证验证码
        if not notification.verify_code(email, code):
            flash("验证码不正确或已过期")
            return render_template("reset_password.html", form=form)

        # 更新密码
        new_password_hash = generate_password_hash(form.new_password.data)
        user = user[0] if isinstance(user, list) else user
        database.update_user(user.id, password_hash=new_password_hash)
        flash("密码已重置，请使用新密码登录")
        return redirect(url_for("auth.login"))

    return render_template("reset_password.html", form=form)


# 登出路由
@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("您已成功登出")
    return redirect(url_for("browse.index"))
