from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user, logout_user
from werkzeug.security import check_password_hash, generate_password_hash
from database import db,get_followers,get_following,follow_user,unfollow_user
from database.models import (
    Material,
    User,
    UserLike,
    UserDownloadLimit,
    Course,  # 添加 Course 导入
)
import database
from utils.forms import UpdateProfileForm, ChangePasswordForm
from sqlalchemy import func, or_  # 添加 or_ 导入，用于构建OR条件查询

# 创建蓝图
profile_bp = Blueprint("profile", __name__)


# 个人资料页面
@profile_bp.route("/profile")
@login_required
def profile():
    # 获取当前标签页
    tab = request.args.get('tab', 'uploads')
    # 获取搜索查询参数
    query = request.args.get('query', '')
    sort_by = request.args.get('sort_by', '最新上传')
    
    # 获取用户上传的资料
    if query:
        # 使用高级查询函数进行搜索 - 现在支持课程名称搜索
        uploads, _ = database.query_materials(
            user_id=current_user.id,
            keyword=query,
            order_by='newest' if sort_by == '最新上传' else 
                    'downloads' if sort_by == '最多下载' else 
                    'title' if sort_by == '按标题' else 'newest'
        )
    else:
        # 获取所有用户上传的资料
        uploads = database.get_material(method="user_id", key=current_user.id)
        
        # 根据排序方式处理
        if sort_by == '最新上传':
            uploads = sorted(uploads, key=lambda m: m.created_at, reverse=True)
        elif sort_by == '最多下载':
            uploads = sorted(uploads, key=lambda m: m.stats.download_count if hasattr(m.stats, 'download_count') else 0, reverse=True)
        elif sort_by == '按标题':
            uploads = sorted(uploads, key=lambda m: m.title)

    # 获取用户收藏的资料 - 也支持课程名称搜索
    if query:
        liked_materials_query = Material.query.join(
            UserLike, Material.id == UserLike.material_id
        ).filter(
            UserLike.user_id == current_user.id
        ).join(
            Course, Material.course_id == Course.id
        ).filter(
            or_(
                Material.title.ilike(f'%{query}%'),
                Course.name.ilike(f'%{query}%')
            )
        )
    else:
        liked_materials_query = Material.query.join(
            UserLike, Material.id == UserLike.material_id
        ).filter(UserLike.user_id == current_user.id)
    
    liked_materials = liked_materials_query.all()
    
    # 根据排序方式处理收藏的资料
    if sort_by == '最新上传':
        liked_materials = sorted(liked_materials, key=lambda m: m.created_at, reverse=True)
    elif sort_by == '最多下载':
        liked_materials = sorted(liked_materials, key=lambda m: m.stats.download_count if hasattr(m.stats, 'download_count') else 0, reverse=True)
    elif sort_by == '按标题':
        liked_materials = sorted(liked_materials, key=lambda m: m.title)

    # 计算总下载量
    total_downloads = sum(material.stats.download_count for material in uploads)
    
    # 计算资料获得的总收藏数
    total_likes = db.session.query(func.count(UserLike.user_id)).join(
        Material, UserLike.material_id == Material.id
    ).filter(Material.user_id == current_user.id).scalar() or 0
    
    # 获取粉丝数量和列表
    followers = get_followers(current_user.id)
    followers_count = len(followers)

    # 获取今日已下载次数
    import datetime
    today = datetime.date.today()
    user_limit = UserDownloadLimit.query.filter_by(
        user_id=current_user.id, date=today
    ).first()
    download_today = user_limit.download_count if user_limit else 0
    
    # 获取关注的用户列表 - 使用User的方法
    following_users = get_following(current_user.id)

    return render_template(
        "profile.html",
        user=current_user,
        uploads=uploads,
        liked_materials=liked_materials,
        total_downloads=total_downloads,
        total_likes=total_likes,
        followers=followers,
        followers_count=followers_count,
        download_today=download_today,
        following_users=following_users,
        is_admin=current_user.is_admin,
        query=query,
        sort_by=sort_by,
        tab=tab
    )


# 编辑个人资料
@profile_bp.route("/edit_profile", methods=["GET", "POST"])
@login_required
def edit_profile():
    profile_form = UpdateProfileForm()
    password_form = ChangePasswordForm()

    if request.method == "GET":
        profile_form.username.data = current_user.username
        profile_form.bio.data = current_user.bio

    if profile_form.validate_on_submit():
        # 检查用户名是否已被其他用户使用 (添加这个检查)
        new_username = profile_form.username.data
        if new_username != current_user.username:  # 只有在用户名变化时才检查
            existing_user = database.get_user(method="username", key=new_username)
            if existing_user and existing_user[0].id != current_user.id:
                flash("该用户名已被使用，请选择其他用户名")
                return render_template(
                    "edit_profile.html", 
                    profile_form=profile_form, 
                    password_form=password_form
                )
        
        update_data = {
            "username": profile_form.username.data,
            "bio": profile_form.bio.data,
        }
        # 处理头像上传
        if profile_form.avatar.data:
            from utils.other import handle_avatar_upload

            avatar_filename = handle_avatar_upload(
                profile_form.avatar.data, current_user.id
            )
            if avatar_filename:
                update_data["avatar"] = avatar_filename

        updated_user = database.update_user(current_user.id, **update_data)
        if updated_user:
            flash("个人资料更新成功！")
            return redirect(url_for("profile.profile"))
        else:
            flash("更新个人资料失败")
            return render_template(
                "edit_profile.html",
                profile_form=profile_form,
                password_form=password_form,
            )

    return render_template(
        "edit_profile.html", profile_form=profile_form, password_form=password_form
    )


# 修改密码
@profile_bp.route("/change_password", methods=["GET", "POST"])
@login_required
def change_password():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        if check_password_hash(current_user.password_hash, form.current_password.data):
            if check_password_hash(current_user.password_hash, form.new_password.data):
                flash("新密码不能与当前密码相同", "danger")
            else:
                new_password_hash = generate_password_hash(form.new_password.data)
                database.session.query(User).filter_by(id=current_user.id).update(
                    {"password_hash": new_password_hash}
                )
                database.session.commit()
                flash("密码修改成功，请重新登录", "success")
                logout_user()
                return redirect(url_for("auth.login"))
        else:
            flash("当前密码错误", "danger")
    return render_template("change_password.html", form=form)

# 关注/取消关注用户API
@profile_bp.route("/follow/<int:user_id>", methods=["POST"])
@login_required
def follow(user_id):
    user_to_follow = User.query.get_or_404(user_id)
    
    if current_user.id == user_id:
        return jsonify({"success": False, "message": "不能关注自己"})
    
    if follow_user(current_user.id,user_to_follow.id):
        return jsonify({"success": True, "message": f"成功关注 {user_to_follow.username}"})
    else:
        return jsonify({"success": False, "message": "您已经关注了该用户"})

# 取消关注用户API
@profile_bp.route("/unfollow/<int:user_id>", methods=["POST"])
@login_required
def unfollow(user_id):
    user_to_unfollow = User.query.get_or_404(user_id)
    
    if unfollow_user(current_user.id,user_to_unfollow.id):
        return jsonify({"success": True, "message": f"已取消关注 {user_to_unfollow.username}"})
    else:
        return jsonify({"success": False, "message": "您尚未关注该用户"})

# 查看用户资料页面
@profile_bp.route("/user/<int:user_id>")
@login_required
def view_user(user_id):
    user = User.query.get_or_404(user_id)
    
    # 获取搜索查询参数
    query = request.args.get('query', '')
    sort_by = request.args.get('sort_by', '最新上传')
    
    # 获取用户上传的资料
    if query:
        # 使用高级查询函数进行搜索 - 现在支持课程名称搜索
        uploads, _ = database.query_materials(
            user_id=user.id,
            keyword=query,
            order_by='newest' if sort_by == '最新上传' else 
                    'downloads' if sort_by == '最多下载' else 
                    'title' if sort_by == '按标题' else 'newest'
        )
    else:
        # 获取所有用户上传的资料
        uploads = database.get_material(method="user_id", key=user.id)
        
        # 根据排序方式处理
        if sort_by == '最新上传':
            uploads = sorted(uploads, key=lambda m: m.created_at, reverse=True)
        elif sort_by == '最多下载':
            uploads = sorted(uploads, key=lambda m: m.stats.download_count, reverse=True)
        elif sort_by == '按标题':
            uploads = sorted(uploads, key=lambda m: m.title)
    
    # 计算总下载量
    total_downloads = sum(material.stats.download_count for material in uploads)
    
    # 计算资料获得的总收藏数
    total_likes = db.session.query(func.count(UserLike.user_id)).join(
        Material, UserLike.material_id == Material.id
    ).filter(Material.user_id == user.id).scalar() or 0
    
    # 获取粉丝列表和数量
    followers = get_followers(user.id)
    followers_count = len(followers)
    
    is_following = database.is_following(current_user.id,user.id) if current_user.is_authenticated else False
    
    return render_template(
        "user_profile.html",
        user=user,
        uploads=uploads,
        total_downloads=total_downloads,
        total_likes=total_likes,
        followers=followers,
        followers_count=followers_count,
        is_following=is_following,
        query=query,
        sort_by=sort_by
    )
