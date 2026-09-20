# 本地验证记录

## UI v2 · 2026-09-20

新版界面 BUILD 为 2026.09.20.2。Chromium 与 Playwright WebKit（Safari 同源引擎，非 iPhone 真机）均通过以下交互检查：

- 系统浅色 / 深色实时切换；固定浅色后重载保留；恢复跟随系统。
- 自定义日期、无效日期拦截、日 / 周 / 月汇总，以及图表点按与键盘查看。
- 明确的 0 km 和缺失日期分别展示；原样例 09/13–09/19 汇总仍为 413 km。
- 周曲线点选、构成周期选择和环图分类点选。
- 320 / 390 / 768 px 三种宽度、三个主页面没有页面横向溢出。
- 手机上传预览、表单修改与确认反馈；写入请求使用模拟响应，没有把测试数据写入真实数据库。
- 连接失败提示、保留已获取数据与重试恢复；版本变化重新导航。
- 无 JavaScript 异常，无 CDN 或其他站外资源请求。

视觉截图保存在 test-results/ 下，以 chromium- / webkit- 开头，包含桌面、手机、能耗及上传的深浅色版本。含个人里程数据，不纳入源码压缩包。

复测新版交互（需要当前本地已导入的样例记录；日期断言基于本次样例）：

```sh
.venv/bin/python scripts/browser_check.py
# Safari 引擎：
.venv/bin/python -m playwright install webkit
BROWSER=webkit .venv/bin/python scripts/browser_check.py
```

## 初版后端与部署验证

验证日期：2026-09-19（北京时间）。使用用户提供的原始截图和静态范例数据；未连接 NAS、WebDAV 或 iPhone 真机。

## 已完成

- Docker Compose 两服务完成构建和启动，app / nginx 健康检查通过。
- 容器运行 Python 3.11.16，Tesseract chi_sim + eng；本机为 macOS Apple Silicon，镜像架构 arm64。DS720+ 的 amd64 构建/运行需在 NAS 验收。
- nginx 配置检查通过；本地 HTTPS `https://localhost:8443/` 可访问，使用自签名证书进行测试。
- 通过 HTTPS 上传真实 PNG → 容器 OCR → SQLite 自动合并 → API 返回数据，全链路成功。
- 每日识别：2026-09-13 至 2026-09-19，42 / 73 / 73 / 75 / 77 / 73 / 0，合计 413 km。
- 周能耗识别：16.7 / 17.6 / 14.2 / 13.6 / 13.8 / 13.7；周期为 2026/08/03–08/09 起至 09/07–09/13。
- 能耗构成：68.1 kWh，行车 85.61%、空调 6.02%、其他 8.37%。
- 原 JSON 的 `last_update` 元数据兼容处理，历史数据实际导入成功。合并样例图后共 21 个每日记录、8 个周记录、3 个构成记录。
- 22 项自动测试在 macOS Python 3.14 和 Docker Python 3.11 中均通过，包含真实截图回归、每日 max、20% 边界/越界、追加规则、并发 max、无效数据、事务回滚、鉴权、审核确认、备份完整性/90 天清理、WebDAV 模拟成功/失败、定时补跑、inbox 及迁移/恢复演练。测试客户端库有两条弃用提示，不影响当前验证。
- 100 天结构化数据的备份小于 1 MB；HTTPS 实际备份为 45,056 字节（随着日志和上传会增长）。
- Chromium 桌面 1440px 与手机视口 390px：登录、日期筛选、日/月视图、管理列表、上传窗口、版本变化导航已检查，无 JS 错误、无页面横向溢出。
- 页面/接口响应包含 no-store。版本导航检查通过；未把这项等同于 iOS 真机缓存测试。

本地视觉检查图片位于 `test-results/desktop.png`、`mobile.png`、`upload-mobile.png`，含私人历史数据，不纳入源码包。

## 部署后仍需实测

- DS720+ 的 amd64 镜像构建、目录权限、运行资源占用。
- DSM 域名证书、外网端口、防火墙和蜂窝网络。
- iPhone Safari / 主屏幕 PWA、快捷指令权限及锁屏定时执行。
- 真实 WebDAV 账号与远端恢复（本地测试使用模拟客户端）。
- 未来零跑 App 不同布局/字号的 OCR。当前准确性来自这张样例，不代表所有截图都能自动识别。

## 复测

```sh
.venv/bin/python -m pytest -q
OCR_FIXTURE='/截图完整路径.png' .venv/bin/python -m pytest -q
.venv/bin/python scripts/smoke.py '/截图完整路径.png'
# 浏览器验证另需安装 playwright 和本机 Chrome：
.venv/bin/python scripts/browser_check.py
```

smoke.py 会向运行中的本地库上传该样例并创建备份；不要使用任意截图替代固定日期的测试样例。browser_check.py 的 413 km 断言同样以该样例数据为前提。
