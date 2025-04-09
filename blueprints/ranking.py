from flask import Blueprint, render_template, request
from database.models import User, Material, MaterialStats, UserLike, Relationship
from database import get_followers, get_following
from sqlalchemy import func, desc
from database import db
from flask_login import login_required, current_user, logout_user

# 创建蓝图，确保命名和url_prefix正确
ranking_bp = Blueprint("ranking", __name__, url_prefix="/ranking")

# 修改路由路径为根路径"/"，这样完整的URL就是/ranking/
@ranking_bp.route("/")
@login_required
def show_ranking():
    # 获取排序参数（默认为下载数量）
    sort_by = request.args.get("sort_by", "downloads")
    
    # 限制只显示前10名用户，不再需要分页
    per_page = 10
    
    # 根据不同的排序参数查询用户
    if sort_by == "uploads":
        # 按上传数量排序
        users_query = db.session.query(
            User,
            func.count(Material.id).label('count')
        ).outerjoin(
            Material, User.id == Material.user_id
        ).group_by(
            User.id
        ).order_by(
            desc('count')
        ).limit(per_page)
    
    elif sort_by == "followers":
        # 按粉丝数量排序 - 使用新的Relationship模型
        users_query = db.session.query(
            User,
            func.count(Relationship.follower_id).label('count')
        ).outerjoin(
            Relationship, User.id == Relationship.followed_id
        ).group_by(
            User.id
        ).order_by(
            desc('count')
        ).limit(per_page)
    
    elif sort_by == "likes":
        # 按收藏数量排序 (用户上传的资料被收藏的总次数)
        users_query = db.session.query(
            User,
            func.sum(MaterialStats.like_count).label('count')
        ).outerjoin(
            Material, User.id == Material.user_id
        ).outerjoin(
            MaterialStats, Material.id == MaterialStats.material_id
        ).group_by(
            User.id
        ).order_by(
            desc('count')
        ).limit(per_page)
    
    else:  # 默认按下载数量排序
        users_query = db.session.query(
            User,
            func.sum(MaterialStats.download_count).label('count')
        ).outerjoin(
            Material, User.id == Material.user_id
        ).outerjoin(
            MaterialStats, Material.id == MaterialStats.material_id
        ).group_by(
            User.id
        ).order_by(
            desc('count')
        ).limit(per_page)
    
    # 直接执行查询，不再进行分页
    users = users_query.all()
    
    # 返回排行榜页面，移除分页相关参数
    return render_template(
        "ranking.html",
        users=users,
        sort_by=sort_by
    )