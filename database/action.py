from .models import Course, Material, Department, MaterialStats,User,Comment,Relationship, UserDownloadLimit
from .base import db
import logging
from sqlalchemy import select
from sqlalchemy import update

logger = logging.getLogger(__name__)

# ========== 数据库操作辅助函数 ==========
def safe_commit():
    """
    安全提交数据库事务,处理并发冲突
    在高并发环境下,当发生并发冲突时会回滚并返回失败状态
    """
    try:
        db.session.commit()
        return True
    except Exception as e:
        db.session.rollback()
        logger.error(f"数据库提交错误: {str(e)}")
        return False


def update_with_version_check(model, instance_id, new_data, current_version):
    """
    使用版本检查更新数据,用于乐观锁实现 (使用SQLAlchemy 2.0 Update构造)
    """
    # 使用Update构造
    stmt = (
        update(model)
        .where(model.id == instance_id, model.version == current_version)
        .values(**new_data, version=current_version + 1)
        .execution_options(synchronize_session=False)
    )

    # 执行更新
    result = db.session.execute(stmt)

    # 检查是否有行被更新
    if result.rowcount == 0:
        return False  # 冲突,没有行被更新

    return safe_commit()  # 提交事务


def get_records(model, method=None, key=None, islikely=False):
    """
    通用记录查询函数 - 支持条件过滤的数据查询
    方便更新匹配库的api接口
    这是一个抽象的通用查询函数,用于替代多个相似的查询函数,减少代码重复。
    可用于任何SQLAlchemy模型的查询,支持按指定字段进行精确或模糊匹配。

    :param model: SQLAlchemy模型类,如User, Course, Material, Comment
    :param method: 过滤字段名,如'username'或'title',必须是model的属性
    :param key: 过滤关键词
    :param islikely: 是否使用模糊匹配(使用SQL LIKE进行模糊查询)
    :return: 查询结果列表,如无匹配则返回空列表

    用法示例:
        users = get_records(User, 'username', 'admin', False)  # 精确匹配username='admin'
        courses = get_records(Course, 'name', '算法', True)    # 模糊匹配name中包含'算法'
    """
    # 创建基本查询
    stmt = select(model)

    # 添加过滤条件
    if method and key:
        attr = getattr(model, method, None)
        if attr:
            if islikely:
                stmt = stmt.filter(attr.like(f"%{key}%"))
            else:
                stmt = stmt.filter(attr == key)

    # 执行查询并返回结果
    result = db.session.execute(stmt).scalars().all()
    return result


# 为保持API兼容性,保留原有函数作为对通用函数的包装
def get_user(method=None, key=None, islikely=False):
    """
    获取用户列表,支持条件过滤
    :param method: 过滤字段名,如'username'或'email'
    :param key: 过滤关键词
    :param islikely: 是否使用模糊匹配
    :return: 用户列表
    """
    return get_records(User, method, key, islikely)


def get_course(method=None, key=None, islikely=False):
    """
    获取课程列表,支持条件过滤
    :param method: 过滤字段名,如'name'或'code'
    :param key: 过滤关键词
    :param islikely: 是否使用模糊匹配
    :return: 课程列表
    """
    return get_records(Course, method, key, islikely)


def get_material(method=None, key=None, islikely=False):
    """
    获取资料列表,支持条件过滤
    :param method: 过滤字段名,如'title'或'file_type'
    :param key: 过滤关键词
    :param islikely: 是否使用模糊匹配
    :return: 资料列表
    """
    return get_records(Material, method, key, islikely)


def get_comment(method=None, key=None, islikely=False):
    """
    获取评论列表,支持条件过滤
    :param method: 过滤字段名,如'material_id'或'user_id'
    :param key: 过滤关键词
    :param islikely: 是否使用模糊匹配
    :return: 评论列表
    """
    return get_records(Comment, method, key, islikely)


def delete_user(id=None):
    """
    删除指定ID的用户
    :param id: 用户ID
    :return: 删除成功返回True,失败返回False
    """
    if id is None:
        return False
    user = db.session.get(User, id)
    if not user:
        return False
    try:
        # 先删除用户的下载限制记录，解决外键约束问题
        UserDownloadLimit.query.filter_by(user_id=id).delete()
        
        # 删除用户关注关系（作为关注者和被关注者两种情况）
        Relationship.query.filter_by(follower_id=id).delete()
        Relationship.query.filter_by(followed_id=id).delete()
        
        # 删除用户
        db.session.delete(user)
        return safe_commit()  # 使用安全提交函数
    except Exception as e:
        db.session.rollback()
        logger.error(f"删除用户失败: {str(e)}")
        return False


def update_user(id=None, **kwargs):
    """
    更新用户信息,支持乐观锁
    :param id: 用户ID
    :param kwargs: 要更新的字段和值
    :return: 成功返回更新后的用户对象,失败返回None
    """
    if id is None:
        return None

    user = db.session.get(User, id)
    if not user:
        return None

    # 检查是否使用乐观锁
    current_version = kwargs.pop("version", None)
    if current_version is not None:
        # 使用乐观锁更新
        return update_with_version_check(User, id, kwargs, current_version)

    # 普通更新
    for key, value in kwargs.items():
        if hasattr(user, key):
            setattr(user, key, value)

    return user if safe_commit() else None


def create_user(**kwargs):
    """
    创建新用户
    :param kwargs: 用户属性字段和值
    :return: 成功返回新用户对象,失败返回None
    """
    # 处理密码字段,如果提供了明文密码则进行哈希处理
    if "password" in kwargs:
        password = kwargs.pop("password")
        user = User(**kwargs)
        user.set_password(password)
    else:
        user = User(**kwargs)

    try:
        db.session.add(user)
        return user if safe_commit() else None
    except Exception as e:
        db.session.rollback()
        logger.error(f"创建用户失败: {str(e)}")
        return None


def delete_course(id=None):
    """
    删除指定ID的课程
    :param id: 课程ID
    :return: 删除成功返回True,失败返回False
    """
    if id is None:
        return False
    course = db.session.get(Course, id)
    if not course:
        return False
    try:
        db.session.delete(course)
        return safe_commit()
    except Exception as e:
        db.session.rollback()
        logger.error(f"删除课程失败: {str(e)}")
        return False


def update_course(id=None, **kwargs):
    """
    更新课程信息,支持乐观锁
    :param id: 课程ID
    :param kwargs: 要更新的字段和值
    :return: 成功返回更新后的课程对象,失败返回None
    """
    if id is None:
        return None

    course = db.session.get(Course, id)
    if not course:
        return None

    # 检查是否使用乐观锁
    current_version = kwargs.pop("version", None)
    if current_version is not None:
        # 使用乐观锁更新
        return update_with_version_check(Course, id, kwargs, current_version)

    # 普通更新
    for key, value in kwargs.items():
        if hasattr(course, key):
            setattr(course, key, value)

    return course if safe_commit() else None


def create_course(**kwargs):
    """
    创建新课程
    :param kwargs: 课程属性字段和值
    :return: 成功返回新课程对象,失败返回None
    """
    try:
        # 参数验证 - 只保留基本检查
        required_fields = ['name', 'department_id']
        for field in required_fields:
            if field not in kwargs:
                logger.error(f"创建课程失败: 缺少必要字段 {field}")
                return None
        
        # 确保课程类型存在，如果不存在则设置默认值
        if 'type' not in kwargs or not kwargs['type']:
            kwargs['type'] = "其他"  # 提供默认类型
            
        # 创建课程对象
        course = Course(**kwargs)
        db.session.add(course)
        
        # 安全提交并返回结果
        if safe_commit():
            return course
        return None
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"创建课程失败: {str(e)}")
        return None


def delete_material(id=None):
    """
    删除指定ID的资料
    :param id: 资料ID
    :return: 删除成功返回True,失败返回False
    """
    if id is None:
        return False
    material = db.session.get(Material, id)
    if not material:
        return False
    try:
        db.session.delete(material)
        return safe_commit()
    except Exception as e:
        db.session.rollback()
        logger.error(f"删除资料失败: {str(e)}")
        return False


def update_material(material_id, **kwargs):
    """更新资料记录"""
    try:
        material = Material.query.get(material_id)
        if not material:
            logger.error(f"更新资料失败: ID为{material_id}的资料不存在")
            return False

        # 检查是否有课程ID更新，需要确保新课程存在
        if "course_id" in kwargs:
            course = Course.query.get(kwargs["course_id"])
            if not course:
                logger.error(f"更新资料失败: ID为{kwargs['course_id']}的课程不存在")
                return False

        # 更新资料字段
        for key, value in kwargs.items():
            if hasattr(material, key):
                setattr(material, key, value)
            else:
                logger.warning(f"忽略未知字段: {key}")

        # 如果修改了文件路径，增加版本号
        if "file_path" in kwargs:
            material.version += 1
            
        # 确保semester字段有值
        if "semester" in kwargs and not kwargs["semester"]:
            material.semester = "其他"

        db.session.commit()
        logger.info(f"资料更新成功: ID={material_id}")
        return material
    except Exception as e:
        db.session.rollback()
        logger.error(f"更新资料出错: {str(e)}")
        return False


def create_material(**kwargs):
    """
    创建新资料
    :param kwargs: 资料属性字段和值
    :return: 成功返回新资料对象,失败返回None
    """
    material = Material(**kwargs)
    try:
        db.session.add(material)
        db.session.commit()

        # 创建关联的统计信息
        stats = MaterialStats(material_id=material.id)
        db.session.add(stats)

        return material if safe_commit() else None
    except Exception as e:
        db.session.rollback()
        logger.error(f"创建资料失败: {str(e)}")
        return None


def delete_comment(id=None):
    """
    删除指定ID的评论
    :param id: 评论ID
    :return: 删除成功返回True,失败返回False
    """
    print(f"database.delete_comment() 被调用: id={id}")
    if id is None:
        print("评论ID为None，无法删除")
        return False
    
    comment = db.session.get(Comment, id)
    if not comment:
        print(f"评论不存在: id={id}")
        return False
    
    try:
        print(f"开始删除评论: id={id}, 内容={comment.content[:20]}...")
        db.session.delete(comment)
        result = safe_commit()
        print(f"删除评论结果: {result}")
        return result
    except Exception as e:
        db.session.rollback()
        logger.error(f"删除评论失败: {str(e)}")
        print(f"删除评论异常: {str(e)}")
        return False


def update_comment(id=None, **kwargs):
    """
    更新评论信息
    :param id: 评论ID
    :param kwargs: 要更新的字段和值
    :return: 成功返回更新后的评论对象,失败返回None
    """
    if id is None:
        return None

    comment = db.session.get(Comment, id)
    if not comment:
        return None

    for key, value in kwargs.items():
        if hasattr(comment, key):
            setattr(comment, key, value)

    return comment if safe_commit() else None


def create_comment(**kwargs):
    """
    创建新评论
    :param kwargs: 评论属性字段和值
    :return: 成功返回新评论对象,失败返回None
    """
    comment = Comment(**kwargs)
    try:
        db.session.add(comment)
        return comment if safe_commit() else None
    except Exception as e:
        db.session.rollback()
        logger.error(f"创建评论失败: {str(e)}")
        return None


def advanced_query(model, filters=None, order_by=None, page=None, per_page=None, joins=None, include_total=True):
    """
    高级查询接口，支持复杂查询条件、排序、分页和关联查询
    
    :param model: SQLAlchemy模型类，如User, Course, Material
    :param filters: 过滤条件列表，每个元素为(字段名, 操作符, 值)的元组
                   操作符可以是: eq, ne, lt, le, gt, ge, like, in, not_in, between
    :param order_by: 排序条件列表，每个元素为(字段名, 方向)的元组，方向可以是'asc'或'desc'
    :param page: 当前页码（从1开始）
    :param per_page: 每页记录数
    :param joins: 关联查询列表，每个元素为要关联的模型属性名
    :param include_total: 是否返回总记录数（用于分页）
    :return: 查询结果列表和分页信息的元组(items, total)，不分页时total为None
    
    示例:
        # 查询名称包含"算法"，学分大于3的课程，按学分降序排列
        filters = [
            ('name', 'like', '%算法%'),
            ('credits', 'gt', 300)  # 学分以整数存储，如3.0存为300
        ]
        order_by = [('credits', 'desc')]
        courses, total = advanced_query(Course, filters=filters, order_by=order_by, page=1, per_page=10)
        
        # 查询某个用户上传的所有资料，并加载关联的课程信息
        filters = [('user_id', 'eq', user_id)]
        joins = ['course']
        materials, total = advanced_query(Material, filters=filters, joins=joins)
    """
    try:
        # 创建基本查询
        query = db.session.query(model)
        
        # 处理关联查询
        if joins:
            for join in joins:
                if hasattr(model, join):
                    relation = getattr(model, join)
                    query = query.join(relation)
        
        # 应用过滤条件
        if filters:
            for field_name, operator, value in filters:
                if not hasattr(model, field_name):
                    continue
                    
                field = getattr(model, field_name)
                
                if operator == 'eq':
                    query = query.filter(field == value)
                elif operator == 'ne':
                    query = query.filter(field != value)
                elif operator == 'lt':
                    query = query.filter(field < value)
                elif operator == 'le':
                    query = query.filter(field <= value)
                elif operator == 'gt':
                    query = query.filter(field > value)
                elif operator == 'ge':
                    query = query.filter(field >= value)
                elif operator == 'like':
                    query = query.filter(field.like(value))
                elif operator == 'in':
                    query = query.filter(field.in_(value))
                elif operator == 'not_in':
                    query = query.filter(~field.in_(value))
                elif operator == 'between' and isinstance(value, (list, tuple)) and len(value) == 2:
                    query = query.filter(field.between(value[0], value[1]))
        
        # 应用排序
        if order_by:
            for field_name, direction in order_by:
                if not hasattr(model, field_name):
                    continue
                    
                field = getattr(model, field_name)
                if direction.lower() == 'desc':
                    query = query.order_by(field.desc())
                else:
                    query = query.order_by(field.asc())
        
        # 获取总记录数（如果需要）
        total = None
        if include_total:
            total = query.count()
        
        # 应用分页
        if page is not None and per_page is not None:
            page = max(1, page)  # 确保页码至少为1
            query = query.offset((page - 1) * per_page).limit(per_page)
        
        # 执行查询并返回结果
        items = query.all()
        return items, total
        
    except Exception as e:
        logger.error(f"高级查询失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return [], 0 if include_total else None




def query_courses(
    department_id=None, 
    keyword=None, 
    credit_range=None,
    course_type=None,
    page=None, 
    per_page=None, 
    order_by=None
):
    """
    课程高级查询函数
    
    参数:
        department_id (int): 院系ID
        keyword (str): 搜索关键词(课程名称、代码)
        credit_range (tuple): 学分范围，如(3.0, 5.0)
        course_type (str): 课程类型，如"专业必修"、"专业选修"等
        page (int): 页码(从1开始)
        per_page (int): 每页记录数
        order_by (str): 排序方式，可选值：
            - 'name_asc': 按名称升序
            - 'name_desc': 按名称降序
            - 'credit_asc': 按学分升序
            - 'credit_desc': 按学分降序
            - 'code': 按课程代码
    
    返回:
        tuple: (课程列表, 总数)
    """
    # 构建过滤条件
    filters = []
    joins = []
    
    if department_id:
        # 按院系ID过滤
        filters.append(('department_id', 'eq', department_id))
    
    if keyword:
        # 关键词过滤(模糊匹配课程名称或代码)
        filters.append(('name', 'like', f'%{keyword}%'))
        # 注意: advanced_query不支持OR条件，需要在应用层合并结果
    
    if credit_range and len(credit_range) == 2:
        # 学分范围过滤(注意学分以整数存储，需要转换)
        min_credit, max_credit = credit_range
        min_credit_int = int(float(min_credit) * 100)
        max_credit_int = int(float(max_credit) * 100)
        filters.append(('credits', 'between', (min_credit_int, max_credit_int)))
    
    if course_type:
        # 课程类型过滤
        filters.append(('type', 'eq', course_type))
    
    # 构建排序条件
    sort_conditions = []
    if order_by:
        if order_by == 'name_asc':
            sort_conditions.append(('name', 'asc'))
        elif order_by == 'name_desc':
            sort_conditions.append(('name', 'desc'))
        elif order_by == 'credit_asc':
            sort_conditions.append(('credits', 'asc'))
        elif order_by == 'credit_desc':
            sort_conditions.append(('credits', 'desc'))
        elif order_by == 'code':
            sort_conditions.append(('code', 'asc'))
    else:
        # 默认排序
        sort_conditions.append(('name', 'asc'))
    
    # 执行查询
    try:
        courses, total = advanced_query(
            Course, 
            filters=filters, 
            order_by=sort_conditions, 
            page=page, 
            per_page=per_page,
            joins=joins
        )
        
        # 如果关键词匹配代码的结果不在上面的结果中，需要额外查询并合并
        if keyword and keyword.strip():
            code_filters = [('code', 'like', f'%{keyword}%')]
            # 移除关键词过滤条件，保留其他条件
            other_filters = [f for f in filters if f[0] != 'name']
            code_filters.extend(other_filters)
            
            code_courses, _ = advanced_query(
                Course, 
                filters=code_filters, 
                order_by=sort_conditions,
                include_total=False
            )
            
            # 合并结果(去重)
            course_ids = {c.id for c in courses}
            for course in code_courses:
                if course.id not in course_ids:
                    courses.append(course)
            
            # 如果有分页，可能需要重新排序和截取
            if page and per_page:
                # 按排序条件重新排序
                if order_by == 'name_asc':
                    courses.sort(key=lambda c: c.name)
                elif order_by == 'name_desc':
                    courses.sort(key=lambda c: c.name, reverse=True)
                elif order_by == 'credit_asc':
                    courses.sort(key=lambda c: c.credits)
                elif order_by == 'credit_desc':
                    courses.sort(key=lambda c: c.credits, reverse=True)
                elif order_by == 'code':
                    courses.sort(key=lambda c: c.code)
                
                # 重新计算总数和分页
                total = len(courses)
                start = (page - 1) * per_page
                end = start + per_page
                courses = courses[start:end]
        
        return courses, total
    except Exception as e:
        logger.error(f"课程查询失败: {str(e)}")
        return [], 0

def query_materials(
    course_id=None,
    user_id=None,
    department_id=None,
    file_type=None,
    keyword=None,
    date_range=None,
    page=None,
    per_page=None,
    order_by=None,
    include_stats=True
):
    """
    资料高级查询函数
    
    参数:
        course_id (int): 课程ID
        user_id (int): 上传用户ID
        department_id (int): 院系ID(将关联查询课程表)
        file_type (str): 资料类型，如"试卷"、"笔记"等
        keyword (str): 搜索关键词(标题、描述)
        date_range (tuple): 上传日期范围，如(start_date, end_date)
        page (int): 页码(从1开始)
        per_page (int): 每页记录数
        order_by (str): 排序方式，可选值：
            - 'newest': 最新上传
            - 'downloads': 下载量
            - 'views': 浏览量
            - 'likes': 点赞数
            - 'title': 标题
        include_stats (bool): 是否包含统计信息(下载量、浏览量等)
    
    返回:
        tuple: (资料列表, 总数)
    """
    # 构建过滤条件
    filters = []
    joins = []
    
    if course_id:
        filters.append(('course_id', 'eq', course_id))
    
    if user_id:
        filters.append(('user_id', 'eq', user_id))
    
    if file_type:
        filters.append(('file_type', 'eq', file_type))
    
    if keyword:
        # 标题关键词搜索
        filters.append(('title', 'like', f'%{keyword}%'))
    
    if date_range and len(date_range) == 2:
        filters.append(('created_at', 'between', date_range))
    
    # 构建排序条件
    sort_conditions = []
    
    # 如果需要按统计信息排序，需要关联统计表
    if order_by in ['downloads', 'views', 'likes']:
        joins.append('stats')
    
    if order_by == 'newest':
        sort_conditions.append(('created_at', 'desc'))
    elif order_by == 'title':
        sort_conditions.append(('title', 'asc'))
    elif order_by == 'downloads':
        # 这里需要注意：高级查询函数可能不支持跨表排序
        # 实际实现时可能需要在应用层处理
        # 这里仅作为示例
        pass
    elif order_by == 'views':
        pass
    elif order_by == 'likes':
        pass
    else:
        # 默认按最新上传排序
        sort_conditions.append(('created_at', 'desc'))
    
    # 执行查询
    try:
        materials, total = advanced_query(
            Material, 
            filters=filters, 
            order_by=sort_conditions, 
            page=page, 
            per_page=per_page,
            joins=joins
        )
        
        # 如果搜索描述的结果不在上面的结果中，需要额外查询并合并
        if keyword and keyword.strip():
            desc_filters = [('description', 'like', f'%{keyword}%')]
            # 移除标题关键词过滤条件，保留其他条件
            other_filters = [f for f in filters if f[0] != 'title']
            desc_filters.extend(other_filters)
            
            desc_materials, _ = advanced_query(
                Material, 
                filters=desc_filters, 
                order_by=sort_conditions,
                include_total=False,
                joins=joins
            )
            
            # 合并结果(去重)
            material_ids = {m.id for m in materials}
            for material in desc_materials:
                if material.id not in material_ids:
                    materials.append(material)
            
            # 如果有分页，可能需要重新排序和截取
            if order_by and page and per_page:
                # 在应用层面处理特殊排序
                if order_by == 'downloads':
                    materials.sort(key=lambda m: getattr(m.stats, 'download_count', 0) if m.stats else 0, reverse=True)
                elif order_by == 'views':
                    materials.sort(key=lambda m: getattr(m.stats, 'view_count', 0) if m.stats else 0, reverse=True)
                elif order_by == 'likes':
                    materials.sort(key=lambda m: getattr(m.stats, 'like_count', 0) if m.stats else 0, reverse=True)
                elif order_by == 'newest':
                    materials.sort(key=lambda m: m.created_at, reverse=True)
                elif order_by == 'title':
                    materials.sort(key=lambda m: m.title)
                
                # 重新计算总数和分页
                total = len(materials)
                start = (page - 1) * per_page
                end = start + per_page
                materials = materials[start:end]
        
        # 确保统计信息已加载（如果不包含在关联查询中）
        if include_stats and 'stats' not in joins:
            for material in materials:
                if not material.stats:
                    material.stats = MaterialStats(material_id=material.id)
        
        return materials, total
    except Exception as e:
        logger.error(f"资料查询失败: {str(e)}")
        return [], 0

def get_course_types():
    """
    获取所有课程类型
    
    返回:
        list: 课程类型列表
    """
    try:
        # 使用distinct查询获取所有不重复的课程类型
        types = Course.query.with_entities(Course.type).distinct().all()
        return [t[0] for t in types]
    except Exception as e:
        logger.error(f"获取课程类型失败: {str(e)}")
        return []

def get_material_types():
    """
    获取所有资料类型
    
    返回:
        list: 资料类型列表
    """
    try:
        # 使用distinct查询获取所有不重复的资料类型
        types = Material.query.with_entities(Material.file_type).distinct().all()
        return [t[0] for t in types]
    except Exception as e:
        logger.error(f"获取资料类型失败: {str(e)}")
        return []

def query_materials(user_id=None, keyword=None, order_by=None, page=None, per_page=None):
    """
    高级查询材料函数，支持多条件过滤、排序和分页
    
    参数:
        user_id (int): 上传用户ID
        keyword (str): 搜索关键词(标题、课程名称)
        order_by (str): 排序方式，可选值：
            - 'newest': 按最新上传排序
            - 'downloads': 按下载次数排序
            - 'title': 按标题排序
        page (int): 页码(从1开始)
        per_page (int): 每页记录数
    
    返回:
        tuple: (材料列表, 总数)
    """
    from sqlalchemy import or_
    from database.models import Material, Course
    
    try:
        # 构建基础查询
        query = Material.query
        
        # 添加用户ID过滤
        if user_id is not None:
            query = query.filter(Material.user_id == user_id)
        
        # 添加关键词过滤 - 同时搜索标题和课程名称
        if keyword:
            # 修改这里，添加对课程名称的搜索
            query = query.join(Course, Material.course_id == Course.id).filter(
                or_(
                    Material.title.ilike(f"%{keyword}%"),
                    Course.name.ilike(f"%{keyword}%")
                )
            )
        
        # 计算总记录数
        total = query.count()
        
        # 添加排序
        if order_by == 'newest':
            query = query.order_by(Material.created_at.desc())
        elif order_by == 'downloads':
            query = query.join(Material.stats).order_by(Material.stats.download_count.desc())
        elif order_by == 'title':
            query = query.order_by(Material.title)
        else:
            # 默认按最新上传排序
            query = query.order_by(Material.created_at.desc())
        
        # 添加分页
        if page and per_page:
            query = query.offset((page - 1) * per_page).limit(per_page)
        
        # 执行查询
        materials = query.all()
        
        return materials, total
    except Exception as e:
        print(f"查询材料失败: {str(e)}")
        return [], 0

# 用户关注相关操作
def is_following(user_id, target_id):
    """
    检查用户是否关注了目标用户
    
    参数:
        user_id: 用户ID
        target_id: 目标用户ID
    
    返回:
        布尔值，表示是否已关注
    """
    if user_id == target_id:
        return False
        
    return Relationship.query.filter_by(
        follower_id=user_id, 
        followed_id=target_id
    ).first() is not None

def follow_user(user_id, target_id):
    """
    关注用户
    
    参数:
        user_id: 用户ID
        target_id: 目标用户ID
    
    返回:
        布尔值，表示操作是否成功
    """
    # 不能关注自己
    if user_id == target_id:
        return False
        
    # 已经关注过了
    if is_following(user_id, target_id):
        return False
        
    try:
        follow = Relationship(follower_id=user_id, followed_id=target_id)
        db.session.add(follow)
        db.session.commit()
        return True
    except Exception as e:
        db.session.rollback()
        # 记录错误信息
        print(f"关注用户失败: {str(e)}")
        return False

def unfollow_user(user_id, target_id):
    """
    取消关注用户
    
    参数:
        user_id: 用户ID
        target_id: 目标用户ID
    
    返回:
        布尔值，表示操作是否成功
    """
    try:
        relationship = Relationship.query.filter_by(
            follower_id=user_id, 
            followed_id=target_id
        ).first()
        
        if relationship:
            db.session.delete(relationship)
            db.session.commit()
            return True
        return False
    except Exception as e:
        db.session.rollback()
        # 记录错误信息
        print(f"取消关注用户失败: {str(e)}")
        return False

def get_following(user_id):
    """
    获取用户关注的所有人列表
    
    参数:
        user_id: 用户ID
    
    返回:
        list: 用户关注的所有人列表
    """
    try:
        users = User.query.join(
            Relationship, Relationship.followed_id == User.id
        ).filter(
            Relationship.follower_id == user_id
        ).order_by(
            Relationship.created_at.desc()
        ).all()
        
        return users
    except Exception as e:
        # 记录错误信息
        logger.error(f"获取关注列表失败: {str(e)}")
        return []

def get_followers(user_id):
    """
    获取关注该用户的所有人列表
    
    参数:
        user_id: 用户ID
    
    返回:
        list: 关注该用户的所有人列表
    """
    try:
        users = User.query.join(
            Relationship, Relationship.follower_id == User.id
        ).filter(
            Relationship.followed_id == user_id
        ).order_by(
            Relationship.created_at.desc()
        ).all()
        
        return users
    except Exception as e:
        # 记录错误信息
        logger.error(f"获取粉丝列表失败: {str(e)}")
        return []