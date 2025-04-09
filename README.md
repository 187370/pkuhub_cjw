## 使用
1. 安装依赖
```bash
# 注意在根目录下执行
pip install -r requirements.txt -i https://pypi.douban.com/simple/
```
2. 启动主程序
``` bash
python3 main.py
# 如果是在服务器上则自行搜索如何使用deploy.py
```
## 未解决

- flush的输出位置不对(可能需要模板继承) 已修复
- 初始的头像不对 已修复
- 还有一些函数没有归类,目前在根目录下utils的other.py下
- 目前不清楚数据库的稳定性
- 不清楚并发性能(邮箱应该能部分支持并发)
- 通知功能未添加(可能需要再写一个页面单独路由)
- 可以减少邮箱输入的长度,不写后缀
- 关于我们还没写
- 忘记密码还没写
- 管理员的管理功能没写
- 表的长度有些使用length有些使用.count(),暂时没有搞明白原理
- 模板内容易出问题(html文件)

## tip
**如何导出环境依赖?**

使用 `pipreqs` 扫描项目代码，仅生成项目实际调用的依赖。
```bash
# 安装 pipreqs
pip install pipreqs

# 在项目根目录下运行
pipreqs ./ --encoding=utf8 --force
```
- **特点**：通过分析代码中的 `import` 语句生成依赖列表，避免冗余[1](@ref)[2](@ref)[19](@ref)[48](@ref)。
- **常见问题**：若出现编码错误，可尝试 `--encoding='iso-8859-1'`[2](@ref)[48](@ref)。


**使用black库实现代码格式化**
```bash
cd c:\Users\exqin\Desktop\pkuhub
# 移动到当前目录
black .
```