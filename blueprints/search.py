from flask import Blueprint, render_template, request, current_app
import database
from flask_login import login_required, current_user
from database.models import Department, Material,Course
from datetime import datetime, timedelta
from sqlalchemy import or_, desc, func
from sqlalchemy.sql.expression import case
from database.models import Department, Material, MaterialStats, Comment

# 创建蓝图
search_bp = Blueprint("search", __name__)


# 搜索路由
@search_bp.route("/search")
@login_required
def search():
    # 获取查询参数
    query = request.args.get("q", "")
    file_type = request.args.get("type", "")
    time_filter = request.args.get("time", "")
    sort_by = request.args.get("sort", "relevance")
    course_type = request.args.get("course_type", "")  # 新增课程类型筛选参数

    if not query and not file_type and not time_filter:
        # 如果没有任何查询参数，显示空结果页面
        return render_template("search.html", materials=[], query="")

    try:
        # 使用SQLAlchemy查询获取基本材料列表
        materials = []

        # 构建基础查询
        stmt = database.db.session.query(Material)

        # 添加关键字过滤
        if query:
            # 在多个字段中搜索关键字
            stmt = stmt.filter(
                or_(
                    Material.title.ilike(f"%{query}%"),
                    Material.description.ilike(f"%{query}%"),
                    Material.course.has(database.Course.name.ilike(f"%{query}%")),
                    Material.course.has(
                        database.Course.department.has(
                            database.Department.name.ilike(f"%{query}%")
                        )
                    ),
                )
            )

        # 添加资料类型过滤
        if file_type:
            stmt = stmt.filter(Material.file_type == file_type)

        # 添加时间过滤
        if time_filter:
            now = datetime.now()
            if time_filter == "week":
                stmt = stmt.filter(Material.created_at >= now - timedelta(days=7))
            elif time_filter == "month":
                stmt = stmt.filter(Material.created_at >= now - timedelta(days=30))
            elif time_filter == "year":
                stmt = stmt.filter(Material.created_at >= now - timedelta(days=365))

        # 添加课程类型筛选
        if course_type:
            stmt = stmt.filter(Material.course.has(Course.type == course_type))

        # 添加排序
        if sort_by == "newest":
            stmt = stmt.order_by(desc(Material.created_at))
        elif sort_by == "downloads":
            stmt = stmt.join(Material.stats).order_by(
                desc(MaterialStats.download_count)  # 修改这里，删除 database. 前缀
            )
        elif sort_by == "comments":
            # 按评论数量排序
            stmt = (
                stmt.outerjoin(Material.comments)
                .group_by(Material.id)
                .order_by(desc(func.count(Comment.id)))
            )
        elif sort_by == "relevance" and query:
            # 相关性排序 - 根据标题匹配程度优先
            relevance = case(
                (Material.title.ilike(f"{query}%"), 100),
                (Material.title.ilike(f"%{query}%"), 50),
                else_=10,
            )
            stmt = stmt.order_by(desc(relevance), desc(Material.created_at))
        else:
            # 默认按创建时间降序
            stmt = stmt.order_by(desc(Material.created_at))

        # 执行查询
        materials = stmt.all()

        # 准备类型选项用于筛选框
        file_types = [
            ("试卷", "试卷"),
            ("笔记", "笔记"),
            ("课件", "课件"),
            ("习题", "习题"),
            ("答案", "答案"),
            ("汇编", "汇编"),
            ("其他", "其他"),
        ]

        # 如果没有找到结果，返回notfound页面
        if not materials:
            # 准备筛选信息以便在notfound页面上显示
            filter_info = []
            if query:
                filter_info.append(("搜索关键词", query))
            if file_type:
                filter_info.append(("资料类型", file_type))
            if time_filter:
                time_labels = {"week": "一周内", "month": "一个月内", "year": "一年内"}
                filter_info.append(
                    ("时间范围", time_labels.get(time_filter, time_filter))
                )
            if sort_by:
                sort_labels = {
                    "newest": "最新发布",
                    "downloads": "下载次数",
                    "comments": "评论数量",
                    "relevance": "相关性",
                }
                filter_info.append(("排序方式", sort_labels.get(sort_by, sort_by)))

            return render_template(
                "notfound.html",
                search_type="search",
                query=query,
                filter_info=filter_info,
            )

        # 获取所有课程类型列表
        course_types = database.get_course_types()

        return render_template(
            "search.html",
            materials=materials,
            query=query,
            current_type=file_type,
            file_types=file_types,
            current_time=time_filter,
            current_sort=sort_by,
            current_course_type=course_type,
            course_types=course_types,
        )

    except Exception as e:
        # 如果发生异常，记录错误并返回错误页面
        current_app.logger.error(f"搜索出错: {str(e)}")
        return render_template(
            "error.html", error_code=500, error_message=f"搜索处理出错: {str(e)}"
        )
