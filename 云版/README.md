# 云版：电脑关机也能每天更新

这套东西让《资讯》脱离你的电脑：GitHub Actions 每天北京时间 07:30 自动抓新闻、调 DeepSeek 写稿、生成网页，发布到 GitHub Pages。手机打开固定网址即可，电脑开不开都无所谓。

```
云版/
├─ generate.py                 抓 RSS → 调模型 → 写数据 → 跑 build.py → 输出 public/
└─ README.md                   本文件

.github/workflows/daily.yml    每天 07:30（UTC 23:30）自动执行
```

---

## 一、准备两个东西

### 1. DeepSeek API Key（写稿用）

1. 打开 <https://platform.deepseek.com/>，用手机号或邮箱注册；
2. 登录后左侧「API keys」→「创建 API key」→ 复制 `sk-...`（只显示一次）；
3. 左侧「充值」→ 充 ¥10（支付宝/微信）。按量计费，一天一期大约几分钱到一毛钱。

### 2. GitHub 账号（跑任务 + 托管网页）

1. <https://github.com/signup> 注册（邮箱验证）；
2. 新建仓库：<https://github.com/new>，名字 `zixun`，选 **Public**（Public 的 Actions 不扣额度，Pages 也免费）。

---

## 二、把仓库跑起来（5 步）

1. **上传文件**：把 `资讯` 目录里的这些内容推到仓库根目录：
   `build.py`、`serve.py`、`数据/`、`资源/`、`站点/`、`推送/`、`云版/`、`.github/`、`.gitignore`
   （不要传 `工具/`，里面有 55MB 的 cloudflared。）

   命令行版：
   ```bash
   cd F:\DEEPSEEK\资讯
   git init
   git add .
   git commit -m "init"
   git branch -M main
   git remote add origin https://github.com/<你的用户名>/zixun.git
   git push -u origin main
   ```

2. **加 Key**：仓库 → Settings → Secrets and variables → Actions → New repository secret
   名称 `DEEPSEEK_API_KEY`，值粘贴 `sk-...`。

3. **开 Pages**：仓库 → Settings → Pages → Build and deployment → Source 选 **GitHub Actions**。

4. **手动跑一次**：仓库 → Actions → 左侧「资讯日报」→ Run workflow。

5. **拿地址**：跑完在 Actions 的 deploy 步骤里能看到 `https://<用户名>.github.io/zixun/`。

之后每天 07:30 自动更新，电脑关机也不影响。

---

## 三、它是怎么工作的

1. `generate.py` 抓 16 个国际 RSS（BBC、Guardian、Al Jazeera、DW、France 24、NPR、CNA、SCMP、Nikkei、Ars Technica、HN、Nature、Science、36Kr、中央社、联合早报），保留最近 40 小时、去重后取 50 条；
2. 把素材 + 上一期的「线索追踪」一起发给 DeepSeek，要求严格按 JSON 结构输出（全球扫描 6 区、8 个板块、3 篇深读、3 条信号、3 条与你有关、线索追踪）；
3. 写入 `数据/YYYY-MM-DD.json` → 跑 `build.py` → 生成 `站点/` → 复制到 `public/`；
4. Actions 把 `数据/`、`站点/`、`public/` 提交回仓库，并把 `public/` 发布到 Pages。

**失败兜底**：模型超时、返回坏 JSON、Key 失效，都会自动退化成「标题版」——只列当天最重要的原始报道和链接，仍会发布，页面不会空白。第二天成功后自动恢复完整版。

**不编数字**：云端不接行情源，所以 `numbers` 留空，模型被明确禁止编造指数点位。想要行情数字，下一步可以接 Stooq（免费 CSV），告诉我即可。

---

## 四、本地试跑（不花钱）

```powershell
cd F:\DEEPSEEK\资讯
python 云版\generate.py --dry-run
```

`--dry-run` 不调模型，只用 RSS 生成降级版，用来验证抓取和构建是否正常。生成结果在 `public\`。

---

## 五、成本与限制

| 项目 | 说明 |
| --- | --- |
| DeepSeek | 一期约 1.5 万 token，按当前价格不到 ¥0.1 |
| GitHub Actions | Public 仓库免费；单次运行约 1—2 分钟 |
| Pages | 免费，国内访问 `github.io` 可能偏慢，可再加 Cloudflare 或 jsDelivr |
| 时区 | 工作流用 UTC；`30 23 * * *` = 北京时间次日 07:30 |
| 失败重试 | 模型调用失败会重试一次，再失败走降级版 |

---

## 六、常见问题

**Q：Actions 显示成功，但页面还是旧的？**
Pages 部署有 1—2 分钟延迟；也可能是浏览器缓存，强制刷新。

**Q：`数据/` 里的历史会丢吗？**
不会，每次提交都保留。`build.py` 会把所有 `数据/*.json` 生成往期页。

**Q：想改成 08:00？**
改 `.github/workflows/daily.yml` 的 cron：`0 0 * * *` = 北京时间 08:00。

**Q：能推送到微信吗？**
可以另外加一步（Server 酱 / 企业微信机器人），给我 webhook 即可。
