from flask import Blueprint, render_template

# 创建蓝图
about_bp = Blueprint("about", __name__)


@about_bp.route("/about")
def about():
    """平台介绍页面"""
    return render_template("about.html")
