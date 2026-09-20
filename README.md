# lingpao · 零跑 C11 行程手记

完全自托管的里程与能耗记录工具：上传截图 → 本机 Tesseract OCR → 校验 → SQLite → 手机网页。
延续原页面的 C11 实车背景与统计内容，采用随系统切换的浅色 / 深色界面，以松绿色和暖金色区分能耗与里程。运行时不加载 CDN、在线字体、图表库或云端 OCR。

## 新版界面 · 2026.09.20.2

- **总览 / 能耗 / 记录**：手机使用底部导航，桌面使用顶部导航；上传入口始终可见。
- **自动外观**：默认跟随 iPhone 系统，即时切换且无需刷新。右上角“偏好与管理”可固定为浅色或深色，偏好仅保存在当前设备。
- **出行节奏**：日 / 周 / 月汇总；点按、触摸横向划动或键盘选择柱形查看具体值。参考虚线为当前汇总方式下已记录项目的简单平均，缺失日期不当作零；长历史仅绘制最近 120 项并显示提示。
- **出行日历**：按自然月独立浏览；虚线代表未记录，实心低亮色代表明确的零值，未来日期不可选。点按日期可打开详情。
- **能耗**：周趋势使用从零开始的纵轴，缺失周不连线；环图可切换周期、点选行车 / 空调 / 其他。构成电量由总电量与占比估算，标注“约”。
- **记录完整度**：统计范围只计算已经到来的日期。只有真实数据才计入天数，不将缺失样本包装成环比增长。
- **截图核对**：日期、里程、周期和百分比直接在表单中修改，支持添加 / 移除待合并行；JSON 编辑保留在高级选项。提交继续执行后端的数据保护规则。
- **连接反馈**：网络失败时保留本次会话中上次获取的数据并显示提示，可重试；不建立离线数据缓存。

外观通过浏览器的系统配色偏好实现，Safari 支持系统深浅色偏好。[WebKit 官方说明](https://webkit.org/blog/8840/dark-mode-support-in-webkit/)

## 快速开始

需要 Docker Compose v2、Python 3（仅初始化用）、OpenSSL。Windows 推荐在 WSL2 中执行。

```sh
cd leap-mileage
python3 scripts/setup.py
docker compose up -d --build
docker compose ps
```

打开 **https://localhost:8443/**。本地自签名证书会提示不受信任，仅本机测试可接受；iPhone 正式部署使用域名的受信任证书。
访问密钥在本机 `.env` 的 `API_TOKEN` 中，登录网页时填写。不要把 `.env`、证书、截图或数据库上传 GitHub。
较旧的 Compose 命令为 `docker-compose`，建议升级至 Compose v2。

应用初始数据库为空，不会自动导入示例。以下命令导入虚构示例；迁移旧页面时，请将来源换为你自己的 JSON 导出文件：

```sh
cp data.sample.json data/import.json
docker compose exec app python migrate.py /data/import.json --dry-run
docker compose exec app python migrate.py /data/import.json
```

data.sample.json 是虚构数据，仅用于验证数据格式，不包含个人历史记录。导入前自动备份；重复导入执行相同合并规则。
背景来自原项目，请确认你拥有公开发布素材的权利。新版应用图标为本项目的 SVG 矢量图形，并提供本地 PWA / iOS PNG 版本。

## 使用

1. 点击“上传截图”，选择截图的实际拍摄日期（北京时间）。旧截图不能使用今天的日期。
2. 上传完整的零跑 App「里程能耗」截图，建议与样例相同的页面布局。
3. 所有区域校验通过后自动入库；任一区域不确定时整张截图标为“待确认”，不会部分写入。
4. 在右上角“偏好与管理 → 截图与待确认记录”中对照原图修改表单，确认后合并。也可移除不确定的行，只保留确定的记录。移除待合并行不会删除历史数据。
5. 页面每分钟、回到前台时重新读取数据。新增版本会自动重新加载，打开核对窗口时推迟更新。

默认本月，可切换本周、上周、上月、全部、自定义，以及日 / 周 / 月汇总。周能耗展示与所选日期相交的完整周期，简单平均不代表按里程加权的整体能耗。
缺失日期不会被补成零，日均只按已记录日期计算。每日 0 km 只在截图确有零值图形证据时记录。

## 数据保护与识别边界

| 数据 | 合并方式 |
| --- | --- |
| 每日里程 | 同日期取最大值 |
| 周能耗 | 同周期取最大值；与旧值的绝对相对偏差 **大于 20%** 则拒绝，20% 本身允许 |
| 能耗构成 | 同周期只首次写入，后续保持原值 |

OCR 在原始图和 2 倍放大、增强对比度、锐化后的图上提取带坐标文字；中文日期行单独识别；按横坐标分七列，候选组合用总里程校验（5 km 或 5%）。缺失数字不能直接当零。
六个周柱值须在 1–50 范围；倾斜周期标签旋转后分别 OCR，要求六周连续，不根据最后选中周猜前五周。能耗百分比必须合计约 100%。跨年周期根据拍摄日期解析。

**OCR 是辅助录入，不是绝对正确的测量。** 20% 规则只保护已有周记录，不能验证首次出现的数据。日历直接显示每日公里数，点击日期可补录或修正（含调小、归零）；手动记录不会被后续 OCR 或 JSON 合并覆盖，请再次在日历中修改。手动保存会记录修改前后的审计日志；如果其他设备已修改同一天，保存会提示冲突，请刷新后重新核对。接口为鉴权的 PUT /api/daily/YYYY-MM-DD，提交 km 和 expected_km（新增为 null），不允许未来日期或超过 3000 km。当前没有绕过周能耗 20% 保护的网页按钮。换手机、字号、App 版本、滚动位置后可能转为待确认，需要新的样例完善解析。
已上传截图永久保存在 `data/screenshots/`；数据库保存识别摘要和审核日志，不保存大段原始 OCR 文本。

## API

除 `/api/health` 与 `/api/version` 外都需要 `Authorization: Bearer <API_TOKEN>` 或 `X-API-Key: <API_TOKEN>`。网页使用后者，以兼容可选 Basic Auth。
网页外壳可以公开读取，所有私人数据需要密钥。不启用跨域访问。

| 方法 / 路径 | 用途 |
| --- | --- |
| GET `/api/data` | `daily[]`、`weekly[]`、`energy[]` |
| POST `/api/upload` | multipart：`file`、`captured_date=YYYY-MM-DD`，日期必填 |
| GET `/api/screenshots` | 最近 30 张截图状态和识别结果 |
| GET `/api/screenshots/{id}/image` | 受保护的原图 |
| POST `/api/screenshots/{id}/confirm` | 用完整三数组 JSON 确认合并，仍执行保护规则 |
| POST `/api/admin/backup` | 创建一致性 SQLite 备份，尝试 WebDAV |
| GET `/api/admin/backups` | 备份列表 |
| GET `/api/admin/backups/{filename}` | 下载备份 |
| GET `/api/admin/logs` | 最近 100 条操作日志 |
| GET `/api/health` | 健康检查（含数据库可读性） |
| GET `/api/version` | BUILD 版本 |

本地测试（把占位内容改为 `.env` 密钥，生产域名不要使用 `-k`）：

```sh
curl -k https://localhost:8443/api/health
curl -k -H 'Authorization: Bearer YOUR_TOKEN' https://localhost:8443/api/data
curl -k -H 'Authorization: Bearer YOUR_TOKEN' \
  -F 'file=@screenshot.png' -F 'captured_date=2026-09-19' \
  https://localhost:8443/api/upload
curl -k -X POST -H 'Authorization: Bearer YOUR_TOKEN' \
  https://localhost:8443/api/admin/backup
```

上传串行执行，另一张正在识别时返回 409，稍后重试。nginx 限制每分钟 12 次上传，单文件不超过 15 MB；总像素限制 1600 万。413 表示过大，422 表示日期/图像不合法或识别失败。
返回 `status=review` 是待确认，不表示已经写入。重复截图可能产生多条审计记录，但每日/每周业务数据不会重复。

## 定时扫描与备份

单进程内置调度器替代 cron：每个北京时间整点后的 30 秒内扫描，03:00 后 30 秒内备份；重启后补执行当小时扫描、当天 03:00 后尚未做的备份。只运行一个 app worker / 副本。

将图片放到 `data/inbox/2026-09-19_任意名称.png`；日期是截图拍摄日期。先复制为 `.part`，完成后改成图片扩展名。跳过修改不足 60 秒的文件。
已处理原件移动至 `processed/`，错误文件移至 `failed/`；待确认结果也可在网页管理界面查看。重试时把失败文件更正日期文件名后放回 inbox。

每日备份用 SQLite Online Backup API，不直接复制正在写入的数据库；备份完整性检查成功后原子重命名。只清理 `data/backups/leap-*.db` 中超过 90 天的本地备份；截图、处理文件和安全恢复备份不会自动删除。
`leap.db-wal` / `leap.db-shm` 是 SQLite WAL 的正常运行文件：**运行时不得只复制 leap.db 当备份**。导出的备份才是可单独恢复的数据库文件。[SQLite 官方说明](https://www.sqlite.org/backup.html)

### WebDAV（可选）

先在坚果云 / Nextcloud 建好专用目录，编辑 `.env`：

```dotenv
WEBDAV_URL=https://your-server.example/remote.php/dav/files/your-user/leap
WEBDAV_USERNAME=your-user
WEBDAV_PASSWORD=your-app-password
```

URL 是已有文件夹；使用应用专用密码；仅支持有效证书的 HTTPS，不跟随重定向。然后 `docker compose up -d --force-recreate app`。
点击“立即备份”，检查返回 `webdav=ok`；失败仍保留本地备份并记录警告，修复配置后手动重试。远端不自动删除，请在远端配置生命周期规则。仅远传数据库，不包含截图；截图目录请额外使用 Synology Hyper Backup / USB 或自己的异地备份方案。

### 恢复演练

先确认网页无人上传，然后：

```sh
docker compose stop app
docker compose run --rm --no-deps app python restore.py \
  /data/backups/leap-实际文件名.db --confirm-app-stopped
docker compose up -d app
```

工具校验备份结构和完整性，先保存 `before-restore-*.db` 安全备份，再恢复。必须停 app，标记是你的停机确认，不会代你停止容器。原图不在数据库备份中；若整机迁移请一起还原 `data/screenshots/`。

## HTTPS 与群晖

详见 [DEPLOY.md](DEPLOY.md)。推荐：公网 HTTPS 8443 → DSM（证书）→ `127.0.0.1:5080` → nginx → app。
DSM 自身通常使用 5000 / 5001，所以本项目不占用 5000。**DSM 要用 8443 时，将容器 HTTPS_PORT 改为 9443**，避免同机监听冲突。
本地测试使用 https://localhost:8443；正式部署由 DSM 管理受信任证书和自动续期。也支持复制自己维护的证书到 `certs/fullchain.pem` / `privkey.pem` 后由容器终止 TLS，更新证书后 `docker compose exec nginx nginx -s reload`。

### 可选 Basic Auth

已有应用密钥保护全部数据，通常不需要额外 Basic Auth。若想连页面外壳也保护，用 `htpasswd -c certs/.htpasswd 你的用户名` 创建口令文件（Apache 工具提供 htpasswd），取消 nginx.conf 的两行 `auth_basic` 注释并重新加载 nginx。
网页在浏览器 Basic 登录后仍需输入应用密钥，以 `X-API-Key` 发送，两者不会冲突。外部 API / 快捷指令同时启用 Basic 时，Authorization 留给 Basic，应用密钥改用 `X-API-Key` 头。公开的健康检查不启用 Basic，仍不含私人数据。

## OCR 数字重识别（2026.09.20.9）

每日数字缺失或存在多个候选时，会对定位到的单列数字区域进行三次纯数字 OCR，
至少两次读数一致才作为候选，再通过日期和七天合计校验；不会用总数倒推缺失里程。
仍不明确时保持待核对，并提示具体日期。重识别读数保存在识别记录的 evidence 中。
原有“可见基线绿色点才补零”、总数容差、周能耗保护和手动里程保护保持有效。

回归测试不公开个人截图。设置 OCR_FIXTURE 为 9 月 19 日旧样例路径、
OCR_FIXTURE_SEP20 为 9 月 20 日新样例路径后运行 pytest，可验证完整识别、
重试不一致和总数不符时拒绝自动写入。未提供图片时，相应真图测试会跳过。

## iPhone 与快捷指令

### 添加到桌面

Safari 打开受信任的 HTTPS 域名 → 登录 → 分享 → 添加到主屏幕。希望长期登录可勾选“在此设备记住密钥”。设备清除网站数据或退出后重新输入。
不注册 service worker，不缓存离线数据。响应统一 `no-store`，API 请求显式 `cache: no-store`；BUILD 变化会用 `?v=版本` 重新导航。
`location.reload(true)` 的布尔参数属于 Firefox 特性，不能靠它保证 iOS 清缓存。[MDN](https://developer.mozilla.org/en-US/docs/Web/API/Location/reload)
旧平台的桌面图标仍指向旧地址，需要为新域名重新添加；更改旧平台域名缓存不在新服务控制范围内。

### 分享截图上传（建议先建立这个）

1. 新建快捷指令“零跑上传”，开启在共享表单中显示，接收图像。
2. 输入为所选截图。读取原照片“拍摄日期”，格式化为 `yyyy-MM-dd`、时区 Asia/Shanghai；若获取不到日期，添加“询问输入”让你填写，勿默认为上传日。
3. “获取 URL 内容”：`https://你的域名:8443/api/upload`，方法 POST。
4. 添加头 `Authorization`：`Bearer 你的API_TOKEN`。
5. 请求体选择“表单”，添加 **文件字段** `file`（图像）和 **文本字段** `captured_date`（日期）。不要手工写 `Content-Type`，让快捷指令生成 multipart boundary。
6. 读取返回 JSON 的 `status`。`done` / `done_with_warnings` 提示已合并；`review` 提示打开网页核对；HTTP 错误或其他状态提示失败。

### 每周日 23:00

先建立专用相册“零跑里程”。截图后将完整里程页加入相册。
快捷指令中“查找照片”：相册=零跑里程，按拍摄时间降序，限制 1；读取照片拍摄日期，传给上述上传动作。若当天没有新截图则停止并通知，不要把旧图按当天日期上传。
“自动化 → 特定时间 → 23:00 → 每周日 → 运行此快捷指令”，按 iOS 提供的选项设为立即运行。首次手动执行授予照片和网络权限。
手机锁定、照片权限、网络和 iOS 版本可能影响执行，应检查返回状态。[Apple 自动化说明](https://support.apple.com/guide/shortcuts/add-automations-apdfbdbd7123/ios)
这只自动上传已有截图，不会自动打开零跑 App、导航并截图；本项目不接入零跑账号或车辆云接口。

## 本地开发与验证

```sh
python3.11 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
# macOS: brew install tesseract tesseract-lang
# Debian: apt install tesseract-ocr tesseract-ocr-chi-sim tesseract-ocr-eng
.venv/bin/python -m pytest -q
# 真图回归（截图不纳入公开仓库）：
OCR_FIXTURE='/绝对路径/截屏 2026-09-19 18.46.20.png' .venv/bin/python -m pytest -q
```

截图回归按提供的 2026-09-19 样例断言：每日 `[42,73,73,75,77,73,0]`，合计 413 km；周能耗 `[16.7,17.6,14.2,13.6,13.8,13.7]`；周期总电量 68.1 kWh。
无 Docker 调试可加载 `.env` 后运行 `uvicorn app.main:app --host 127.0.0.1 --port 8000`。生产始终从 nginx/DSM 访问，不公开 app 端口。

## 十年维护

“十年可用”依靠可迁移的数据和定期维护，而不是十年不升级。SQLite 数据无云服务锁定；可随时导出 JSON、恢复到新机器。
100 天结构化数据很小，但日志、重复上传记录、索引、截图会长期增长，不能保证十年数据库一直小于 1 MB。至少每季度检查备份和做一次恢复演练；每年评估 Docker/Python/Tesseract 安全更新与磁盘空间。
Python 3.11 与当前基础镜像在十年内会结束支持，届时需升级运行时并跑回归测试。
构建期需要 Docker 镜像仓库、Debian 软件源和 PyPI；运行期无需它们。离线长期部署请保存 **amd64 镜像**（DS720+ 使用 Intel），以及源代码、配置和数据备份。证书到期要续期。

更新：先手动备份 → 更新代码 → 更改 `.env` 中 BUILD → `docker compose up -d --build` → 检查健康状态与上传。不要删除 `data/`。上传 GitHub 前检查 `.gitignore`；不要使用强制添加忽略文件。
