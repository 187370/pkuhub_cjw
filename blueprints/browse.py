from calendar import c
from flask import Blueprint, render_template, flash, redirect, url_for, jsonify, request
from flask_login import login_required  # 添加导入
from blueprints import material
from database import Course, Material, Department, get_material, get_course
import database

# 创建蓝图
browse_bp = Blueprint("browse", __name__)


# 首页路由
@browse_bp.route("/")
def index():
    materials = database.get_material(method="all")

    # 获取最近更新的材料（防止没有资料时的错误）
    recent_materials = (
        sorted(materials, key=lambda x: x.created_at, reverse=True)[:6]  # 将4改为6
        if materials
        else []
    )

    # 获取热门资料
    popular_materials = (
        sorted(materials, key=lambda x: x.stats.download_count, reverse=True)[:6]  # 将4改为6
        if materials
        else []
    )

    # 获取所有学院
    departments = Department.query.all()

    # 获取统计数据
    material_count = len(materials)
    user_count = len(database.get_user(method="all")) or 0
    download_count = sum(material.stats.download_count for material in materials)

    return render_template(
        "index.html",
        recent_materials=recent_materials,
        popular_materials=popular_materials,
        departments=departments,
        material_count=material_count,
        user_count=user_count,
        download_count=download_count,
    )


# 学院资料浏览路由
@browse_bp.route("/department/<int:department_id>")
def department_view(department_id):
    # 确保找到指定学院
    department = Department.query.get_or_404(department_id)
    
    # 获取搜索查询参数
    query = request.args.get('query', '')
    
    # 如果有搜索查询，使用高级查询函数
    if query:
        courses, _ = database.query_courses(
            department_id=department_id,
            keyword=query,
            per_page=100  # 设置较大的数量，确保所有结果显示
        )
    else:
        # 否则使用原来的方式获取所有课程
        courses = database.get_course(method="department_id", key=department_id)

    # 打印调试信息
    print(f"学院ID: {department_id}, 学院名称: {department.name}")
    print(f"搜索关键词: {query if query else '无'}")
    print(f"找到课程数量: {len(courses)}")
    for course in courses:
        materials_count = len(database.get_material(method="course_id", key=course.id))
        print(
            f"  - 课程ID: {course.id}, 名称: {course.name}, 材料数量: {materials_count}"
        )

    return render_template("department.html", department=department, courses=courses, query=query)


# 课程资料浏览路由
@browse_bp.route("/course/<int:course_id>")
@login_required  # 添加登录验证装饰器
def course_view(course_id):
    courses = get_course(key=course_id, method="id")
    if not courses:
        flash("课程不存在或已被删除", "error")
        return redirect(url_for("browse.index"))

    # 如果返回的是列表，则取第一个元素
    course = courses[0] if isinstance(courses, list) else courses
    
    # 获取过滤参数
    file_type = request.args.get('file_type', '全部')
    semester = request.args.get('semester', '全部学期')
    sort_by = request.args.get('sort_by', '最新上传')
    
    # 先获取所有材料
    materials = get_material(key=course_id, method="course_id") or []
    
    # 应用类型过滤
    if file_type != '全部':
        materials = [m for m in materials if m.file_type == file_type]
    
    # 应用学期过滤
    if semester != '全部学期':
        materials = [m for m in materials if m.semester == semester]
    
    # 应用排序
    if sort_by == '最新上传':
        materials = sorted(materials, key=lambda m: m.created_at, reverse=True)
    elif sort_by == '最多下载':
        materials = sorted(materials, key=lambda m: m.stats.download_count if hasattr(m, 'stats') and m.stats else 0, reverse=True)
    elif sort_by == '最多评论':
        # 修复这里的语法错误
        materials = sorted(materials, key=lambda m: m.comments.count(), reverse=True)
    
    # 获取所有可能的资料类型和学期选项
    file_types = ['全部'] + sorted(list(set(m.file_type for m in materials))) if materials else ['全部']
    semesters = ['全部学期'] + sorted(list(set(m.semester for m in materials if m.semester))) if materials else ['全部学期']
    
    return render_template(
        "course.html",
        course=course,
        materials=materials,
        file_types=file_types,
        semesters=semesters,
        current_file_type=file_type,
        current_semester=semester,
        current_sort=sort_by
    )


# API路由 - 获取课程列表（用于AJAX）
@browse_bp.route("/api/courses/<int:department_id>")
def get_courses(department_id):
    courses = database.get_course(method="department_id", key=department_id)
    return jsonify([{"id": course.id, "name": course.name} for course in courses])


# API路由 - 获取课程详情
@browse_bp.route("/api/course_detail/<int:course_id>")
def get_course_detail(course_id):
    # 使用 get_or_404 直接获取单个课程对象，而不是返回列表
    course = Course.query.get_or_404(course_id)
    
    return jsonify({
        'id': course.id,
        'name': course.name,
        'code': course.code,
        'type': course.type,  # 确保返回课程类型
        'credits': course.credits
    })


# API路由 - 获取所有课程类型
@browse_bp.route("/api/course_types")
def get_all_course_types():
    """获取所有课程类型列表，用于新课程类型选择"""
    course_types = database.get_course_types()
    return jsonify(course_types)
