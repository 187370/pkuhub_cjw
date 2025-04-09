from flask import Blueprint, render_template

# 创建蓝图
errors_bp = Blueprint("errors", __name__)


# 404 错误处理
@errors_bp.app_errorhandler(404)
def page_not_found(e):
    return render_template("notfound.html", search_type="page"), 404


# 403 错误处理
@errors_bp.app_errorhandler(403)
def forbidden(e):
    return (
        render_template(
            "error.html", error_code=403, error_message="您没有权限访问此页面"
        ),
        403,
    )


# 500 错误处理
@errors_bp.app_errorhandler(500)
def internal_server_error(e):
    return (
        render_template(
            "error.html", error_code=500, error_message="服务器内部错误，请稍后重试"
        ),
        500,
    )


# 400 错误处理
@errors_bp.app_errorhandler(400)
def bad_request(e):
    return (
        render_template("error.html", error_code=400, error_message="错误的请求"),
        400,
    )
