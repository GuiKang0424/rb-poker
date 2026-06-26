# CLAUDE.md

本文件为 Claude Code 在本仓库工作时提供项目上下文与约定。

## 项目概述

Web 端多人德州扑克游戏（无限注），最多支持 10 人同桌、真人 + 5 种风格规则型 AI、单进程多房间。详细规划见 [项目计划.md](./项目计划.md)。

## 技术栈

**后端**：Python 3.9+ / FastAPI / 原生 WebSocket / SQLAlchemy 2.0 + aiosqlite / deuces 手牌评估 / bcrypt / python-jose (JWT)
**前端**：React 18 + TypeScript + Vite + Tailwind CSS v4

## 目录结构

```
dzpk/
├── 项目计划.md              # 完整规划与里程碑
├── backend/                  # 后端 FastAPI
│   ├── app/
│   │   ├── main.py          # FastAPI 入口；HTTP /rooms + WebSocket /ws/{room_id}（等待区/准备/开始游戏/展示阶段）
│   │   ├── api/
│   │   │   ├── websocket.py # ConnectionManager 广播 + 客户端动作解析 + WS 认证状态
│   │   │   └── auth.py      # 认证 API（guest/upgrade/login/me）+ JWT 工具函数
│   │   ├── game/
│   │   │   ├── deck.py          # Card / Deck + Fisher-Yates 洗牌
│   │   │   ├── evaluator.py     # deuces 封装：手牌强度评估与比较
│   │   │   ├── player.py        # Player + PlayerStatus + is_ready/is_owner
│   │   │   ├── poker.py         # Action / BettingRound / 动作合法性 / Side Pot
│   │   │   ├── showdown.py      # 主池/边池筹码分配
│   │   │   ├── state_machine.py # GameStage / TableState（核心状态机）+ enter_reveal_phase/apply_reveal_choice/compute_hand_result
│   │   │   └── room.py          # RoomManager + WaitingPlayer + reveal_pending/reveal_choices/uncontested
│   │   ├── schemas/
│   │   │   ├── game.py   # Pydantic 请求/响应（房间）
│   │   │   └── auth.py   # Pydantic 认证 Schema
│   │   └── db/
│   │       ├── __init__.py
│   │       ├── session.py  # AsyncSession + init_db
│   │       └── models.py   # User + HandHistory SQLAlchemy 模型
│   ├── tests/               # pytest 单元测试
│   ├── requirements.txt
│   └── pytest.ini
├── frontend/                 # 前端（里程碑 2 完成）
│   ├── src/
│   │   ├── main.tsx          # React 入口
│   │   ├── App.tsx           # 页面路由（Lobby / GameTable）
│   │   ├── types/
│   │   │   ├── game.ts     # 游戏协议类型定义（GameStage/RevealPhase/HandResult）
│   │   │   └── auth.ts     # 认证类型定义（UserInfo/AuthState）
│   │   ├── hooks/
│   │   │   ├── useWebSocket.ts  # WebSocket Hook（含自动重连 + auth 消息）
│   │   │   └── useAuth.ts      # 认证 Hook（initGuest/login/upgrade/logout）
│   │   ├── context/GameContext.tsx # 全局状态管理（useReducer）+ 集成 auth userId
│   │   ├── components/
│   │   │   ├── Card.tsx      # 扑克牌组件（支持 small prop）
│   │   │   ├── PlayerSeat.tsx # 玩家座位（昵称/筹码/底牌）
│   │   │   ├── ActionBar.tsx  # 操作按钮栏（Fold/Check/Call/Bet/Raise/All-in）
│   │   │   ├── GameTable.tsx  # 游戏桌（椭圆牌桌+公共牌+底池+等待区面板+准备入座+展示阶段UI+下一局按钮+聊天面板）
│   │   │   ├── Lobby.tsx      # 大厅（创建/加入房间、房间列表 + 用户信息栏 + 登录入口）
│   │   │   ├── Login.tsx      # 登录/注册弹窗组件
│   │   │   ├── UserProfile.tsx # 用户信息展示（头像/昵称/筹码/注册入口）
│   │   │   └── ChatPanel/     # 聊天面板组件
│   │   │       ├── ChatPanel.tsx    # 主面板（可折叠/展开、自动滚底、新消息红点）
│   │   │       ├── ChatMessage.tsx  # 消息卡片（text/quick/system 三种样式）
│   │   │       ├── ChatInput.tsx    # 输入框 + 发送按钮
│   │   │       └── QuickPhrases.tsx # 8 个快捷短语按钮（4×2 网格）
│   │   └── utils/card.ts     # 牌面解析工具
│   ├── vite.config.ts        # Vite 配置（host:0.0.0.0 + /api 代理到 :8000）
│   └── package.json
```

## 常用命令

后端开发与测试均在 `backend/` 目录下执行。

```bash
# 安装依赖
cd backend && pip install -r requirements.txt

# 运行单元测试（应全部通过）
python -m pytest -v

# 启动开发服务（默认 8000 端口，监听所有网卡以支持内网访问）
python -m uvicorn app.main:app --reload --host 0.0.0.0
```

前端开发在 `frontend/` 目录下执行。

```bash
# 安装依赖
cd frontend && npm install

# 启动开发服务（默认 5173 端口，代理到 8000）
npm run dev

# 生产构建
npm run build
```

开发环境访问：
- 前端页面：`http://localhost:5173`
- 后端健康检查：`GET http://localhost:8000/health`
- 后端 API 文档：`http://localhost:8000/docs`

## 核心设计约定

1. **后端权威**：所有游戏逻辑、合法性判定、状态计算均在后端执行；前端仅渲染。任何前端动作通过 `state_machine.TableState.submit_action` 入队，由 `validate_and_apply_action` 校验后才生效（见 `app/game/poker.py`）。
2. **事件驱动通信**：后端通过 `TableState._emit(event, data)` 推送事件到 WebSocket 广播。事件协议见 `项目计划.md` 第 190 行起的 S2C/C2S 列表。
3. **状态机分阶段**：`GameStage` 枚举 Waiting → Preflop → Flop → Turn → River → **RevealWait** → Showdown → HandEnd。`start_hand()` 是一手牌的入口，返回 `"uncontested"` 或 `"showdown"` 表示进入展示阶段。
4. **类型安全**：所有 game 模块文件头部使用 `from __future__ import annotations`，确保 Python 3.9 也能使用 `int | None` 类风格注解。FastAPI 路由签名中的 runtime 注解需保持 3.9 兼容。
5. **Fisher-Yates 洗牌**：默认使用 `secrets.SystemRandom`（加密安全）；测试可传 `seed` 复现。
6. **Side Pot 算法**：按"投入金额分层"计算（`poker.py::compute_side_pots`）。弃牌玩家筹码计入池中但不参与争夺。短 All-in（不足最小加注）不重新打开下注轮。
7. **筹码分配**：平局均分；除不尽的余数（odd chip）按惯例给 button 左手第一个赢家（`showdown.py::distribute_pots`）。
8. **等待区机制**：玩家加入房间先进入等待区（`Room.waiting`），点击"准备"后系统自动分配最小可用座位并入座。房主创建房间自动入座座位0+自动准备。取消准备踢回等待区并释放座位。
9. **游戏开始流程**：房主点击"开始游戏"→后端校验（入座≥2人、全部已准备、非游戏中）→ 所有入座者状态设为 ACTIVE → `start_hand()`。牌局结束后所有人 is_ready=False、阶段回到 WAITING，筹码<100 者踢回等待区。
10. **WebSocket 动作**：`ready`/`unready`/`start_game` 由 `main.py` 直接处理（不入状态机队列）；游戏动作 `fold`/`check`/`call`/`bet`/`raise`/`all_in` 通过 `submit_action` 入队由状态机处理。
11. **手牌展示阶段**：牌局结束（不战而胜或摊牌）后进入 `REVEAL_WAIT` 阶段。所有有手牌的玩家（包括已弃牌的）必须选择"展示"或"不展示"。选择"不展示"的未弃牌玩家视为弃牌，不参与结算。所有人选择完毕后通过 `compute_hand_result()` 计算结果并发送 `showdown_result` 事件。

## 开发原则

- **不要在前端实现游戏逻辑**——任何规则判断必须在后端。
- **不要相信前端任何数据**——动作合法性由 `validate_and_apply_action` 守卫。
- **修改核心规则必须补/改单元测试**——见 `tests/test_poker.py`、`test_showdown.py`、`test_state_machine.py`。
- **按里程碑迭代**——当前已完成里程碑 1（后端核心）+ 里程碑 2（前端基础）。正在进行里程碑 3（联调）。

## 关键 WebSocket 事件（S2C）

| 事件名 | 说明 | 数据 |
|--------|------|------|
| `auth_success` | WS 认证成功 | `{userId, username, chips, isAnonymous}` |
| `auth_failed` | WS 认证失败（随后关闭连接） | `{reason: "invalid_token" \| "user_not_found"}` |
| `reveal_phase_start` | 进入手牌展示阶段 | `{pendingPlayers: number[], uncontested: boolean}` |
| `player_revealed` | 玩家做出展示选择 | `{seat: number, revealed: boolean, cards?: string[]}` |
| `showdown_result` | 展示阶段结束，显示结果 | `{winners: number[][], pots: number[], showdown: boolean, revealedHands: Record<string, string[]>}` |
| `hand_end` | 牌局结束（旧事件，保留兼容） | `{winners: number[][], pots: number[], showdown: boolean, revealed?: Record<string, string[]>}` |
| `chat_message` | 聊天消息（文本/快捷/系统） | `{seat, userId, nickname, type, content, timestamp}` |
| `chat_history` | 聊天历史（新玩家加入时补发） | `{messages: ChatMessage[]}` |

## 关键 WebSocket 动作（C2S）

| 动作名 | 说明 | 数据 |
|--------|------|------|
| `auth` | WS 认证（连接后首条消息） | `{token: string}` |
| `reveal_choice` | 展示阶段选择 | `{choice: boolean}`（true=展示, false=不展示） |
| `ready` | 准备下一局（复用现有机制） | `{chips?: number}` |
| `chat` | 发送聊天消息 | `{type: "text"\|"quick", content?: string, phrase_id?: number}` |

## 当前进度

- ✅ **里程碑 1（后端核心）**：31 个单元测试全部通过，FastAPI 服务可启动。
- ✅ **里程碑 2（前端基础）**：React 18 + TypeScript + Vite + Tailwind CSS v4 项目搭建完成，WebSocket 联调通过。支持创建/加入房间、椭圆牌桌渲染、玩家操作（Fold/Check/Call/Bet/Raise/All-in）、公共牌与底池展示。前后端构建均通过。
- ⏳ **里程碑 3（联调完善）**：进行中。已完成：
  - 等待区+准备入座+房主开始游戏
  - 内网访问兼容修复（host:0.0.0.0 + WS 直连 + UUID fallback）
  - 手牌展示阶段（`REVEAL_WAIT`）：所有玩家可选择展示或不展示手牌
  - 下一局流程：复用 `isReady` 机制
  - 已弃牌玩家也可展示手牌（不参与结算）
  - 不战而胜时也可选择展示手牌
  - **用户系统**：匿名账号+正式账号、JWT 认证、筹码全局持久化、登录/注册 UI
  - **牌局聊天室**：文本消息+快捷短语（8条）+系统消息（12类事件自动广播）、内存缓存最近100条、可折叠聊天面板
  - 待完成：前端动画、断线重连提示、牌局历史展示。
- ⏳ 里程碑 4（AI）：待开始。
- ⏳ 里程碑 5（多房间体验）：待开始。

## 用户系统

- **匿名+正式账号混合体系**：新用户自动创建匿名账号（`POST /api/auth/guest`），可升级为用户名密码正式账号（`POST /api/auth/upgrade`）
- **JWT 认证**：HS256 算法，30 天有效期，`JWT_SECRET_KEY` 从环境变量读取（开发默认 fallback）
- **WebSocket 认证**：连接后首条消息发送 `{action: "auth", data: {token}}`，认证失败直接关闭连接
- **筹码全局化**：注册赠送 10000 筹码，入座时校验不能超过账号余额，每手牌结束后立即写入 SQLite
- **密码加密**：bcrypt（cost factor=12）哈希存储
- **一期不实现**：邮箱验证、密码找回、排行榜、好友系统

## 牌局聊天室

- **消息类型**：文本（`text`）、快捷短语（`quick`）、系统消息（`system`）
- **快捷短语**：8 条固定预设，前端硬编码，C2S 只传 `phrase_id`（0-7），后端透传广播
- **系统消息**：12 类事件自动广播（加入/离开房间、入座/离座、Fold/Check/Call/Bet/Raise/All-in、游戏开始/牌局结束）
- **消息持久化**：内存 `deque` 缓存最近 100 条（`ChatHistory` 类），不写 DB；新玩家加入时补发 `chat_history`
- **消息过滤**：不做限频、不做敏感词过滤、不做长度限制；前端 React 自动 escape 防 XSS
- **ChatPanel UI**：牌桌右侧可折叠面板，区分 text/quick/system 三种消息样式，新消息自动滚底，折叠时有红点提示

## 已知约束

- 暂不实现：房间密码、超时自动弃牌、可验证公平性、锦标赛、分布式部署、ML AI（详见 `项目计划.md` "不做" 列表）。
