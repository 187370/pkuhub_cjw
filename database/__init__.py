from .base import db
from .models import User, Course, Material, Department, Comment

# 导入数据库操作函数
from .action import (
    # 用户
    create_user,  # 创建用户
    get_user,  # 获取用户
    delete_user,  # 删除用户
    update_user,  # 更新用户
    # 资料
    create_material,  # 创建资料
    get_material,  # 获取资料
    update_material,  # 更新资料
    delete_material,  # 删除资料
    # 课程
    create_course,  # 创建课程
    get_course,  # 获取课程
    update_course,  # 更新课程
    delete_course,  # 删除课程
    # 评论
    create_comment,
    get_comment,
    update_comment,
    delete_comment,
    # 高级查询
    query_courses,  # 课程高级查询
    query_materials,  # 资料高级查询
    get_course_types,  # 获取所有课程类型
    get_material_types,  # 获取所有资料类型
)

# 导入用户关系操作函数
from .action import (
    is_following,  # 是否关注
    follow_user,  # 关注用户
    unfollow_user,  # 取消关注
    get_following,  # 获取关注列表
    get_followers,  # 获取粉丝列表
)


__all__ = [
    "db",  # 数据库对象
    "User",  # 用户模型
    "Course",  # 课程模型
    "Department",  # 学院模型
    "Material",  # 课程资料模型
    "Comment",  # 评论模型
    # 用户通用操作
    "create_user",  # 创建用户
    "get_user",  # 获取用户
    "delete_user",  # 删除用户
    "update_user",  # 更新用户
    # 资料通用操作
    "create_material",  # 创建资料
    "get_material",  # 获取资料
    "delete_material",  # 删除资料
    "update_material",  # 更新资料
    "create_course",  # 创建课程
    "get_course",  # 获取课程
    "delete_course",  # 删除课程
    "update_course",  # 更新课程
    # 评论通用操作
    # 评论通用操作
    "create_comment",  # 添加评论
    "get_comment",  # 查询评论
    "delete_comment",  # 删除评论
    "update_comment",  # 更新评论y
      # 高级查询接口
    "query_courses",  # 课程高级查询
    "query_materials",  # 资料高级查询
    "get_course_types",  # 获取所有课程类型
    "get_material_types",  # 获取所有资料类型
      # 用户关系操作
    "is_following",  # 检查是否关注
    "follow_user",  # 关注用户
    "unfollow_user",  # 取消关注
    "get_following",  # 获取关注列表
    "get_followers",  # 获取粉丝列表
]
