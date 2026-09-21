# 回归预告机 · 从零接上数据库（给非程序员）

这份说明只讲「点哪里、复制什么、粘贴到哪里」。
先不要一次做完所有步骤。当前请只做文末「你现在只要做的两件事」。

---

## 现在这套系统怎么走

官方网页
→ Python 爬虫每小时抓一次
→ 存进 Supabase 数据库
→ API 读数据库
→ 微信小程序打开时自动显示

你不需要自己一台 Linux 服务器，也不用安装 Docker。

---

## 现有小程序已经怎么工作（我检查过）

1. 活动数据现在在这些文件里：
   - `miniprogram/data/comebacks.js` / `.json`（回归）
   - `miniprogram/data/concerts.js` / `.json`（演唱会）
   - `miniprogram/data/ticket_concerts.js` / `.json`（票务演唱会）
   - `miniprogram/data/fansigns.js` / `.json`（签售）
   - `miniprogram/data/festas.js` / `.json`（活动）

2. 一条活动主要字段：
   `id artist type date dateKey detail ticketPlatform ticketTime venue showTime detailUrl officialUrl locationText coverImage`

3. 搜索会看：艺人、活动名、类型、地点、场馆、票务平台。

4. 日历圆点看：`dateKey`（哪一天）+ 类型筛选 + 国家/地区筛选。

5. 详情页看：上面这些字段，外加官方链接按钮。

6. 收藏用手机本地 `my_favorites`，加入行程用 `my_records`。第一阶段继续这样，不上云。

7. 点进详情：不是网址带 id，而是先把活动放进 `app.globalData.eventDetail` 再跳转。现在 API 可用时，详情页会再用 id 向服务器要一份完整数据。

8. 以前爬虫偶尔把场馆写进 `ticketTime`。代码里已有纠正，数据库里开票时间和场馆是分开的两列。

没配置 API 时，小程序仍用本地文件，不会空白。

---

## 第一步：注册 Supabase

1. 用电脑浏览器打开：https://supabase.com
2. 点右上角 **Start your project** 或 **Sign in**
3. 用 GitHub 登录最方便（有 GitHub 就点 Continue with GitHub）

## 第二步：创建项目

1. 登录后点绿色按钮 **New project**
2. Organization 选默认即可
3. **Name** 填：`hgygj`（随便，能记住就行）
4. **Database Password** 自己设一个并记在备忘录（以后很少用到）
5. **Region** 选离你近的，例如 `Northeast Asia (Tokyo)`
6. 点 **Create new project**
7. 等大约 1–2 分钟，直到项目变成可用

## 第三步：运行建表 SQL

1. 左侧点 **SQL Editor**
2. 点 **New query**
3. 打开本项目里的文件 `supabase/schema.sql`
4. 全选复制，粘贴到 SQL Editor 大框
5. 点右下角 **Run**
6. 下方出现 success 就对了
7. 左侧点 **Table Editor**，应能看到表名 **events**

## 第四步：找到 SUPABASE_URL

1. 左侧最下面点 **Project Settings**（齿轮）
2. 点 **API**
3. 找到 **Project URL**
4. 复制，类似：`https://abcdefgh.supabase.co`

## 第五步：找到 service_role key

仍在 **Settings → API** 页面：

1. 找到 **Project API keys**
2. 在 `service_role` 那一行点 **Reveal** 再复制
3. 这一串绝对不能发给别人，不能写进小程序，不能发到微信群

## 第六步：这些东西分别放在哪里

在项目根目录复制：

`.env.example` → 改名为 `.env`

然后：

- `SUPABASE_URL=` 后面粘贴第四步的网址
- `SUPABASE_SERVICE_ROLE_KEY=` 后面粘贴第五步的 key

`.env` 已被 git 忽略，不会上传。

GitHub 上线爬虫时，同样两个名字要填进 GitHub Secrets（见第十步）。

## 第七步：本地测试 API

1. 打开「终端」
2. 进入本项目文件夹
3. 运行：

```bash
python3 api/server.py
```

4. 看到 `API 已启动 http://127.0.0.1:5001` 就对了
5. 浏览器打开：`http://127.0.0.1:5001/api/events`
6. 若表是空的，会显示 `"schedules": []`，这是正常的，等爬虫写入后才有内容

## 第八步：测试微信小程序

1. 用微信开发者工具打开本项目
2. 打开文件 `miniprogram/utils/config.ts`
3. 把 `SCHEDULE_API_BASE` 改成 `'http://127.0.0.1:5001'`
4. 详情里勾选 **不校验合法域名**（本地调试用）
5. 重新编译
6. API 没数据时会自动退回本地 `data/*.js`，首页仍能打开

## 第九步：创建 GitHub 仓库

如果你已经有仓库 `lynnnwoo417/hgygjxcx`，直接推送新文件即可。

如果还没有：

1. 打开 https://github.com/new
2. Repository name 填一个英文名
3. 选 **Private** 更安全
4. 不要勾选添加 README（项目里已有）
5. 点 **Create repository**
6. 按页面提示把本地项目推上去

## 第十步：添加 GitHub Secrets

1. 打开你的 GitHub 仓库
2. 点 **Settings**
3. 左侧 **Secrets and variables** → **Actions**
4. 点 **New repository secret**
5. Name 填 `SUPABASE_URL`，Value 粘贴第四步网址，点 Add
6. 再添加一条 `SUPABASE_SERVICE_ROLE_KEY`，粘贴第五步 key

不要把 key 写进 `.yml` 文件。

## 第十一步：确认爬虫自动运行成功

1. 仓库点 **Actions**
2. 左侧点 **crawler**
3. 点 **Run workflow** → **Run workflow**（立即手动跑一次，不用等一小时）
4. 点进这次运行
5. 全部绿勾 = 成功
6. 回到 Supabase → Table Editor → events，应能看到行数增加

GitHub 免费额度：公开仓库的 Actions 基本够用；私有仓库每月有免费分钟数。如果运行被跳过或失败，打开这次运行的日志，把红色报错发给我即可。

---

## 常用命令（以后用）

```bash
python3 crawler/main.py
python3 crawler/seed_from_local.py
python3 api/server.py
```

`crawler/main.py`：抓 KPOP OFFICIAL 回归页并写入数据库  
`seed_from_local.py`：把已经爬好的本地真实 JSON 一次性导入（不是编造）

---

## 你现在只要做的两件事

1. 打开 https://supabase.com 用 GitHub 登录  
2. 点 **New project** 创建一个项目，等到它显示绿色可用

做完后告诉我「项目已创建」。  
**先不要复制密钥，也不要改小程序。** 下一步我再带你点 SQL 和复制地址。
