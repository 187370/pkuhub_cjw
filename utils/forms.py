from flask_wtf import FlaskForm  # Flask表单基类
from flask_wtf.file import (
    FileField,
    FileRequired,
    FileAllowed,
)  # 文件上传相关字段和验证器
from wtforms import (  # 各种表单字段类型
    StringField,
    PasswordField,
    SubmitField,
    BooleanField,
    TextAreaField,
    SelectField,
)
from wtforms.validators import (
    DataRequired,
    Email,
    EqualTo,
    Length,
    ValidationError,
)  # 验证器


class LoginForm(FlaskForm):
    email = StringField(
        "邮箱", validators=[DataRequired(), Email()]
    )  # 必须填写且符合邮箱格式
    password = PasswordField("密码", validators=[DataRequired()])  # 必须填写
    remember = BooleanField("记住我")  # 记住登录状态的复选框
    submit = SubmitField("登录")  # 提交按钮


class RegisterForm(FlaskForm):
    username = StringField(
        "用户名", validators=[DataRequired(), Length(min=2, max=20)]
    )  # 2-20字符
    email = StringField(
        "邮箱", validators=[DataRequired(), Email()]
    )  # 必须符合邮箱格式
    verification_code = StringField(
        "验证码", validators=[DataRequired(), Length(min=6, max=6)]
    )  # 6位验证码
    password = PasswordField(
        "密码", validators=[DataRequired(), Length(min=6)]
    )  # 至少6位
    confirm_password = PasswordField(
        "确认密码", validators=[DataRequired(), EqualTo("password")]
    )  # 需与密码一致
    submit = SubmitField("注册")  # 提交按钮


class RequestVerificationCodeForm(FlaskForm):
    email = StringField("邮箱", validators=[DataRequired(), Email()])  # 邮箱验证
    submit = SubmitField("发送验证码")  # 触发验证码发送


class UpdateProfileForm(FlaskForm):
    username = StringField("用户名", validators=[DataRequired(), Length(min=2, max=20)])
    bio = TextAreaField("个人简介", validators=[Length(max=500)])  # 最多500字
    avatar = FileField(
        "头像图片",
        validators=[  # 图片文件上传
            FileAllowed(
                ["jpg", "png", "jpeg", "gif"], "仅支持JPG、PNG、JPEG和GIF格式图片"
            )  # 限制文件类型
        ],
    )
    submit = SubmitField("更新资料")  # 提交按钮


class ChangePasswordForm(FlaskForm):
    current_password = PasswordField(
        "当前密码", validators=[DataRequired()]
    )  # 需验证原密码
    new_password = PasswordField(
        "新密码", validators=[DataRequired(), Length(min=6)]
    )  # 至少6位
    confirm_password = PasswordField(
        "确认新密码", validators=[DataRequired(), EqualTo("new_password")]
    )  # 两次输入一致
    submit = SubmitField("更改密码")  # 提交按钮


class UploadForm(FlaskForm):
    title = StringField(
        "资料标题", validators=[DataRequired(), Length(max=200)]
    )  # 必填且最长200字
    description = TextAreaField("资料描述")  # 可选描述
    file = FileField(  # 文件上传验证
        "选择文件",
        validators=[
            FileRequired(),  # 必须上传文件
            FileAllowed(
                [
                    "pdf",
                    "docx",
                    "doc",
                    "ppt",
                    "pptx",
                    "xls",
                    "xlsx",
                    "txt",
                    "zip",
                    "rar",
                    "md",
                    "ipynb",
                    "py",
                ],
                "仅支持文档和压缩文件",  # 允许的扩展名列表
            ),
        ],
    )
    department = SelectField(
        "所属学院", coerce=int, validators=[DataRequired()]
    )  # 下拉菜单（需转换值为int）
    course = StringField(
            "课程名称", 
            validators=[DataRequired(), Length(max=100)],
            render_kw={"list": "course-list", "autocomplete": "off"}
        )  # 必填课程名，支持自动补全
    course_type = SelectField(  # 新增课程类型字段
        "课程类型",
        choices=[
            ("", "选择课程类型"),
            ("专业必修", "专业必修"),
            ("专业选修", "专业选修"),
            ("专业任选", "专业任选"),
            ("通选课", "通选课"),
            ("公共课", "公共课"),
            ("其他", "其他"),
        ],
        validators=[DataRequired()],
    )  # 课程类型选择
    material_type = SelectField(  # 类型下拉菜单
        "资料类型",
        choices=[
            ("试卷", "试卷"),
            ("笔记", "笔记"),
            ("课件", "课件"),
            ("习题", "习题"),
            ("答案", "答案"),
            ("汇编", "汇编"),
            ("其他", "其他"),
        ],
        validators=[DataRequired()],
    )
    # 添加semester字段 - 学期选择
    semester = SelectField(
        "学期",
        choices=[
            ("", "选择学期"),
            ("2024春季", "2024春季"),
            ("2023秋季", "2023秋季"),
            ("2023春季", "2023春季"),
            ("2022秋季", "2022秋季"),
            ("2022春季", "2022春季"),
            ("2021秋季", "2021秋季"),
            ("2021春季", "2021春季"),
            ("其他", "其他"),
        ],
        validators=[DataRequired()],
    )  # 添加学期字段
    submit = SubmitField("上传资料")  # 提交按钮


class EditMaterialForm(FlaskForm):
    """编辑资料表单 - 文件是可选的"""

    # 字段与上传表单类似，但文件字段变为可选
    title = StringField("资料标题", validators=[DataRequired(), Length(max=200)])
    description = TextAreaField("资料描述")
    file = FileField(
        "更新文件 (可选)",
        validators=[
            FileAllowed(
                [
                    "pdf",
                    "docx",
                    "doc",
                    "ppt",
                    "pptx",
                    "xls",
                    "xlsx",
                    "txt",
                    "zip",
                    "rar",
                ],
                "仅支持文档和压缩文件",
            )
        ],
    )
    department = SelectField("所属学院", coerce=int, validators=[DataRequired()])
    course = StringField("课程名称", validators=[DataRequired(), Length(max=100)])
    course_type = SelectField(
        "课程类型",
        choices=[
            ("专业必修", "专业必修"),
            ("专业限选", "专业限选"),
            ("专业任选", "专业任选"),
            ("通选课", "通选课"),
            ("全校公选课", "全校公选课"),
            ("大学英语", "大学英语"),
            ("体育", "体育"),
            ("思想政治", "思想政治"),
            ("其他", "其他"),
        ],
        validators=[DataRequired()],
    )
    material_type = SelectField(
        "资料类型",
        choices=[
            ("试卷", "试卷"),
            ("笔记", "笔记"),
            ("课件", "课件"),
            ("习题", "习题"),
            ("答案", "答案"),
            ("汇编", "汇编"),
            ("其他", "其他"),
        ],
        validators=[DataRequired()],
    )
    semester = SelectField(
        "学期",
        choices=[
            ("2024春季", "2024春季"),
            ("2023秋季", "2023秋季"),
            ("2023春季", "2023春季"),
            ("2022秋季", "2022秋季"),
            ("2022春季", "2022春季"),
            ("2021秋季", "2021秋季"),
            ("2021春季", "2021春季"),
            ("2020秋季", "2020秋季"),
            ("2020春季", "2020春季"),
            ("其他", "其他"),
        ],
        validators=[DataRequired()],
    )
    submit = SubmitField("更新资料")


class CommentForm(FlaskForm):
    """评论表单"""
    content = TextAreaField(
        "评论内容",
        validators=[
            DataRequired(message="评论内容不能为空"),
            Length(min=1, max=1000, message="评论长度不能超过1000字符")
        ],
    )
    submit = SubmitField("提交评论")


class AdminEditUserForm(FlaskForm):
    """管理员编辑用户资料表单"""

    username = StringField("用户名", validators=[DataRequired(), Length(min=2, max=20)])
    email = StringField("邮箱", validators=[DataRequired(), Email()])
    bio = TextAreaField("个人简介", validators=[Length(max=500)])  # 最多500字
    is_admin = BooleanField("管理员权限")
    submit = SubmitField("更新资料")  # 提交按钮


class RequestResetPasswordForm(FlaskForm):
    """请求重置密码的表单"""

    email = StringField("邮箱", validators=[DataRequired(), Email()])
    submit = SubmitField("获取验证码")


class ResetPasswordForm(FlaskForm):
    """重置密码的表单"""

    email = StringField("邮箱", validators=[DataRequired(), Email()])
    verification_code = StringField(
        "验证码", validators=[DataRequired(), Length(min=6, max=6)]
    )
    new_password = PasswordField("新密码", validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField(
        "确认密码",
        validators=[
            DataRequired(),
            EqualTo("new_password", message="两次密码必须一致"),
        ],
    )
    submit = SubmitField("重置密码")
