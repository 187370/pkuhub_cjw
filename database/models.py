# 数据库相关定义
# 包括用户、课程、资料、评论等模型定义
# 以及数据库操作辅助函数

# 对于文件的操作，这里只涉及到了对于文件的数据库数据的操作（比方说文件路径），具体的文件的上传和下载操作需要另行定义以保证模块之间的独立性
# 可以考虑在具体的文件上传下载成功之后再对于数据库的操作函数进行调用

from sqlalchemy.sql import func
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
import secrets
import logging
from sqlalchemy import select
from .base import db, login_manager
from sqlalchemy import update, text
import datetime

# 配置日志记录器 - 用于记录数据库操作过程中的错误和警告信息
logger = logging.getLogger(__name__)


# User 加载函数 - Flask-Login 需要的回调函数，用于从会话中恢复用户对象
# 参数:
#   user_id: 存储在 session 中的用户 ID
# 返回:
#   找到的用户对象，如未找到则返回 None
@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# 用户角色表(多对多关系) - 用于实现RBAC(基于角色的访问控制)模型
# 这是一个关联表，不是独立的模型类，用于连接 User 和 Role 多对多关系
roles_users = db.Table(
    "roles_users",
    db.Column("user_id", db.Integer, db.ForeignKey("user.id", ondelete="CASCADE")),
    db.Column("role_id", db.Integer, db.ForeignKey("role.id", ondelete="CASCADE")),
    db.Index("ix_user_role", "user_id", "role_id"),  # 创建复合索引提高查询效率
)


class Role(db.Model):
    """
    用户角色模型 - 定义系统中可用的角色 (如管理员、普通用户等,不同于user模型)
    用于实现基于角色的权限控制系统，如管理员、普通用户等
    """

    __tablename__ = "role"  # 主键
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(
        db.String(80), unique=True, nullable=False
    )  # 角色名称，如"admin"，"user"等
    description = db.Column(db.String(255))  # 角色描述，便于理解角色用途

    def __repr__(self):
        return f"<Role {self.name}>"


class User(UserMixin, db.Model):
    """
    用户模型 - 存储用户账户信息和身份验证数据
    继承 UserMixin 实现 Flask-Login 所需的方法
    """

    __tablename__ = "user"
    # 主键
    id = db.Column(db.Integer, primary_key=True)
    # 用户名，唯一且建立索引提高查询速度
    username = db.Column(db.String(64), unique=True, index=True, nullable=False)
    # 邮箱，唯一且建立索引
    email = db.Column(db.String(120), unique=True, index=True, nullable=False)
    # 密码哈希，不存储明文密码
    password_hash = db.Column(db.String(128), nullable=False)
    # 用户头像文件路径，可为空（采用默认头像）
    avatar = db.Column(db.String(255), default="default_avatar.png")
    # 用户个人简介，可为空
    bio = db.Column(db.Text)
    # 邮箱是否已验证
    is_email_verified = db.Column(db.Boolean, default=False)
    # 是否为管理员
    is_admin = db.Column(db.Boolean, default=False)
    # 账户创建时间，自动维护
    created_at = db.Column(db.DateTime, default=func.now(), nullable=False)
    # 账户更新时间，自动更新
    updated_at = db.Column(db.DateTime, default=func.now(), onupdate=func.now())
    # 最后登录时间，建立索引便于查询活跃用户
    last_login = db.Column(db.DateTime, index=True)
    # 用于乐观锁，防止并发更新冲突
    version = db.Column(db.Integer, default=0)

    # 删除禁言相关字段

    # 关系

    roles = db.relationship(
        "Role",
        secondary=roles_users,
        backref=db.backref(
            "users", lazy="dynamic"
        ),  # 通过 role.users 可访问具有该角色的所有用户
    )

    materials = db.relationship(
        "Material",
        backref="uploader",  # 通过 material.uploader 可访问上传者
        lazy="dynamic",  # 懒加载提高性能
        cascade="all, delete-orphan",  # 用户删除时，自动删除其上传的资料
    )
    comments = db.relationship(
        "Comment",
        backref="author",  # 通过 comment.author 可访问评论作者
        lazy="dynamic",
        cascade="all, delete-orphan",  # 用户删除时，自动删除其所有评论
    )

    def __repr__(self):
        return f"<User {self.username}>"

    def set_password(self, password):
        """
        设置密码哈希 - 使用 Werkzeug 的安全哈希函数
        参数:
            password: 明文密码
        """
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """
        验证密码 - 比较输入的明文密码与存储的哈希值
        参数:
            password: 待验证的明文密码
        返回:
            布尔值，密码正确返回 True，否则返回 False
        """
        return check_password_hash(self.password_hash, password)

    def generate_email_token(self):
        """
        生成邮箱验证令牌 - 用于邮箱验证流程
        返回:
            随机生成的16字节十六进制令牌
        注意:
            实际应用中应存储在Redis或数据库中关联用户
        """
        token = secrets.token_hex(16)
        return token

    @staticmethod
    def verify_email_token(token):
        """
        验证邮箱令牌 - 验证用户提供的令牌是否有效
        参数:
            token: 要验证的令牌
        注意:
            实际应用中应从Redis或数据库中验证并关联用户
        """
        pass

    def to_dict(self):
        """
        转换为字典 - 用于API响应，排除敏感信息
        返回:
            包含用户公开信息的字典
        """
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "avatar": self.avatar,
            "bio": self.bio,
            "created_at": self.created_at,
            "is_admin": self.is_admin,
        }


class Department(db.Model):
    """
    院系部门模型 - 代表学校的各个学院和部门
    用于组织和分类课程
    """

    __tablename__ = "department"
    # 主键
    id = db.Column(db.Integer, primary_key=True)
    # 院系名称，唯一且建立索引提高查询速度
    name = db.Column(db.String(50), unique=True, index=True, nullable=False)
    # 院系描述，可为空
    description = db.Column(db.Text)

    # 关系
    courses = db.relationship(
        "Course",
        backref="department",  # 通过 course.department 访问课程所属院系
        lazy="dynamic",
        cascade="all, delete-orphan",  # 删除院系时级联删除其下所有课程
    )

    def __repr__(self):
        return f"<Department {self.name}>"


class Course(db.Model):
    """
    课程模型 - 存储课程信息
    每个课程隶属于一个院系，并可以有多个相关资料
    """

    __tablename__ = "course"
    # 主键
    id = db.Column(db.Integer, primary_key=True)
    # 课程名称
    name = db.Column(db.String(100), index=True, nullable=False)
    # 课程代码，唯一
    code = db.Column(db.String(20), unique=True, index=True, nullable=False)
    # 学分，存储为整数(如3.0学分存为300)
    credits = db.Column(db.Integer, nullable=False)
    # 课程类型
    type = db.Column(db.String(100), index=True, nullable=False)
    # 课时数
    hours = db.Column(db.Integer, nullable=False)
    # 课程描述，可为空
    description = db.Column(db.Text)
    department_id = db.Column(
        db.Integer,
        db.ForeignKey(
            "department.id", ondelete="CASCADE"
        ),  # 外键关联department表，级联删除
        index=True,  # 建立索引提高关联查询效率
        nullable=False,  # 每门课必须关联到一个院系
    )
    # 创建时间，自动维护
    created_at = db.Column(db.DateTime, default=func.now(), nullable=False)
    # 更新时间，自动维护
    updated_at = db.Column(db.DateTime, default=func.now(), onupdate=func.now())
    # 乐观锁版本号，防止并发更新冲突
    version = db.Column(db.Integer, default=0)

    # 关系
    materials = db.relationship(
        "Material", backref="course", lazy="dynamic", cascade="all, delete-orphan"
    )

    __table_args__ = (
        # 复合索引：按照院系ID和课程名称查询
        db.Index("ix_dept_course_name", "department_id", "name"),
    )

    def __repr__(self):
        return f"<Course {self.code}: {self.name}>"


class Material(db.Model):
    """课程资料模型"""

    __tablename__ = "material"
    # 主键
    id = db.Column(db.Integer, primary_key=True)
    # 资料标题，建立索引便于搜索
    title = db.Column(db.String(200), nullable=False, index=True)
    # 资料描述
    description = db.Column(db.Text)
    # 文件在服务器上的存储路径
    file_path = db.Column(db.String(255), nullable=False)
    # 文件大小，单位可能是字节
    file_size = db.Column(db.Integer, default=0)
    # 资料类型，如"试卷"、"笔记"等
    file_type = db.Column(db.String(50), nullable=False, index=True)

    course_id = db.Column(
        db.Integer,
        db.ForeignKey("course.id", ondelete="CASCADE"),  # 关联到课程，级联删除
        index=True,
        nullable=False,
    )
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id", ondelete="CASCADE"),  # 关联到上传用户，级联删除
        index=True,
        nullable=False,
    )
    # 上传时间
    created_at = db.Column(db.DateTime, default=func.now(), nullable=False)
    # 更新时间，自动更新
    updated_at = db.Column(db.DateTime, default=func.now(), onupdate=func.now())
    # 文件扩展名，如".pdf"，用于前端显示适当图标
    file_extension = db.Column(db.String(20))
    # 学期，如"2023-2024学年第一学期"
    semester = db.Column(db.String(50), index=True)
    # 原始文件名
    original_filename = db.Column(db.String(255))
    # 乐观锁版本号
    version = db.Column(db.Integer, default=0)

    # 关系
    comments = db.relationship(
        "Comment",
        backref="material",
        lazy="dynamic",
        cascade="all, delete-orphan",  # 删除资料时级联删除相关评论
    )
    stats = db.relationship(
        "MaterialStats",
        uselist=False,  # 一对一关系
        backref="material",
        cascade="all, delete-orphan",  # 删除资料时级联删除统计信息
    )
    likes = db.relationship(
        "UserLike", backref="material", lazy="dynamic", cascade="all, delete-orphan"
    )

    # 添加 user 属性别名
    @property
    def user(self):
        return self.uploader

    __table_args__ = (
        # 复合索引：按照课程ID和创建时间查询 - 用于查询某课程的资料并按时间排序
        db.Index("ix_course_created", "course_id", "created_at"),
        # 复合索引：按照类型和创建时间查询 - 用于查询某类型的资料并按时间排序
        db.Index("ix_type_created", "file_type", "created_at"),
    )

    def __repr__(self):
        return f"<Material {self.title}>"

    def increment_download_count(self):
        """
        增加下载计数 - 使用乐观锁和原生SQL实现高并发下的计数更新

        实现说明:
        1. 如果资料还没有统计记录，先创建一个
        2. 使用原生SQL直接更新计数，避免读取-修改-写入的竞争条件
        3. 尝试最多5次，应对高并发下的竞争失败情况

        返回:
            布尔值，更新成功返回True，失败返回False
        """
        if not self.stats:
            self.stats = MaterialStats(material_id=self.id)
            db.session.add(self.stats)

        # 尝试最多5次更新，应对高并发下的更新冲突
        for attempt in range(5):
            try:
                # 使用原生SQL直接更新计数，避免读取后再更新的竞争条件
                # 这是一种乐观锁的应用，直接在数据库层面完成操作
                result = db.session.execute(
                    text(
                        "UPDATE material_stats SET download_count = download_count + 1 "
                        "WHERE material_id = :material_id"
                    ),
                    {"material_id": self.id},
                )
                db.session.commit()
                # 如果影响了行数,说明更新成功
                if result.rowcount > 0:
                    return True
            except Exception as e:
                db.session.rollback()
                # 如果是最后一次尝试失败,则抛出异常
                if attempt == 4:
                    raise e
        return False

    def increment_view_count(self):
        """增加浏览计数"""
        if not self.stats:
            self.stats = MaterialStats(material_id=self.id)
            db.session.add(self.stats)

        # 尝试最多5次更新，应对高并发下的更新冲突
        for attempt in range(5):
            try:
                # 使用原生SQL直接更新计数，避免读取后再更新的竞争条件
                result = db.session.execute(
                    text(
                        "UPDATE material_stats SET view_count = view_count + 1 "
                        "WHERE material_id = :material_id"
                    ),
                    {"material_id": self.id},
                )
                db.session.commit()
                # 如果影响了行数,说明更新成功
                if result.rowcount > 0:
                    return True
            except Exception as e:
                db.session.rollback()
                # 如果是最后一次尝试失败,则抛出异常
                if attempt == 4:
                    raise e
        return False

    def toggle_like(self, user_id):
        """切换点赞状态，返回(操作结果, 当前状态)"""
        # 检查用户是否已点赞
        like = UserLike.query.filter_by(user_id=user_id, material_id=self.id).first()

        try:
            if (like):
                # 如果已点赞，则取消点赞
                db.session.delete(like)
                db.session.execute(
                    text(
                        "UPDATE material_stats SET like_count = like_count - 1 "
                        "WHERE material_id = :material_id"
                    ),
                    {"material_id": self.id},
                )
                db.session.commit()
                return True, False  # 操作成功，当前未点赞
            else:
                # 如果未点赞，则添加点赞
                new_like = UserLike(user_id=user_id, material_id=self.id)
                db.session.add(new_like)
                db.session.execute(
                    text(
                        "UPDATE material_stats SET like_count = like_count + 1 "
                        "WHERE material_id = :material_id"
                    ),
                    {"material_id": self.id},
                )
                db.session.commit()
                return True, True  # 操作成功，当前已点赞
        except Exception as e:
            db.session.rollback()
            return False, None  # 操作失败

    def is_liked_by(self, user_id):
        """检查资料是否被指定用户点赞"""
        if not user_id:
            return False
        return (
            UserLike.query.filter_by(user_id=user_id, material_id=self.id).first()
            is not None
        )


class MaterialStats(db.Model):
    """
    资料统计模型 - 分离高频更新字段，优化性能
    将频繁更新的统计数据分离到独立表中，减少锁竞争和表膨胀
    """

    __tablename__ = "material_stats"
    material_id = db.Column(
        db.Integer,
        db.ForeignKey("material.id", ondelete="CASCADE"),
        primary_key=True,  # 使用外键作为主键
    )
    download_count = db.Column(db.Integer, default=0)  # 下载次数统计
    view_count = db.Column(db.Integer, default=0)  # 查看次数统计
    like_count = db.Column(db.Integer, default=0)  # 点赞次数统计

    def __repr__(self):
        return f"<MaterialStats for Material {self.material_id}>"


class Comment(db.Model):
    """
    评论模型 - 用户对资料的评论和讨论
    支持回复功能，可以构建评论树
    """

    __tablename__ = "comment"
    # 主键
    id = db.Column(db.Integer, primary_key=True)
    # 评论内容
    content = db.Column(db.Text, nullable=False)
    # 评论时间
    created_at = db.Column(db.DateTime, default=func.now(), nullable=False)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id", ondelete="CASCADE"),  # 关联到评论用户，级联删除
        index=True,
        nullable=False,
    )
    material_id = db.Column(
        db.Integer,
        db.ForeignKey("material.id", ondelete="CASCADE"),  # 关联到被评论资料，级联删除
        index=True,
        nullable=False,
    )
    parent_id = db.Column(
        db.Integer,
        db.ForeignKey("comment.id", ondelete="CASCADE"),  # 自引用外键，关联到父评论
        index=True,  # 建立索引便于查找回复
    )

    # 自引用关系,用于回复功能
    replies = db.relationship(
        "Comment",
        backref=db.backref("parent", remote_side=[id]),  # 通过comment.parent访问父评论
        lazy="dynamic",
        cascade="all, delete-orphan",  # 删除评论时级联删除其下所有回复
    )

    __table_args__ = (
        # 复合索引：按照资料ID和创建时间查询(用于按时间排序评论)
        db.Index("ix_material_created", "material_id", "created_at"),
        # 复合索引：按照用户ID和创建时间查询(用于查看用户的所有评论)
        db.Index("ix_user_created", "user_id", "created_at"),
    )

    def __repr__(self):
        return f"<Comment {self.id}>"


class MaterialTag(db.Model):
    """
    资料标签关联表 - 多对多关联表，连接Material和Tag
    允许一个资料有多个标签，一个标签可应用于多个资料
    """

    __tablename__ = "material_tag"
    material_id = db.Column(
        db.Integer,
        db.ForeignKey("material.id", ondelete="CASCADE"),
        primary_key=True,  # 复合主键的一部分
    )
    tag_id = db.Column(
        db.Integer,
        db.ForeignKey("tag.id", ondelete="CASCADE"),
        primary_key=True,  # 复合主键的一部分
    )
    created_at = db.Column(db.DateTime, default=func.now(), nullable=False)  # 创建时间

    __table_args__ = (  # 复合索引: 优化按资料或标签查询的性能
        db.Index("ix_material_tag", "material_id", "tag_id"),
    )


class Tag(db.Model):
    """
    标签模型 - 用于分类和标记资料
    通过多对多关系与资料关联
    """

    __tablename__ = "tag"
    id = db.Column(db.Integer, primary_key=True)  # 主键
    name = db.Column(
        db.String(50), unique=True, index=True, nullable=False
    )  # 标签名称，唯一

    # 多对多关系定义
    materials = db.relationship(
        "Material",
        secondary="material_tag",  # 通过中间表关联
        backref=db.backref(
            "tags", lazy="dynamic"
        ),  # 通过material.tags访问资料的所有标签
        lazy="dynamic",  # 延迟加载提高性能
    )

    def __repr__(self):
        return f"<Tag {self.name}>"


class UserLike(db.Model):
    """用户点赞/收藏模型 - 记录用户对资料的收藏状态"""

    __tablename__ = "user_like"
    user_id = db.Column(
        db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), primary_key=True
    )
    material_id = db.Column(
        db.Integer, db.ForeignKey("material.id", ondelete="CASCADE"), primary_key=True
    )
    created_at = db.Column(db.DateTime, default=func.now(), nullable=False)

    def __repr__(self):
        return f"<UserLike: User {self.user_id} likes Material {self.material_id}>"


class UserDownloadLimit(db.Model):
    """用户下载限制模型，记录用户每天的下载次数"""

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), nullable=False
    )
    date = db.Column(db.Date, nullable=False, default=datetime.date.today)
    download_count = db.Column(db.Integer, default=0)

    # 建立关系
    user = db.relationship(
        "User", backref=db.backref("download_limits", lazy="dynamic")
    )

    # 复合唯一索引，确保每个用户每天只有一条记录
    __table_args__ = (
        db.UniqueConstraint("user_id", "date", name="uix_user_download_date"),
    )

    def __repr__(self):
        return f"<UserDownloadLimit {self.user_id} {self.date} count={self.download_count}>"


class Relationship(db.Model):
    """
    用户关注关系模型 - 存储用户之间的关注关系
    支持查询用户的关注者和被关注者
    """
    
    __tablename__ = 'relationships'
    
    id = db.Column(db.Integer, primary_key=True)
    follower_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete="CASCADE"), nullable=False)
    followed_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete="CASCADE"), nullable=False)
    created_at = db.Column(db.DateTime, default=func.now(), nullable=False)
    
    # 确保同一用户不会重复关注同一个人
    __table_args__ = (
        db.UniqueConstraint('follower_id', 'followed_id', name='uq_user_relationship'),
    )
    
    # 关系定义
    follower = db.relationship(
        'User', 
        foreign_keys=[follower_id], 
        backref=db.backref('following_relationships', lazy='dynamic'),
        primaryjoin="Relationship.follower_id == User.id"
    )
    followed = db.relationship(
        'User', 
        foreign_keys=[followed_id], 
        backref=db.backref('follower_relationships', lazy='dynamic'),
        primaryjoin="Relationship.followed_id == User.id"
    )
    
    def __repr__(self):
        return f"<Relationship {self.follower_id} follows {self.followed_id}>"