from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    request,
    flash,
    jsonify,
    current_app,
)
from flask_login import login_required, current_user
from database import db,get_followers,is_following
from database.models import (
    Course,
    Material,
    Department,
    Comment,
    MaterialStats,
    UserDownloadLimit,
) 
import database
from utils.forms import UploadForm, CommentForm, EditMaterialForm
from utils.secure_filename_cn import secure_filename_cn
from datetime import datetime, date
import os
from werkzeug.utils import secure_filename
import json
import pytz

# 创建蓝图
material_bp = Blueprint("material", __name__)


# 上传资料路由
@material_bp.route("/upload", methods=["GET", "POST"])
@login_required
def upload():
    form = UploadForm()
    
    # 加载所有部门到表单的选择字段
    departments = Department.query.all()
    form.department.choices = [(d.id, d.name) for d in departments]
    
    # 确保course_type的选项也已经加载
    course_types = database.get_course_types()  # 假设有这个函数
    if course_types and not form.course_type.choices:
        form.course_type.choices = [("", "选择课程类型")] + [(t, t) for t in course_types]
    
    if form.validate_on_submit():
        # 处理文件上传
        f = form.file.data
        original_filename = f.filename  # 保留原始文件名包括中文
        secure_name = secure_filename_cn(original_filename)  # 使用自定义函数处理文件名

        # 保存原始文件名和扩展名
        _, file_extension = os.path.splitext(original_filename)

        # 检查文件扩展名
        if not file_extension:
            flash("文件必须有扩展名")
            return render_template("upload.html", form=form)

        # 创建用户上传目录
        user_upload_path = os.path.join(
            current_app.config["UPLOAD_FOLDER"], str(current_user.id)
        )
        os.makedirs(user_upload_path, exist_ok=True)

        # 保存文件，使用安全处理后的文件名
        file_path = os.path.join(user_upload_path, secure_name)
        f.save(file_path)

        # 获取或创建课程
        existing_course = Course.query.filter_by(
            name=form.course.data, department_id=form.department.data
        ).first()

        # 自动生成课程代码: 使用更长更唯一的课程代码
        import uuid

        # 当创建新课程时
        if not existing_course:
            # 生成更健壮的课程代码，格式：课程名前缀(最多5个字符) + 时间戳 + 随机字符串
            base_code = form.course.data.upper().replace(" ", "")[:5]
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')  # 年月日时分秒
            random_suffix = str(uuid.uuid4())[:8]  # 添加8位随机字符
            generated_code = f"{base_code}{timestamp}{random_suffix}"
            
            # 确保课程类型不为空
            course_type = form.course_type.data
            if not course_type:
                course_type = "其他"  # 设置默认值
            
            # 使用database模块创建课程，传入必要参数，包括类型
            try:
                course_obj = database.create_course(
                    name=form.course.data,
                    code=generated_code,
                    department_id=form.department.data,
                    type=course_type,  # 修正：使用course_type变量，而不是表单对象
                    credits=0.0,  # 默认学分
                    hours=0,  # 默认学时
                )
                
                # 验证课程是否成功创建
                if course_obj is None:
                    flash("创建课程失败，请稍后重试")
                    return render_template("upload.html", form=form)
                    
                course = course_obj  # 从返回值中获取课程对象
            except Exception as e:
                flash(f"创建课程时出错: {str(e)}")
                return render_template("upload.html", form=form)
        else:
            course = existing_course

        # 创建资料记录
        material_data = {
            "title": form.title.data,
            "description": form.description.data,
            "file_path": os.path.join(str(current_user.id), secure_name),
            "file_type": form.material_type.data,
            "original_filename": original_filename,
            "file_extension": file_extension,
            "course_id": course.id,  # 现在可以正确访问course.id
            "user_id": current_user.id,
            "semester": form.semester.data,
            "created_at": datetime.now(),  # 使用导入的 datetime 类
        }

        # 使用database模块创建资料
        material = database.create_material(**material_data)

        if material:
            # 创建通知提醒关注该用户的人
            notify_followers(current_user.id, material)

        flash("资料上传成功!")
        return redirect(url_for("browse.index"))

    return render_template("upload.html", form=form)


# 资料详情页路由
@material_bp.route("/material/<int:material_id>", methods=["GET", "POST"])
@login_required  # 添加登录验证装饰器
def material_view(material_id):
    materials = database.get_material(method="id", key=material_id)
    if not materials:
        flash("资料不存在或已被删除", "error")
        return redirect(url_for("browse.index"))

    # 如果返回的是列表，则取第一个元素
    material = materials[0] if isinstance(materials, list) else materials

    # 增加浏览量
    material.increment_view_count()

    form = CommentForm()

    # 处理评论提交
    if form.validate_on_submit() and current_user.is_authenticated:
        # 判断是否是AJAX请求
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        
        # 创建评论时使用中国时区时间
        china_tz = pytz.timezone('Asia/Shanghai')
        now = datetime.now().replace(tzinfo=pytz.utc).astimezone(china_tz)
        
        # 使用database模块创建评论 - 保存原始文本，前端会处理渲染
        comment = database.create_comment(
            content=form.content.data, 
            user_id=current_user.id, 
            material_id=material_id,
            created_at=now
        )
        
        # 如果是AJAX请求，返回JSON响应
        if is_ajax:
            avatar_url = current_user.avatar
            if not avatar_url.startswith(('http://', 'https://')):
                avatar_url = current_user.avatar
                
            return jsonify({
                'success': True,
                'comment': {
                    'id': comment.id,
                    'content': comment.content,  # 返回原始内容，由前端处理Markdown和LaTeX渲染
                    'created_at': comment.created_at.strftime('%Y-%m-%d %H:%M'),
                    'user': {
                        'id': current_user.id,
                        'username': current_user.username,
                        'avatar': avatar_url
                    },
                    'can_delete': True
                }
            })
            
        # 传统表单提交的响应
        flash("评论已添加")
        return redirect(url_for("material.material_view", material_id=material_id))

    comments = database.get_comment(method="material_id", key=material_id)

    # 检查当前用户是否点赞过该资料
    is_liked = material.is_liked_by(
        current_user.id if current_user.is_authenticated else None
    )

    # 检查当前用户是否关注了作者
    is_following = False
    if current_user.is_authenticated and current_user.id != material.user_id:

        is_following = database.is_following(current_user.id,material.uploader.id)

    return render_template(
        "material.html",  # 确认使用这个模板文件
        material=material,
        form=form,
        comments=comments,
        is_liked=is_liked,
        is_following=is_following,
    )


@material_bp.route("/download/<int:material_id>")
@login_required
def download(material_id):
    try:
        # 获取资料信息
        materials = database.get_material(method="id", key=material_id)
        if not materials:
            flash("资料不存在或已被删除", "error")
            return redirect(url_for("browse.index"))
            
        material = materials[0] if isinstance(materials, list) else materials
        
        # 管理员不受下载次数限制
        if not current_user.is_admin:
            # 检查用户今日下载次数
            today = date.today()
            user_limit = UserDownloadLimit.query.filter_by(
                user_id=current_user.id, date=today
            ).first()

            # 每日下载限制次数
            daily_limit = 10

            # 如果今天没有下载记录，创建新记录
            if not user_limit:
                user_limit = UserDownloadLimit(
                    user_id=current_user.id, date=today, download_count=0
                )
                db.session.add(user_limit)

            # 检查是否超过限制
            if user_limit.download_count >= daily_limit:
                flash(f"您今日的下载次数已达上限({daily_limit}次)", "error")
                return redirect(url_for("material.material_view", material_id=material_id))
                
            # 增加用户下载计数
            user_limit.download_count += 1
            db.session.commit()
        
        # 构建完整的文件路径
        file_path = material.file_path
        full_path = os.path.join(current_app.config["UPLOAD_FOLDER"], file_path)
        print(f"下载路径: {full_path}")
        print(f"文件存在: {os.path.exists(full_path)}")

        if not os.path.exists(full_path):
            flash("文件不存在或已被删除", "error")
            return redirect(url_for("material.material_view", material_id=material_id))

        # 增加资料下载计数
        material.increment_download_count()

        # 确定下载文件名
        if hasattr(material, "original_filename") and material.original_filename:
            download_filename = material.original_filename
        else:
            file_extension = os.path.splitext(file_path)[1] if "." in file_path else ""
            download_filename = f"{material.title}{file_extension}"
        
        # 确定文件的MIME类型
        import mimetypes
        mime_type = mimetypes.guess_type(full_path)[0] or "application/octet-stream"
        
        # 使用Flask内置的send_file函数，使用兼容性写法
        from flask import send_file
        
        # 尝试使用Flask 2.x风格的参数
        try:
            return send_file(
                full_path,
                as_attachment=True,
                download_name=download_filename,
                mimetype=mime_type,
            )
        except TypeError:
            # 如果出错，尝试使用Flask 1.x风格的参数
            return send_file(
                full_path,
                as_attachment=True,
                attachment_filename=download_filename,
                mimetype=mime_type,
            )

    except Exception as e:
        import traceback
        print(f"下载文件出错: {str(e)}")
        print(traceback.format_exc())  # 打印完整错误堆栈
        flash(f"下载文件失败，请联系管理员", "error")
        return redirect(url_for("material.material_view", material_id=material_id))


# 删除资料路由
@material_bp.route("/material/<int:material_id>/delete", methods=["POST"])
@login_required
def delete_material(material_id):
    materials = database.get_material(method="id", key=material_id)
    if not materials:
        return jsonify({"success": False, "message": "资料不存在"})

    # 获取第一个资料对象
    material = materials[0]

    # 检查是否是资料的上传者或管理员
    if material.user_id != current_user.id and not current_user.is_admin:
        return jsonify({"success": False, "message": "没有权限删除此资料"})

    try:
        # 获取文件路径
        file_path = os.path.join(
            current_app.config["UPLOAD_FOLDER"], material.file_path
        )

        # 检查是否有其他材料也在使用这个文件
        other_materials_using_file = len(
            database.get_material(method="file_path", key=file_path)
        )

        # 只有当没有其他材料使用这个文件时，才物理删除文件
        if (
            os.path.exists(file_path) and other_materials_using_file <= 1
        ):  # 修改条件为<=1，因为当前资料也在使用这个文件
            try:
                os.remove(file_path)
                print(f"已删除文件: {file_path}")
                flash("已删除文件")

                # 如果用户的上传目录为空，也删除该目录
                user_dir = os.path.dirname(file_path)
                if (os.path.exists(user_dir) and not os.listdir(user_dir)):
                    os.rmdir(user_dir)
                    print(f"已删除空目录: {user_dir}")
            except Exception as e:
                print(f"删除文件时出错: {str(e)}")
                flash("删除文件时出错")
        else:
            print(
                f"文件 {file_path} 被其他 {other_materials_using_file-1} 个资料使用，不进行物理删除"
            )

        # 使用database模块删除资料
        database.delete_material(material_id)
        return jsonify({"success": True})
    except Exception as e:
        print(f"删除资料时出错: {str(e)}")
        return jsonify({"success": False, "message": "删除失败，请稍后重试"})


# 添加评论删除路由
@material_bp.route("/comment/<int:comment_id>/delete", methods=["POST"])
@login_required
def delete_comment(comment_id):
    """删除评论处理函数"""
    print(f"收到删除评论请求: comment_id={comment_id}, user_id={current_user.id}")
    
    try:
        # 获取评论
        comments = database.get_comment(method="id", key=comment_id)
        if not comments or len(comments) == 0:
            print(f"评论不存在: {comment_id}")
            response = jsonify({'success': False, 'message': '评论不存在'})
            response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            return response

        # 获取第一个评论对象
        comment = comments[0]
        print(f"找到评论: {comment.id}, 作者ID: {comment.user_id}, 资料ID: {comment.material_id}")

        # 检查权限 - 只有评论作者和管理员可以删除
        if comment.user_id != current_user.id and not current_user.is_admin:
            print(f"权限检查失败: 当前用户ID={current_user.id}, 评论作者ID={comment.user_id}")
            response = jsonify({'success': False, 'message': '您没有权限删除此评论'})
            response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            return response

        # 保存评论所属的资料ID，稍后重定向用
        material_id = comment.material_id
        
        # 使用database模块删除评论
        print(f"开始删除评论: id={comment_id}")
        result = database.delete_comment(comment_id)
        print(f"删除评论结果: {result}")
        
        if result:
            print(f"成功删除评论: {comment_id}")
            response = jsonify({'success': True, 'message': '评论已成功删除', 'comment_id': comment_id})
            response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            return response
        else:
            print(f"数据库删除失败: {comment_id}")
            response = jsonify({'success': False, 'message': '数据库删除操作未成功'})
            response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            return response
            
    except Exception as e:
        import traceback
        print(f"删除评论出错: {str(e)}")
        print(traceback.format_exc())
        response = jsonify({'success': False, 'message': f'删除评论失败: {str(e)}'})
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        return response


# 编辑资料路由
@material_bp.route("/material/<int:material_id>/edit", methods=["GET", "POST"])
@login_required
def edit_material(material_id):
    materials = database.get_material(method="id", key=material_id)
    if not materials:
        flash("资料不存在")
        return redirect(url_for("browse.index"))

    # 确保我们有一个单一的 Material 对象而不是列表
    material = materials[0] if isinstance(materials, list) else materials

    # 检查是否是资料的上传者或管理员
    if material.user_id != current_user.id and not current_user.is_admin:
        flash("您没有权限编辑此资料")
        return redirect(url_for("material.material_view", material_id=material_id))

    form = EditMaterialForm()
    form.department.choices = [(d.id, d.name) for d in Department.query.all()] 

    if request.method == "GET":
        # 预填表单
        form.title.data = material.title
        form.description.data = material.description
        form.department.data = material.course.department_id
        form.course.data = material.course.name
        form.course_type.data = material.course.type
        form.material_type.data = material.file_type
        form.semester.data = material.semester

    if form.validate_on_submit():
        # 更新资料信息
        update_data = {
            "title": form.title.data,
            "description": form.description.data,
            "file_type": form.material_type.data,
            "semester": form.semester.data
        }

        # 处理课程信息
        department_id = form.department.data
        course_name = form.course.data.strip()  # 保留了strip()以移除前后空白字符
        course_type = form.course_type.data

        # 检查课程是否存在
        course = Course.query.filter_by(name=course_name, department_id=department_id).first()
        if not course:
            # 如果课程不存在，创建新课程
            try:
                # 生成唯一的课程代码
                import uuid
                course_code = f"AUTO-{uuid.uuid4().hex[:12]}"
                
                course = database.create_course(
                    name=course_name,
                    code=course_code,
                    credits=0,  # 默认学分
                    type=course_type,
                    department_id=department_id,
                    hours=0  # 默认课时
                )
                
                if course is None:
                    flash("创建课程失败，请稍后再试")
                    return render_template("edit_material.html", form=form, material=material)
                    
            except Exception as e:
                flash(f"创建课程时出错: {str(e)}")
                return render_template("edit_material.html", form=form, material=material)
        
        # 更新资料的课程ID
        update_data["course_id"] = course.id

        # 处理文件上传
        f = form.file.data
        if f and f.filename:
            # 安全地处理文件名
            secure_name = secure_filename_cn(f.filename)
            original_filename = f.filename
            
            # 确保上传目录存在
            user_upload_path = os.path.join(
                current_app.config["UPLOAD_FOLDER"], str(current_user.id)
            )
            os.makedirs(user_upload_path, exist_ok=True)
            
            # 保存新文件
            file_path = os.path.join(str(current_user.id), secure_name)
            full_path = os.path.join(current_app.config["UPLOAD_FOLDER"], file_path)
            
            # 如果文件已存在，添加时间戳使其唯一
            if os.path.exists(full_path):
                timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
                name, ext = os.path.splitext(secure_name)
                secure_name = f"{name}_{timestamp}{ext}"
                file_path = os.path.join(str(current_user.id), secure_name)
                full_path = os.path.join(current_app.config["UPLOAD_FOLDER"], file_path)
            
            # 保存新文件
            f.save(full_path)
            
            # 如果旧文件存在且不是正在上传的文件，则删除旧文件
            if material.file_path and material.file_path != file_path:
                old_file_path = os.path.join(
                    current_app.config["UPLOAD_FOLDER"], material.file_path
                )
                if os.path.exists(old_file_path):
                    try:
                        os.remove(old_file_path)
                    except Exception as e:
                        print(f"删除旧文件失败: {e}")
            
            # 更新文件信息
            update_data.update({
                "file_path": file_path,
                "original_filename": original_filename,
                "file_extension": os.path.splitext(original_filename)[1],
            })

        try:
            # 使用database模块更新资料
            updated = database.update_material(material_id, **update_data)
            if updated:
                flash("资料更新成功!")
                return redirect(url_for("material.material_view", material_id=material_id))
            else:
                flash("资料更新失败，请稍后再试")
        except Exception as e:
            flash(f"更新过程中发生错误: {str(e)}")
            return redirect(url_for("material.edit_material", material_id=material_id))

    return render_template(
        "edit_material.html", form=form, material=material
    )


@material_bp.route("/material/<int:material_id>/like", methods=["POST"])
@login_required
def toggle_like(material_id):
    materials = database.get_material(method="id", key=material_id)
    if not materials:
        return jsonify({"success": False, "message": "资料不存在"}), 404

    material = materials[0] if isinstance(materials, list) else materials
    success, is_liked = material.toggle_like(current_user.id)

    if success:
        # 获取更新后的点赞数
        like_count = material.stats.like_count
        return jsonify(
            {"success": True, "is_liked": is_liked, "like_count": like_count}
        )
    else:
        return jsonify({"success": False, "message": "操作失败，请稍后再试"}), 500


# 通知关注者有新资料上传
def notify_followers(user_id, material):
    """通知所有关注该用户的人有新资料上传"""
    # 查找所有关注该用户的用户ID
    followers = get_followers(user_id)
    
    # 修改这里：直接从User对象获取id属性，而不是尝试像元组那样索引
    follower_ids = [follower.id for follower in followers]
    
    if not follower_ids:
        return

    # 读取现有通知
    try:
        with open("notifications.json", "r", encoding="utf-8") as f:
            notifications = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        notifications = []

    # 创建通知
    notification = {
        "id": str(datetime.now().timestamp()),
        "title": "关注的用户上传了新资料",
        "content": f"您关注的用户 {material.uploader.username} 上传了新资料《{material.title}》，点击查看详情。\n\n资料类型：{material.file_type}\n课程：{material.course.name}\n上传时间：{material.created_at.strftime('%Y-%m-%d %H:%M')}",
        "target_role": "followers",  # 特殊标记，表示这是针对特定用户的关注通知
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "created_by": user_id,
        "material_id": material.id,  # 添加资料ID便于跳转
        "for_users": follower_ids,  # 记录需要接收通知的用户ID
        "read_by": [],
    }

    notifications.append(notification)

    # 保存通知
    with open("notifications.json", "w", encoding="utf-8") as f:
        json.dump(notifications, f, ensure_ascii=False, indent=2)


@material_bp.route("/material/<int:material_id>/comments")
def get_material_comments(material_id):
    # 获取该资料的所有评论
    comments = database.get_comment(method="material_id", key=material_id)
    
    # 确保获取到的是最新数据（避免缓存影响）
    db.session.commit()
    
    # 获取排序参数（默认为newest_first，即最新评论在前）
    sort_order = request.args.get('sort', 'newest_first')
    
    # 根据排序参数排序评论
    if sort_order == 'oldest_first':
        comments = sorted(comments, key=lambda x: x.created_at)  # 时间顺序：旧->新
    else:  # 默认为newest_first
        comments = sorted(comments, key=lambda x: x.created_at, reverse=True)  # 时间倒序：新->旧
    
    # 准备JSON响应 - 返回原始评论内容，由前端渲染
    comments_data = []
    for comment in comments:
        # 获取头像URL
        avatar_url = comment.author.avatar
        if not avatar_url.startswith(('http://', 'https://')):
            avatar_url = comment.author.avatar
            
        comment_data = {
            'id': comment.id,
            'content': comment.content,  # 返回原始内容，由前端处理Markdown和LaTeX渲染
            'created_at': comment.created_at.strftime('%Y-%m-%d %H:%M'),
            'user': {
                'id': comment.user_id,
                'username': comment.author.username,
                'avatar': avatar_url
            },
            'can_delete': current_user.is_authenticated and (current_user.id == comment.user_id or current_user.is_admin)
        }
        comments_data.append(comment_data)
    
    # 设置不缓存响应
    response = jsonify({
        'success': True,
        'count': len(comments),
        'comments': comments_data,
        'sort_order': sort_order  # 返回当前使用的排序
    })
    
    # 添加防缓存头
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    
    return response


@material_bp.route("/material/<int:material_id>/check_new_comments")
def check_new_comments(material_id):
    """检查是否有新的评论，返回最新评论的时间戳"""
    # 仅获取最新评论的ID和时间
    last_comment = (
        Comment.query.filter_by(material_id=material_id)
        .order_by(Comment.created_at.desc())
        .first()
    )
    
    # 返回最新评论ID和时间戳
    if last_comment:
        timestamp = int(last_comment.created_at.timestamp() * 1000)  # 转换为毫秒
        return jsonify({
            'success': True,
            'last_comment_id': last_comment.id,
            'timestamp': timestamp
        })
    else:
        return jsonify({
            'success': True,
            'last_comment_id': 0,
            'timestamp': 0
        })
