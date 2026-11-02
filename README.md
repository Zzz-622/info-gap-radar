# DSH 信息差雷达（Info-Gap Radar）· 落地文档

> 状态：✅ 已在本工作区部署并跑通首轮采集与日报。剩下 3 个收尾动作（4.1~4.3）完成后即可全自动运行。
> 原则：**全免费数据源 + 零依赖脚本 + 少量 LLM 费用（可选，可降至 0 元）**。

## 1. 系统架构

```
定时触发(Windows任务计划, 每日07:30) 或 手动
        │
        ▼
radar\run-radar.cmd  ──►  dsh headless（一次性agent, 按 .dsh/skills 的 radar* skills 执行）
        │
        ├─ 1) fetch_radar.py   25个免费源(热榜/RSS/API) → SQLite 快照 radar\data\radar.db
        ├─ 2) diff_radar.py    对比历史 → 新增/变化/告警 → radar\data\latest_diff.json
        ├─ 3) report_radar.py  纯脚本生成基础日报(0成本) → radar\reports\radar-YYYY-MM-DD.md
        ├─ 4) LLM 雷达解读      读 latest_diff.json 追加"信息差三问"章节(≤600字, 约¥0.05/次)
        └─ 5) LLM 学习卡        挑一条信号写费曼卡 → radar\learn\cards\ + 更新主题时间线
        │
        ▼
知道层: radar\reports\ 日报/周报     学习层: radar\learn\ 卡片/主题档案/复习计划
```

双层设计：**知道层**回答"发生了什么"（日报），**学习层**回答"为什么、怎么运作、我记住了吗"（费曼卡 + 主题时间线 + 间隔重复）。

## 2. 目录结构

```
<工作区>\
├─ .dsh\skills\              # DSH skill(热加载, 已安装)
│  ├─ radar\SKILL.md         #   总路由
│  ├─ radar-fetch\SKILL.md   #   采集
│  ├─ radar-diff\SKILL.md    #   差异/告警
│  ├─ radar-report\SKILL.md  #   报告/解读
│  └─ radar-learn\SKILL.md   #   学习层(费曼卡/主题档案/复习)
└─ radar\
   ├─ config\sources.json    # 25 个信息源(增删改这里)
   ├─ config\alerts.json     # 告警关键词 + 娱乐过滤词 + 条数
   ├─ config\tophub-nodes.tsv# tophub 116 个榜单节点对照表(扩源用)
   ├─ scripts\fetch_radar.py # 采集(仅标准库)
   ├─ scripts\diff_radar.py  # 差异+告警(仅标准库)
   ├─ scripts\report_radar.py# 0 成本日报(仅标准库)
   ├─ scripts\quiz_radar.py  # 间隔重复复习调度(仅标准库)
   ├─ run-radar.cmd          # 每日无人值守入口
   ├─ run-radar-weekly.cmd   # 周报+复习入口
   ├─ data\                  # radar.db / last_run.json / latest_diff.json
   ├─ logs\radar.log         # 定时任务日志
   ├─ reports\               # 日报/周报(知道层)
   └─ learn\                 # 学习层(新)
      ├─ topics.json         #   主题清单(slug/关键词/为什么关心)
      ├─ cards\              #   费曼学习卡(每天一张, 日积月累)
      ├─ topics\<slug>\      #   每个主题: timeline.md / notes.md / questions.md
      └─ reviews\            #   间隔重复计划 schedule.json + 复习记录
```

## 3. 当前进度

| 事项 | 状态 |
|---|---|
| 4 个 radar skills（工作区 + 全局 `~/.dsh/skills`） | ✅ 已安装 |
| 28 个免费信息源连通性验证 | ✅ 28/28 通过 |
| 首轮采集（507 条入库）→ 差异 → 日报 | ✅ 已跑通（见 `radar\reports\`） |
| `dsh` CLI 验证（`headless --help`） | ✅ 通过 |
| 用户 PATH 注册 `dsh` 命令 | ⬜ 可选，见 4.1 |
| `DEEPSEEK_API_KEY` 配置（定时任务必需） | ⬜ 见 4.2 |
| Windows 定时任务注册 | ⬜ 见 4.3 |

## 4. 收尾安装命令（PowerShell）

### 4.1 把 `dsh` 命令加进 PATH（可选，1 分钟）

```powershell
setx PATH "%PATH%;D:\deepseekharness\resources\runtime\cli\bin"
```

新开终端后验证：`dsh headless --help`（不加 PATH 也可直接用完整路径 `D:\deepseekharness\resources\runtime\cli\bin\dsh.cmd`）。

### 4.2 配置 API Key（定时/headless 运行必需）

headless 模式**不读取 GUI 里保存的凭据**，只读环境变量 / `<运行目录>\.env` / `%USERPROFILE%\.dsh\.env`：

```powershell
notepad $env:USERPROFILE\.dsh\.env
```

写入一行（用你在 DSH GUI「模型」页使用的同一个 DeepSeek Key）：

```
DEEPSEEK_API_KEY=sk-你的key
```

验证：`dsh headless "请只回复两个字：正常"` → 输出"正常"即成功。

> 注：0 成本档（不跑 LLM 解读）不需要 key——直接用 5.3 的纯脚本命令。

### 4.3 注册定时任务（推荐）

```powershell
# 每日 07:30 自动跑雷达（采集→差异→日报→LLM解读）
schtasks /Create /TN "DSH-Radar-Daily" /TR "\"C:\Users\32094\Documents\deepseek-harness\default-workspace\radar\run-radar.cmd\"" /SC DAILY /ST 07:30 /F

# 可选: 每周一 08:00 生成周报(把任务文本换成"生成周报"即可, 或直接在 GUI 里让 agent 汇总近7天日报)
schtasks /Create /TN "DSH-Radar-Weekly" /TR "\"C:\Users\32094\Documents\deepseek-harness\default-workspace\radar\run-radar-weekly.cmd\"" /SC WEEKLY /D MON /ST 08:00 /F

# 查看/删除
schtasks /Query /TN "DSH-Radar-Daily"
schtasks /Delete /TN "DSH-Radar-Daily" /F
```

日志在 `radar\logs\radar.log`。

### 4.4 全局安装 skills（已执行，换机器时重跑）

```powershell
robocopy "C:\Users\32094\Documents\deepseek-harness\default-workspace\.dsh\skills" "$env:USERPROFILE\.dsh\skills" /E
```

DSH 的 skill 加载路径（优先级从高到低）：`<项目>\.dsh\skills` → `<项目>\.agents\skills` → 自定义目录 → `~\.dsh\skills` → `~\.agents\skills`，且**热加载**（改完即生效，无需重启）。

## 5. 三种使用方式

### 5.1 全自动（主力）
每天 07:30 任务计划自动产出 `radar\reports\radar-YYYY-MM-DD.md`。你只需要偶尔打开目录扫一眼，或在 DSH 里问。

### 5.2 GUI 对话式（DSH Web 界面，新开一个会话即可看到 radar skills）
- "**今天有什么信息差？**" → agent 直接读最新日报回答（不重跑脚本，零成本）
- "**今天有什么值得看的？**" → 读今日精选报告，摘 top 3-5 条讲（私人编辑）
- "**跑一次雷达**" → 全流程执行并口述摘要
- "**把告警关键词加上『关税』**" → agent 改 `alerts.json` 并重跑 diff
- "**更新我的画像：我对 XX 也感兴趣 / 以后别推 XX**" → agent 改 `profile.json` 并重跑精选
- "**新增一个信息源：虎扑热帖**" → agent 从 `tophub-nodes.tsv` 找节点 id 加进 `sources.json`
- "**今天学什么？**" → 读今日学习卡，用费曼方式讲给你听
- "**给我讲讲 AI 产业与资本**" → 读该主题 timeline/notes，讲来龙去脉
- "**考考我 / 复习**" → 按间隔重复计划抽题自测，答完推进复习进度
- "**反驳我：XX 观点**" → 让 agent 找证据支持或反驳你的判断

### 5.3 纯脚本 / 0 成本档（不需要 API key）
```powershell
$py = 'C:\Users\32094\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe'
$ws = 'C:\Users\32094\Documents\deepseek-harness\default-workspace'
& $py "$ws\radar\scripts\fetch_radar.py"     # 采集
& $py "$ws\radar\scripts\diff_radar.py"      # 差异+告警
& $py "$ws\radar\scripts\report_radar.py"    # 生成 0 成本日报
```

### 5.4 命令行 headless
```powershell
dsh headless "跑一次雷达并输出摘要"
dsh headless --session-id session-xxx "继续深入分析上周的财经信号"   # 延续同一会话
```

### 5.5 学习层用法（从"知道"到"学到"）

三个机制，都围绕 `radar\learn\` 目录：

| 机制 | 目录 | 节奏 | 解决什么 |
|---|---|---|---|
| **费曼学习卡** | `learn\cards\` | 每天 1 张（定时任务自动写） | 用"一句话解释+机制+反面观点+自测题"倒逼理解，少而深 |
| **主题时间线** | `learn\topics\<slug>\` | 每次相关信号出现时追加 | 把碎片新闻攒成有因果的叙事，看到来龙去脉 |
| **间隔重复复习** | `learn\reviews\` | 1/3/7/14/30/60 天（脚本调度） | 对抗遗忘曲线，卡片到期时自测 |

对话式学习见 5.2；复习调度脚本：
```powershell
& $py radar\scripts\quiz_radar.py --scan      # 新卡登记进复习计划
& $py radar\scripts\quiz_radar.py             # 查今日到期复习
& $py radar\scripts\quiz_radar.py --done 2026-11-01-siliconflow-ipo   # 复习完成, 推进到下一轮
```

主题清单在 `radar\learn\topics.json`（已预置 3 个：AI Agent 与自动化 / AI 产业与资本 / 宏观与市场机制），想加主题直接说"我想跟踪学习 XX"，agent 会建目录。

## 6. 信息源矩阵（38 源，全部免费、已验证连通；中英双语覆盖）

> 定制记录：保留 AI·技术 / 财经·市场 / 科技商业 / 科技数码·产品 / 舆情热点 / 安全 / 国际·新闻 七个领域；**已移除**消费捡漏（淘宝/京东热卖）与 B站热门视频；舆情热点源按 `exclude_keywords` **过滤娱乐八卦**；2026-11-02 起新增 13 个海外英文源。想改，直接改 `radar\config\sources.json`，或对 DSH 说"把 XX 加回来/去掉"。

| 领域 | 源 | 说明 |
|---|---|---|
| 舆情热点 | 微博热搜 / 知乎热榜 / 百度实时热点 / 抖音总榜 / B站全站日榜 | tophub 聚合，带热度数值；娱乐八卦已过滤 |
| 新闻时政 | 澎湃热榜 / BBC中文 | |
| 财经 | 华尔街见闻 / 新浪财经 / 雪球热帖 / 美元汇率 | 优先领域，新增即告警 |
| 财经·海外 | CNBC Markets | 英文财经 |
| 科技商业 | 36氪热榜 / 虎嗅 / Readhub | |
| 科技·海外 | TechCrunch / The Verge / Ars Technica / Wired / MIT Tech Review | 英文科技媒体（RSS+Atom 均支持） |
| AI前沿 | 机器之心 / 量子位 / GoogleNews·AI（全球 AI 新闻聚合） | 优先领域 |
| 科技数码 | IT之家 / 少数派RSS | |
| 技术趋势 | 掘金 / GitHub热榜 / GitHub Trending / HackerNews首页·AI / Lobsters / dev.to | 优先领域 |
| 产品出海 | Product Hunt | 海外新品信号 |
| 安全 | FreeBuf | 漏洞/安全事件 |
| 学术前沿 | arXiv cs.AI 最新论文 | 优先领域 |
| 国际·英文 | BBC News / The Guardian / 纽约时报首页 | 英文时事 |

扩源：`radar\config\tophub-nodes.tsv` 里有 tophub 全部 116 个榜单；任意网站的 RSS/Atom 直接加进 `sources.json`；想看某个主题的全球报道，用 Google News RSS 模板（换关键词即换主题，免费）：
`https://news.google.com/rss/search?q=<关键词>+when:1d&hl=en-US&gl=US&ceid=US:en`

## 7. 告警与过滤规则（radar\config\alerts.json）

```json
{
  "keywords": ["AI","大模型","裁员","降息","暴跌","漏洞","新规","制裁","并购", ...],
  "min_hot": 0,                              // 热度阈值, 0=关闭
  "priority_domains": ["财经","技术趋势","学术前沿"],  // 这些领域的新增条目自动告警
  "exclude_keywords": ["综艺","官宣","恋情","演唱会","八卦", ...],  // 娱乐八卦过滤(采集时丢弃)
  "caps": {"new":300,"updated":60,"alerts":40,"top_hot":15}
}
```
改完无需重启：`& $py radar\scripts\fetch_radar.py` 立即生效。想加过滤词（如体育赛事、某明星名字）往 `exclude_keywords` 里加即可。

## 8. 成本估算

| 方案 | 每日费用 | 说明 |
|---|---|---|
| 0 成本档 | ¥0 | 只跑脚本（采集/差异/日报/规则精选/复习调度），不需要 API key |
| LLM 解读+学习卡档 | ≈¥0.05~0.12 | 日报解读 + 每日 1 张费曼卡（读 `latest_diff.json` 约 15~25k token + 写 600 字解读 + 写卡片），按 DeepSeek API 计费，**每月约 ¥2~4** |
| +私人编辑精选+深读档 | 再 +¥0.08~0.2/日 | 画像精选（LLM 判分）约 ¥0.02~0.05 + 深读 top3 原文摘要约 ¥0.05~0.15，**合计每月约 ¥5~10** |
| 深度周报档 | 每周 +¥0.3~0.6 | 汇总 7 天做跨域分析 + 周复习自测出题 |

可选付费增强（都不必须）：Firecrawl（免费 500 积分/月，抓 JS 渲染页）、Tavily（免费 1000 次/月，搜索聚合）。

## 9. 扩展路线（打破更深的信息差）

| 目标 | 方案 | 说明 |
|---|---|---|
| 二手捡漏 | 审查后安装 [xianyu-monitor-skill](https://github.com/lenkin233/xianyu-monitor-skill) 等闲鱼 skill 到 `~\.dsh\skills` 或 `~\.agents\skills` | 登录态+强风控，**自担账号风险**，低频小批量 |
| 电商比价 | [MarketSpider-Agent-Skill](https://github.com/Rexray117/MarketSpider-Agent-Skill) / browser-use 插件（官方 discussion [#2853](https://github.com/deepseek-ai/deepseek-harness/discussions/2853)） | 需自行审查代码 |
| 房价 | [lianjia-beike-spider](https://github.com/KivenJia/Python--lianjia-beike-spider) 独立运行，结果以文件形式喂给雷达 | 与本系统解耦最安全 |
| 招聘情报 | BOSS直聘类爬虫 | 高风险，强烈建议不做或仅手动 |
| 更多数据源 | 自建 RSSHub / 任意 RSS / 自定义 JSON API | 在 `fetch_radar.py` 加一个解析函数即可 |
| MCP 扩展 | 在 `~\.dsh\profiles\desktop\cordis.patch.yml` 追加 `dsh-mcp-client` 条目（模板见官方 mcp 模板） | 如 firecrawl-mcp |

## 10. 合规与风险提示

- 本系统只使用**公开免费接口与 RSS**，采集频率低（每日一次、每源≤30 条）、带 UA、单线程。
- tophub 是第三方聚合站：**非官方数据接口，随时可能改版或失效**。源失效时日报会标注 `[fail]`，去 `tophub-nodes.tsv` 换节点即可。
- 登录态站点（闲鱼/京东商详/BOSS直聘/小红书）抓取有**账号封禁与法律风险**，默认不做；坚持要做请自行评估并降低频率。
- 报告数据可能滞后或不全，投资决策请交叉验证，**不构成投资建议**。

## 11. 常见问题

- **控制台/终端中文乱码？** 脚本内部全部 UTF-8 落盘，日报文件没有乱码；终端显示乱码不影响数据。
- **某源连续失败？** `sources.json` 里换一个同领域源（tophub 节点表），或删除该源。
- **想改每天跑的时间？** `schtasks /Change /TN "DSH-Radar-Daily" /ST 08:00`。
- **GUI 会话里看不到 radar skills？** 新开会话即可（skill 目录热加载，但会话的 skill 目录在会话创建时快照）。

## 12. 关机也能跑：云端运行（GitHub Actions，免费）

采集脚本是纯 Python、LLM 解读走 DeepSeek API，**都不依赖本机**。把 `radar/` 目录推到一个 GitHub 仓库，云端每天北京时间 07:30 自动跑全套并提交结果回仓库，手机打开 GitHub 就能看。已备好组件：

- `.github\workflows\radar-daily.yml` — 每日 07:30(北京) 定时工作流：采集→差异→日报→LLM解读(可选)→提交
- `scripts\llm_digest.py` — 云端的 LLM 解读步骤（有 `DEEPSEEK_API_KEY` 就追加解读，没有就跳过，两种模式都兼容）

### 部署 4 步

```powershell
cd C:\Users\32094\Documents\deepseek-harness\default-workspace\radar
git init
git add .
git commit -m "info-gap radar"
# 在 github.com 新建一个仓库(公开=免费无限用; 私有=每月2000分钟, 本任务每天约2分钟, 够用)
git remote add origin https://github.com/<你的用户名>/<仓库名>.git
git push -u origin main
```

2. **配 API Key（可选）**：GitHub 仓库页 → Settings → Secrets and variables → Actions → 新建 `DEEPSEEK_API_KEY`。不配也能跑，只是日报没有 LLM 解读章节。
3. **验证**：仓库页 → Actions 标签 → `radar-daily` → Run workflow 手动触发一次。
4. **手机看**：装 GitHub App / 网页访问仓库的 `reports/` 目录即可；想要微信推送再加 Server酱（见下）。

### 与本地任务的关系

- 云端为主时，本机的 `DSH-Radar-Daily` 定时任务可以**删掉**（`schtasks /Delete /TN "DSH-Radar-Daily" /F`），避免两份数据各跑各的。
- 开机后想把云端数据同步回本机（这样 DSH 里问"今天有什么信息差"也是最新数据）：
  ```powershell
  cd C:\Users\32094\Documents\deepseek-harness\default-workspace\radar
  git pull
  ```

### 注意事项

- Actions 调度有 5~15 分钟延迟；runner 在美国，个别国内源若在美区访问异常，日报会标 `[fail]`（实测 tophub 等均可访问）。
- 升级玩法：微信推送加 Server酱（`sct.ftqq.com` 免费，把日报摘要 POST 过去）；或改用轻量云服务器（约 ¥50~150/年）跑 cron，可控性最强。

## 13. 私人编辑：阅读并筛选"对你有用"的新闻

采集只是第一步。精选层会**按你的画像阅读全部今日信号，只留下对你有用的 ≤10 条**，每条给出"为什么有用 + 可行动作"，并对 top 3 抓取原文写摘要（不用点开链接）。

- 画像配置：`radar\config\profile.json`——用途（职业与工作/学习成长/投资理财）、兴趣加权词、加权领域、排除词、每日条数、深读条数
- 脚本：`scripts\pick_news.py`（精选，有 key 走 LLM 判分、无 key 退化为 0 成本规则精选）、`scripts\deep_read.py`（深读，经免费 r.jina.ai 抓原文）
- 产物：`reports\radar-YYYY-MM-DD-picks.md`（今日精选 + 深读摘要）
- 反馈闭环：对 DSH 说"**这条没用，以后别推这类**" → agent 把关键词加进 `profile.json` 的 `exclude`；说"**我对 XX 也感兴趣**" → 加进 `interests`。画像越用越准

## 14. 网页访问：随时打开随时读（GitHub Pages）

所有报告会渲染成**移动端友好的静态网页**，托管在 GitHub Pages，手机浏览器随时访问（关机、电脑不在身边都行）。

- 生成：`scripts\build_site.py` → `docs\`（index.html 今日页 + 归档页 + 每篇日报/精选/学习卡的独立页面，含 PWA manifest，可"添加到主屏幕"当 App 用）
- **本地预览**：双击 `docs\index.html` 即可
- **上线 3 步**（云端工作流已自动构建并提交 docs/）：
  1. 推送到 GitHub（见第 12 节）
  2. 仓库 Settings → Pages → Source 选 `Deploy from a branch` → 分支 `main`、目录 `/docs` → Save
  3. 等 1~2 分钟，访问 `https://<你的用户名>.github.io/<仓库名>/` —— 收藏到手机，随时打开阅读

手机体验：iOS Safari「分享 → 添加到主屏幕」、Android Chrome「⋮ → 添加到主屏幕」，之后就像打开一个小程序一样直达当日精选。
