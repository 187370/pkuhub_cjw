from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
import database
from database.models import User, Material, Course, Department
from utils.forms import AdminEditUserForm
from permission import admin_required
from datetime import datetime, timedelta
import os
from flask import current_app

# 创建蓝图
admin_bp = Blueprint("admin", __name__)


# 管理员后台主页
@admin_bp.route("/admin/dashboard")
@login_required
def admin_dashboard():
    if not current_user.is_admin:
        flash("您没有权限访问管理后台")
        return redirect(url_for("profile.profile"))
    
    # 获取搜索和筛选参数
    material_query = request.args.get('material_query', '')
    material_sort = request.args.get('material_sort', '最新上传')
    
    # 获取所有用户
    users = User.query.all()
    
    # 获取最近上传资料
    if material_query:
        # 使用高级查询
        recent_materials, _ = database.query_materials(
            keyword=material_query,
            order_by='newest' if material_sort == '最新上传' else 
                    'downloads' if material_sort == '最多下载' else 
                    'title' if material_sort == '按标题' else 'newest',
        )
    else:
        # 获取所有资料
        recent_materials = database.get_material(method="all")
        
        # 根据排序方式处理
        if material_sort == '最新上传':
            recent_materials = sorted(recent_materials, key=lambda m: m.created_at, reverse=True)
        elif material_sort == '最多下载':
            recent_materials = sorted(recent_materials, key=lambda m: m.stats.download_count if hasattr(m, 'stats') and m.stats else 0, reverse=True)
        elif material_sort == '按标题':
            recent_materials = sorted(recent_materials, key=lambda m: m.title)
    
    # 限制显示数量
    recent_materials = recent_materials[:50] if len(recent_materials) > 50 else recent_materials
    
    # 计算总下载量用于显示
    download_count = sum(m.stats.download_count for m in database.get_material(method="all") if hasattr(m, 'stats') and m.stats)
    
    # 统计数据
    user_count = len(users)
    material_count = Material.query.count()
    course_count = Course.query.count()
    
    return render_template(
        "admin_dashboard.html", 
        users=users, 
        recent_materials=recent_materials, 
        user_count=user_count, 
        material_count=material_count,
        course_count=course_count,
        material_query=material_query,
        material_sort=material_sort,
        download_count=download_count
    )


# 编辑用户资料
@admin_bp.route("/admin/user/<int:user_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def edit_user(user_id):
    """管理员编辑用户资料"""
    # 使用database模块获取用户
    users = database.get_user(method="id", key=user_id)
    if not users:
        flash("用户不存在")
        return redirect(url_for("admin.admin_dashboard"))

    user = users[0] if isinstance(users, list) else users

    # 创建表单并预填充数据
    form = AdminEditUserForm()

    if request.method == "GET":
        form.username.data = user.username
        form.email.data = user.email
        form.bio.data = user.bio
        form.is_admin.data = user.is_admin

    if form.validate_on_submit():
        # 检查用户名是否已被其他用户使用 (添加这个检查)
        new_username = form.username.data
        if new_username != user.username:  # 只有在用户名变化时才检查
            existing_user = database.get_user(method="username", key=new_username)
            if existing_user and (isinstance(existing_user, list) and existing_user[0].id != user_id or 
                                existing_user.id != user_id):
                flash(f"用户名 '{new_username}' 已被其他用户使用，请选择其他用户名")
                return render_template("admin_edit_user.html", user=user, form=form)
                
        # 准备更新数据
        update_data = {
            "username": form.username.data,
            "email": form.email.data,
            "bio": form.bio.data,
        }

        # 使用database模块更新用户
        updated_user = database.update_user(user_id, **update_data)
        if updated_user:
            flash(f"用户 {updated_user.username} 资料已更新")
            return redirect(url_for("admin.admin_dashboard"))
        else:
            flash("更新用户资料失败")

    return render_template("admin_edit_user.html", user=user, form=form)


# 删除用户
@admin_bp.route("/admin/user/<int:user_id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_user(user_id):
    """管理员删除用户账号"""
    # 防止管理员删除自己
    if user_id == current_user.id:
        return jsonify({"success": False, "message": "不能删除自己的账号"})

    # 获取用户
    users = database.get_user(method="id", key=user_id)
    if not users:
        return jsonify({"success": False, "message": "用户不存在"})

    user = users[0] if isinstance(users, list) else users

    # 防止删除管理员
    if user.is_admin:
        return jsonify({"success": False, "message": "不能删除管理员账号"})

    # 删除用户
    if database.delete_user(user_id):
        return jsonify({"success": True, "message": "用户已成功注销"})
    else:
        return jsonify({"success": False, "message": "删除用户失败"})
