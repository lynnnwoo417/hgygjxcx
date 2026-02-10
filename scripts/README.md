# 回归预告机 - 爬虫脚本

## 打歌预录回归日程（comebacks）

本地 `comebacks.json/js` 可能来自不同来源：

- **Reddit r/kpop wiki（历史基线）**：`scripts/scrape_reddit_comebacks.py`
- **KPOP OFFICIAL（补充/校准某个月）**：`scripts/scrape_kpopofficial.py --month=N`（增量合并进本地历史）

```bash
# 1) 先用 Reddit 生成/更新本地历史（若你的网络环境可访问 Reddit）
python3 scripts/scrape_reddit_comebacks.py

# 2) 再用 KPOP OFFICIAL 增量更新指定月份（例如只更新三月）
python3 scripts/scrape_kpopofficial.py --month=3
```

- 写入：`miniprogram/data/comebacks.js`、`comebacks.json`
- 小程序中显示为 **回归** 类型

### Reddit 403（Blocked）怎么办

部分网络环境下直接请求 Reddit wiki 会 403。此时可用 Reddit OAuth（app-only）绕过：

1. 在 `reddit.com/prefs/apps` 创建一个 app，拿到 `client_id` 和 `client_secret`
2. 设置环境变量后再跑：

```bash
export REDDIT_CLIENT_ID="xxx"
export REDDIT_CLIENT_SECRET="yyy"
export REDDIT_USER_AGENT="Mozilla/5.0 (compatible; KpopScheduleBot/1.0)"
python3 scripts/scrape_reddit_comebacks.py
```

### 环境

仅依赖 Python 3 标准库，无需安装第三方包。请遵守各网站使用条款与 robots 规则。
