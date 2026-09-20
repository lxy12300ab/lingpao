# DS720+ 群晖部署指南

下面是逐屏字段说明，不是假造的 DSM 截图。尚未连接你的 NAS，DSM 实际界面名称可能随版本/语言不同；请按字段含义对应。[Synology 官方路径参考](https://kb.synology.com/DSM/tutorial/Quick_Start_Synology_SSO)

## 1. 上传项目

套件中心安装 Container Manager（旧版名为 Docker）。控制面板 → 终端机和 SNMP → 启用 SSH。
上传源代码到 `/volume1/docker/leap/`，目录中直接包含 Dockerfile、docker-compose.yml、app/ 等文件。
不要上传 Mac 的 `.venv/`，也不要把 Mac 的 UID/GID、测试密钥当成 NAS 正式配置。

```sh
ssh 你的用户@NAS地址
cd /volume1/docker/leap
id -u
id -g
python3 scripts/setup.py
```

若 NAS 无 Python/OpenSSL：复制 `.env.example` 为 `.env`，填入至少 24 位随机密钥，将 UID/GID 填成上面查出的值，创建 data/、certs/ 并放入证书；也可在电脑初始化后传 `.env` 和证书，再纠正 UID/GID。不要复用文档示例密钥。
项目 data/ 应归该 UID/GID 所有，并允许容器读写；遇到 Permission denied 时纠正该目录的属主，不要对整个 volume1 递归修改权限。

## 2. 选择证书与端口模式

### A：DSM 管理 HTTPS（推荐）

编辑 `.env`：

```dotenv
BIND_IP=127.0.0.1
HTTP_PORT=5080
HTTPS_BIND_IP=127.0.0.1
HTTPS_PORT=9443
```

这里 9443 仅是容器备用 TLS 本地端口，公网访问走 DSM 的 8443。
`scripts/setup.py` 生成的本地证书留在 certs/，nginx 启动需要它；它不用于公网客户端。
DSM 的受信任证书在下一步绑定公网反代服务。无需复制 DSM 内部证书私钥到项目。

### B：nginx 容器直接 HTTPS

没有 DSM 反代时，可以 `HTTPS_BIND_IP=0.0.0.0`、`HTTPS_PORT=8443`。
把有效的域名证书链放到 `certs/fullchain.pem`，私钥放到 `certs/privkey.pem`。限制目录权限，证书/私钥必须匹配；路由器把公网 8443 转发到 NAS 8443。
证书可以从 DSM 导出后拼好完整链，或使用你维护的 ACME 客户端申请 Let's Encrypt 证书。当前两容器项目不包含 ACME 客户端，**直接模式不会自动续期证书**；续期后替换文件并 reload nginx。
不要同时让 DSM 与容器监听相同地址的 8443。

## 3. 启动

```sh
docker compose up -d --build
docker compose ps
docker compose logs --tail=80 app nginx
curl http://127.0.0.1:5080/api/health
```

预期两个容器 healthy，健康检查返回 `status=ok`。群晖账号如无 Docker 权限，按本机管理方式使用 sudo。
首次构建下载 Python、Tesseract 中文模型等，需要网络。若镜像拉取超时，先检查 NAS DNS、代理与 Docker Hub 连通性；不要随意把未知镜像源当可信仓库。

如果在 Mac 预构建镜像带到 NAS，要构建 linux/amd64（Apple Silicon 本地默认为 arm64）：

```sh
docker buildx build --platform linux/amd64 -t leap-mileage:local --load .
docker pull --platform linux/amd64 nginx:1.28-alpine
docker save -o leap-images-amd64.tar leap-mileage:local nginx:1.28-alpine
# 把 tar 上传 NAS 后：
docker load -i leap-images-amd64.tar
docker compose up -d --no-build --pull never
```

用 `docker image inspect` 确认保存的镜像架构为 amd64。保存镜像能避免未来软件仓库变化，但不替代安全升级。

## 4. DSM 反向代理配置（模式 A）

控制面板 → 登录门户 → 高级 → 反向代理 → 新增。

| 窗口 / 字段 | 填写值 |
| --- | --- |
| 名称 | Leap-C11 |
| 来源协议 | HTTPS |
| 来源主机名 | 你的外网域名，不含 `https://` 或端口 |
| 来源端口 | 8443 |
| 目的地协议 | HTTP |
| 目的地主机名 | 127.0.0.1 |
| 目的地端口 | 5080 |
| 高级超时 | 发送/读取超时如可设，填 180 秒 |

若界面有自定义请求头配置，确保 `Host` 保留原始域名与端口（nginx 变量 `$http_host`），避免 Origin 同源校验失败。
初次配置不要开启额外网页缓存。App 不需要 WebSocket。

控制面板 → 安全性 → 证书：添加或申请域名的有效证书，在“设置 / 配置”中把 **Leap-C11 对应的反代服务**分配给该证书。
Let's Encrypt 的申请/自动续期依赖域名解析、验证方式和外网连通性；按 DSM 实际提示完成。确认 Safari 看到证书域名匹配。

```text
iPhone https://你的域名:8443
            │ 受信任的域名证书
            ▼
       DSM HTTPS :8443
            │ HTTP，NAS 回环地址
            ▼
   127.0.0.1:5080 → nginx :80 → app :8000 → /data/leap.db
```

## 5. 路由器 / 防火墙

外网域名解析到你可达的公网地址。路由器 TCP 8443 转发到 NAS 8443（你已有域名+端口方案时沿用对应映射）。
DSM 防火墙仅开放实际需要的访问端口；5080 保持回环绑定，无需开放外网。不要把 app 8000、DSM 管理端口因为本项目再暴露出去。
如果使用 IPv6，确认 IPv6 的防火墙规则与 DNS 一致，不要只验证 IPv4。

手机关闭 Wi-Fi，用蜂窝网络访问 `https://你的域名:8443/`，登录后上传截图。

## 6. 历史迁移与 iPhone

按 README 的 migrate 命令导入旧 JSON，刷新页面。点击管理 → 立即备份，下载一份到电脑。
Safari → 分享 → 添加到主屏幕。旧 WorkBuddy 图标需要替换为这个新域名的图标。
每次发布改 BUILD；验证手机从后台返回后数据更新。运行时无 CDN，但浏览器证书、域名与旧图标仍需正确。

## 7. 逐项验收

- [ ] 两个容器健康，无重复重启。
- [ ] HTTPS 域名证书有效，蜂窝网络可访问。
- [ ] 未携带密钥访问 `/api/data` 返回 401。
- [ ] 导入历史数据后总里程符合原数据。
- [ ] 上传样例截图，7 个每日数字合计 413 km，6 个周期与图中一致。
- [ ] 重复上传后不产生重复日期，较小日里程不覆盖较大值。
- [ ] 周数据超过 20% 偏差被拦截，日志可见。
- [ ] 手动备份可下载；隔日查看 03:00 自动备份。
- [ ] WebDAV 启用时检查远端文件及日志 `webdav=ok`。
- [ ] 在独立目录做恢复演练，验证数据和截图引用。
- [ ] 更新 BUILD 后 PWA 回到前台能更新版本，无刷新循环。

## 8. 排查

| 现象 | 检查 |
| --- | --- |
| 502 | app 是否 healthy；目的地应是 HTTP 5080，不能把 HTTP 指向 TLS 端口 |
| 8443 被占用 | 模式 A 把容器 HTTPS_PORT 改成 9443 |
| app 退出 | API_TOKEN 是否占位/过短；data/ UID/GID；日志 |
| nginx 退出 | fullchain.pem 与 privkey.pem 是否存在、匹配、可读 |
| 401 | API_TOKEN、Bearer 前缀、旧设备保存的密钥 |
| 403 | DSM 是否保留 Host 及端口，与浏览器 Origin 一致 |
| 413 / 429 / 409 | 图片太大 / 请求太密 / 正在识别另一张 |
| 待确认 | 图像布局不同、日期不符、OCR 数字/周期不全；网页核对 |
| WebDAV failed | HTTPS 证书、已存在的目录、应用密码、PUT 权限；不跟随重定向 |
| PWA 仍旧版本 | 是否仍是旧平台图标；BUILD 是否更新；反代未额外缓存 |

本指南提供可执行配置；NAS、路由器、证书、iPhone 真机操作需在你的设备上完成，没有声称已远程配置。
