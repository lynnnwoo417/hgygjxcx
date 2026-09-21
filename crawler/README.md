# 爬虫说明（给以后加数据源用）

入口：`python3 crawler/main.py`

当前正式 Demo 源：`crawler/sources/kpopofficial_comebacks.py`  
（KPOP OFFICIAL 回归列表，复用项目里已能工作的解析器）

新增网站时：

1. 在 `crawler/sources/` 新建一个 py 文件
2. 实现 `fetch_events()`，返回统一字段的 dict 列表
3. 在 `crawler/main.py` 的 `SOURCES` 里加一行

统一字段见项目 SETUP.md。
