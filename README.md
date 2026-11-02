# Schale Panel · 碧蓝档案风格 AstrBot 控制面板

把 AstrBot（QQ 机器人）的运行状态、群友关系、日程、商店、任务做成一块「夏莱办公室」的
游戏化面板。前端是 Vue 3 + PixiJS（Spine 立绘），后端是一个薄薄的 FastAPI 胶水层，
直接读 AstrBot 的数据目录，不修改它。

![license](https://img.shields.io/badge/license-MIT-blue)

## 它长什么样

| 页面 | 内容 |
|---|---|
| 大厅 | Spine 立绘、情绪气泡（贴图随情绪换）、顶部资源条、左侧四个功能入口、底部八格导航 |
| 桃信 | 所有人的对话记录，真实的 QQ 往来，能直接在面板里发消息（真的会发到 QQ） |
| 成员 | 人格卡列表 → 点进去是角色详情（人格设定 / 相处数据 / 内心读数） |
| 日程 | 学院地图，按地区看当天安排 |
| 商店 | 柜台场景，右侧是「商品」列表（模型、插件等占用） |
| 工作任务 | 任务看板，可增删改，和日历联动 |
| 编队 | 六个后台服务的一键启停（面板、AstrBot、NapCat、Ollama…），不用再开一堆黑窗口 |
| 资料 | 账号信息 / 玩家信息 / ID 卡，值日员、称号、问候语可改 |

## 快速开始

需要 Python 3.10+。Node.js 只在你要改前端源码时才需要（仓库里已带构建好的 `frontend/dist`）。

```bash
cd backend
pip install -r requirements.txt
cp config.example.json config.json     # 然后改里面的内容
python main.py                          # 默认 http://127.0.0.1:7870
```

Windows 用户直接双击根目录的 `start.bat`，它会启动后端并自动打开浏览器。

### config.json 要改什么

| 字段 | 说明 |
|---|---|
| `password` | 面板登录密码 |
| `jwt_secret` | 留空会自动生成（重启后面板会话失效，建议固定一个随机串） |
| `data_dir` | AstrBot 的 `data` 目录路径，例如 `D:/AstrBot/data` |
| `plugins` | 可选。你的插件数据目录名和这里的默认值不同时才需要填：`companion_dir` / `emotion_dir` / `billing_usage` / `comfy_config` |
| `owners` | 你自己的 QQ 号，用于把「主人」从群友里区分出来 |
| `onebot` | NapCat / OneBot 的 HTTP 地址与 token，只有「在面板里发消息」才需要 |
| `services` | 编队页要管理的进程清单，`cmd` 填启动命令，留空则不显示 |

## 前端开发

```bash
cd frontend
npm install
npm run dev        # 默认 5173，代理 /api 到 7870
npm run build      # 产物进 dist/
```

## 目录结构

```
backend/     FastAPI 胶水层：登录、聚合 AstrBot 数据、OneBot 发送、服务托管
frontend/
  src/       Vue 3 + TypeScript 源码
  public/    立绘、背景、图标、登录动画等静态资源
  dist/      已构建的产物（后端直接托管它）
start.bat    Windows 一键启动
start.sh     Linux / macOS 一键启动
```

## 和 AstrBot 的关系

面板**只读** AstrBot 的数据（`data/data_v4.db`、插件目录里的 json），唯一会写的是：

- `panel_*.json`：面板自己的偏好、任务、对话记录
- 发消息时写回 `companions.json` 里的「最后一句」，让机器人自己的记忆不脱节

它不会改 AstrBot 的人格卡，也不会覆盖插件配置。

## 素材来源与致谢

面板里的立绘、背景、图标、Spine 模型大量来自 **基沃托斯古书馆（https://kivo.wiki/）**。
没有它整理的游戏素材，这个项目做不出来。

游戏《碧蓝档案 / Blue Archive》的角色与美术版权归 NEXON Games 与 Yostar 所有。
本项目是非商业的同人工具，与官方无关。

## 隐私与数据

这个仓库里**不含任何个人信息**：

- 没有 QQ 号、群号、好友昵称、聊天记录
- 没有 token、密码、JWT 密钥（`config.example.json` 里全是 `CHANGE_ME` / `YOUR_ONEBOT_TOKEN` 占位）
- 没有日志、账本、`companions.json`、人格卡等运行期数据（`.gitignore` 已排除 `data/`、`logs/`、`backend/config.json`）
- 没有你的本机路径；代码里读的都是 `data_dir` 相对路径
- 面板的所有人物头像与立绘都来自游戏素材，不是真人照片

面板默认的角色名（`frontend/public/panel-config.json` 里的 `characterName`）只是示例，改成你自己的即可。

别人即使拿到这个仓库，也只能看到一套空壳程序——**没有你的 `config.json` 和 `data_dir`，它读不到任何人的数据**。

## License

MIT
