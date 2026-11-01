# 校园集市 · Capstone 报告素材

> 使用说明：以下内容可直接摘入课程报告，请按学校模板调整章节编号、字体与图表编号。涉及外部研究、统计数据或文献对比的段落已标注 `[建议补充引用]`，提交前请用 UWE Harvard 或课程指定格式补充真实来源。测试数据来自本项目实际运行结果，未做虚构。

---

## 1. 中文摘要

针对校园二手交易中信息刷屏、分类混乱、已售商品仍被反复询问等问题，本文设计并实现了一个仅面向本校学生的二手闲置网站「校园集市」。系统采用 Flask + SQLite + Jinja2 的服务端渲染架构，提供注册登录、商品发布、七类分类浏览、关键词搜索、价格与热度排序、收藏和浏览记录等功能。核心机制是发布者可实时切换「在售 / 已售 / 暂停出售」三种状态：已售商品保留记录但灰化并隐藏联系方式，暂停商品从公开列表下架，从源头减少无效咨询。系统同时提供管理员后台，支持下架与恢复商品、分类维护、举报处理和全站统计，并实现中英文双语界面。通过 85 个自动化测试以及桌面端与移动端视觉检查，验证了认证、权限、图片上传、状态流转、软删除、搜索分页和双语等关键行为。结果表明，该方案能够以较低实现成本提升校园闲置信息的准确性与流通效率，适合作为课程项目与轻量校园应用的参考实现。

**关键词**：校园二手交易；Flask；SQLite；商品状态；双语界面；Web 应用

## 2. English Abstract

This paper presents Campus Market, a campus-only second-hand marketplace designed to address the chaotic information, unclear categories, and stale listings common in student group chats. The system is implemented with Flask, SQLite, and server-rendered Jinja2 templates, requiring no front-end build step or external services. Students can register, post items with multiple images, browse seven campus-oriented categories, search and sort listings, save favourites, and review browsing history. Its central mechanism is a real-time status model: sellers switch listings between on sale, sold, and paused. Sold items remain visible but are greyed out with contact details hidden, while paused items disappear from public listings, reducing invalid enquiries. An admin dashboard supports listing moderation, category management, report handling, and site-wide statistics. The interface is bilingual in Chinese and English. The implementation is validated by 85 automated tests and desktop/mobile visual checks covering authentication, permissions, uploads, status transitions, soft deletion, search, pagination, and localisation. The results suggest that a lightweight, status-aware campus marketplace can improve information accuracy and circulation efficiency at low implementation cost.

**Keywords**: campus marketplace; second-hand trading; Flask; SQLite; item status; bilingual web application

## 3. 背景与问题

校园二手交易长期依赖微信群、QQ 群和朋友圈。其优势是门槛低、传播快，但随着信息量增加，问题逐渐明显：

1. **信息刷屏**：同一件商品被反复转发，真正的新信息被淹没。
2. **状态失真**：商品已经卖出，但帖子仍留在群里，买家反复询问，卖家反复解释。
3. **分类缺失**：教材、电子产品、生活用品混在一起，只能靠关键词碰运气。
4. **交易对象不透明**：群成员来源复杂，难以确认是否为校内学生。
5. **价格与成色不统一**：缺少固定字段，描述质量参差。
6. **记录不可追溯**：成交后帖子被删除，历史信息消失，纠纷难以复盘。

本项目的切入点不是做一个「更大的二手平台」，而是把校园群里最痛的一个问题——**商品状态不准确**——变成系统的一等公民。通过发布者手动切换状态、系统强制执行可见性与联系方式规则，让「看到的信息就是当前真实情况」。

## 4. 目标与范围

### 4.1 项目目标

- 提供仅面向本校学生的轻量二手发布与浏览平台。
- 用固定字段（分类、价格、成色、地点、状态）规范商品信息。
- 用「在售 / 已售 / 暂停」状态机制减少无效咨询。
- 提供发布、编辑、删除、收藏、浏览记录、个人资料等完整闭环。
- 提供管理员审核、分类维护、举报处理和全站统计。
- 实现中英文双语，覆盖系统文案、校验提示和后台。
- 保持技术栈轻量：本地可运行、无外部依赖、便于课程演示。

### 4.2 非目标

- 不做站内即时聊天、订单、支付或担保交易。
- 不接入学校统一身份认证（SSO）；学号仅作为自填账号。
- 不做邮箱 / 短信验证、找回密码。
- 不做多校区、多租户隔离。
- 不做移动 App 或小程序。
- 不做推荐算法、图片 CDN、对象存储。
- 不做管理员用户封禁；v1 只管理商品、分类和举报。

### 4.3 成功标准

- 新用户能在 1 分钟内完成一次发布。
- 已售 / 暂停商品在列表和详情中有明确区分，已售商品无法显示联系方式。
- 中英文切换覆盖所有系统文案，切换后停留在当前页面。
- 管理员能独立完成下架、恢复、分类维护和举报处理。
- Windows 上按 README 步骤可启动，数据落在本地 SQLite。

## 5. 场景对比

| 维度 | 校园二手群 | 通用二手平台 | 本系统 |
|---|---|---|---|
| 发布门槛 | 低 | 中 | 低 |
| 分类 | 基本没有 | 丰富但泛化 | 7 个校园高频类 |
| 状态准确性 | 依赖卖家自觉 | 有，但流程重 | 一键切换，规则强制 |
| 交易对象 | 群成员，来源复杂 | 社会用户 | 设计目标为校内学生 |
| 已售信息 | 仍被转发 | 下架或归档 | 保留、灰化、隐藏联系方式 |
| 轻量程度 | 极高 | 低 | 高（无构建、无外部服务） |
| 课程可讲解性 | — | 复杂 | 高（SQL、权限、状态机清晰） |

`[建议补充引用]` 可在此处补充校园二手交易、信息过载、C2C 信任机制相关文献或调查报告，用真实数据支撑问题陈述。

## 6. 技术选型与理由

| 选择 | 理由 |
|---|---|
| Python + Flask | 路由、模板、会话、错误处理清晰；代码量适合课程项目；便于逐行讲解 |
| SQLite | 零配置、单文件、可直接用 SQL 演示；与课程数据库内容衔接 |
| Jinja2 服务端渲染 | 无需前端构建；SEO 友好；表单校验与错误回显简单 |
| 原生 CSS / JS | 无 npm、无 CDN、离线可演示；避免框架版本问题 |
| pytest | 测试即文档；覆盖权限、状态、上传、双语等边界 |
| 本地文件上传 | 不依赖对象存储；UUID 文件名 + 文件头校验 |
| 本地 SVG 占位图 | 演示数据统一、无版权风险、断网可展示 |

未采用 React / Vue 的原因：本项目页面以表单和列表为主，服务端渲染足以覆盖；引入前端框架会增加构建、状态管理和部署复杂度，不利于课程讲解与现场演示。

## 7. 系统架构

```text
浏览器
  │  HTTP（HTML 表单 / 少量 JS）
  ▼
Flask 应用工厂 create_app
  ├─ 蓝图 auth      注册、登录、退出
  ├─ 蓝图 main      首页、分类、语言
  ├─ 蓝图 items     列表、详情、发布、编辑、状态、收藏、举报
  ├─ 蓝图 account   我的发布、收藏、历史、个人中心
  └─ 蓝图 admin     概览、商品、分类、举报
        │
        ├─ security.py    会话、CSRF、登录/管理员装饰器
        ├─ permissions.py 商品访问模式（full/paused/removed/denied）
        ├─ queries.py     列表、详情、收藏、统计 SQL
        ├─ uploads.py     图片校验与保存
        ├─ i18n.py        中英文案与 t()
        └─ db.py          SQLite 连接、查询辅助
        │
        ▼
SQLite（7 张表）+ static/uploads + static/img/placeholders
```

关键设计：

- **应用工厂**：便于测试时注入临时数据库和上传目录。
- **查询层集中**：商品 SELECT、过滤、排序、分页只在 `queries.py` 维护，避免路由里重复拼 SQL。
- **权限集中**：`item_access_mode()` 返回 6 种访问模式，详情页、编辑、收藏、举报共用同一判断。
- **CSRF 全局钩子**：所有 POST 统一校验，避免遗漏。
- **软删除带来源**：`removed_by` 区分管理员与卖家，恢复逻辑只对管理员下架生效。

## 8. 数据库设计摘要

共 7 张表：

- `users`：学号、昵称、密码哈希、微信 / 手机号、角色。
- `categories`：中英文名、slug、图标、排序、启停。
- `items`：发布者、分类、标题、描述、售价、原价、成色、地点、状态、浏览量、软删除字段、时间。
- `item_images`：商品多图，`sort_order=0` 为封面。
- `favorites`：用户 + 商品复合主键。
- `browse_history`：用户 + 商品复合主键，UPSERT 更新时间。
- `reports`：举报商品、举报人、原因、状态、处理时间。

关系：用户 1:N 商品；分类 1:N 商品；商品 1:N 图片；用户 M:N 商品（收藏、浏览）；用户 / 商品 1:N 举报。

规范化：图片拆表满足 1NF；复合主键满足 2NF；分类名、卖家信息外置，避免传递依赖，满足 3NF。`view_count` 作为受控冗余计数，提升排序性能。

详细字段、索引与 SQL 示例见 [`01-数据库设计.md`](01-数据库设计.md)。

## 9. 功能实现

### 9.1 账号与安全

- 学号唯一，密码使用 Werkzeug `generate_password_hash`；登录使用 `check_password_hash`。
- 会话保存 `user_id` 与语言；登录成功清空会话并重建 CSRF token，防止会话固定。
- 所有 POST 校验 CSRF；缺失或错误返回 400 自定义页。
- `next` 只允许站内相对路径，阻止开放重定向。
- 密码规则：至少 8 位，包含字母和数字；联系方式至少一项。

### 9.2 发布与图片

- 必填：1–5 张图片、名称、分类、售价、描述。
- 选填：原价、成色、交易地点。
- 图片同时校验扩展名、文件头和大小（≤5 MB）；文件名使用 UUID，原始文件名不落盘。
- 发布前检查卖家联系方式；缺失则跳转个人中心并提示。
- 保存顺序：先校验全部图片 → 保存文件 → 写商品与图片记录；异常时清理已保存文件。

### 9.3 状态机制

- 新发布默认 `on_sale`。
- 详情页与「我的发布」均可切换 `on_sale / sold / unavailable`。
- 已售：列表保留、卡片灰化、详情提示、联系方式隐藏、不可新增收藏。
- 暂停：从列表 / 分类 / 首页 / 搜索隐藏；直达详情显示「暂不出售」；联系方式与收藏不可用。
- 状态切换写 `updated_at`，无缓存，列表实时反映。

### 9.4 权限与访问模式

`item_access_mode()` 返回：

- `full`：正常访问。
- `paused_owner`：发布者 / 管理员查看暂停商品。
- `paused_public`：公开用户查看暂停商品的提示页。
- `removed_admin`：发布者 / 管理员只读查看管理员下架商品。
- `removed_seller`：管理员只读查看卖家删除商品。
- `denied`：404。

权限矩阵见 [`02-功能与页面说明.md`](02-功能与页面说明.md)。

### 9.5 搜索、排序、分页

- 关键词匹配标题与描述，`LIKE` 通配符 `%`、`_`、`\` 转义。
- 排序：最新、价格升序、价格降序、浏览量降序。
- 每页 12 条，页码越界收敛到最后一页。
- 分类计数采用「在售 + 已售」公开口径，与默认列表一致。

### 9.6 收藏与浏览记录

- 收藏只能新增在售商品；已售 / 暂停 / 下架的既有收藏保留，显示「已售 / 已失效」，可取消。
- 浏览记录只在登录用户浏览 `full` 商品时写入；暂停 / 下架 / 删除后从记录中隐藏。
- 同一商品重复浏览按 `(user_id, item_id)` UPSERT。
- 浏览量 30 分钟内同会话去重，发布者浏览不计数。

### 9.7 双语

- 所有系统文案集中在 `app/i18n.py`，模板与 Python 共用 `t()`。
- 分类、成色、状态、地点建议均有中英文映射；用户内容保持原文。
- 语言写入会话；切换后回到当前页面；`<html lang>` 同步。
- 日期格式按语言变化；英文布局经过截图验证无溢出。

### 9.8 管理后台

- 概览：用户数、商品总数、各状态数、总浏览、待处理举报、分类分布。
- 商品：全量筛选（含下架 / 卖家删除），填写原因下架，管理员下架可恢复。
- 分类：新增、编辑、启停；slug 唯一；停用后不在入口与发布下拉出现。
- 举报：待处理 / 已处理 / 已驳回 / 全部；可标记处理、驳回、下架并处理。
- 统计口径：商品总数与分类分布排除已删除；暂停仍计入商品总数。

## 10. 创新点

1. **状态优先的信息设计**：不是把状态作为附属字段，而是让状态决定列表可见性、卡片样式、联系方式、收藏与举报权限。它直接回应校园群「已售仍刷屏」的核心痛点。
2. **校园场景化分类**：7 个分类来自学生高频闲置（教材、电子、生活、运动、美妆衣物、文具、其他），比通用电商分类更贴近校园。
3. **带来源的软删除**：区分管理员下架与卖家删除，既保留审计记录，又尊重卖家意愿；管理员可恢复误下架，卖家删除不可被后台「复活」。
4. **零构建、离线可演示**：Flask + SQLite + 原生 CSS/JS，无 npm、无 CDN、无在线字体；本地 SVG 占位图保证断网演示效果。
5. **双语但不过度翻译**：系统文案双语，用户内容保持原文；既服务国际化展示，又避免自动翻译带来的语义失真。
6. **举报驱动的治理闭环**：学生举报 → 管理员处理 → 商品下架 / 举报关闭，形成可演示的校园治理流程。

## 11. 测试与结果

测试命令：

```bash
python -m pytest -q
```

实际结果：**85 passed**（Python 3.13.12，pytest 9.2.0；运行时间约 109 秒）。

| 测试文件 | 数量 | 覆盖内容 |
|---|---|---|
| `test_app.py` | 3 | 建表、外键开启、debug 默认关闭 |
| `test_i18n.py` | 3 | 默认中文、切换英文持久化、非法语言 404 |
| `test_auth.py` | 8 | 注册、重复学号、错误密码、英文错误、登录退出、开放重定向、控制字符重定向 |
| `test_security.py` | 5 | 缺失 / 错误 CSRF、密码规则、安全跳转、语言切换跳转 |
| `test_listing.py` | 9 | 公开过滤、搜索转义、中文搜索、价格排序、分页、分类计数、停用分类、分类名 |
| `test_detail.py` | 9 | 在售 / 已售 / 暂停 / 下架 / 删除、浏览量、只读控件、超大 ID |
| `test_publish.py` | 10 | 登录要求、发布成功、联系方式、缺图 / 超图 / 伪造图、英文地点、停用分类编辑、超大分类 |
| `test_status.py` | 7 | 状态切换、非本人 403、暂停隐藏、卖家删除、POST 越权、缺失 CSRF |
| `test_uploads.py` | 4 | PNG 文件头、伪造扩展名、超 5 MB、UUID 与路径穿越 |
| `test_account.py` | 4 | 我的发布过滤、收藏规则、历史去重与隐藏、资料与密码 |
| `test_admin.py` | 5 | 非管理员 403、下架恢复、不可恢复卖家删除、分类创建启停、举报处理 |
| `test_seed.py` | 1 | 28 件商品与状态分布 |
| `test_home.py` | 3 | 首页最新 / 热门、热门仅在售、404 页面 |
| `test_smoke.py` | 14 | 公开、登录后、管理员页面全部 200 |
| **合计** | **85** | |

视觉与交互检查：

- 1440px 桌面端：首页、列表、详情、发布、后台、举报页。
- 375px 移动端：首页、列表、展开菜单；`scrollWidth = 375`，无横向溢出。
- 英文界面：首页与后台截图，导航、表单、状态、统计均无溢出。
- 轮播 6 秒自动切换、移动端菜单展开均通过浏览器脚本验证。
- 截图见 [`docs/screenshots/`](screenshots/)。

未进行的测试：真实多用户并发、压力测试、正式无障碍审计、真实校园 SSO 联调、用户可用性研究。报告中不应声称已完成这些测试。

## 12. 局限与展望

### 12.1 局限

1. **校园封闭性仅靠自填学号**：没有真实 SSO 或校园邮箱验证，理论上校外人员可注册。这是「校园专属」主张的最大限制。
2. **无站内沟通与支付**：联系方式直接展示，交易和付款在线下完成；平台不提供担保。
3. **单机 SQLite**：适合课程与小型部署；高并发写入、跨节点扩展能力有限。
4. **无通知系统**：收藏商品变价、举报处理结果不会主动通知用户。
5. **图片处理简单**：仅校验与存储，未压缩、裁剪、生成多尺寸；大图会影响加载。
6. **管理审计有限**：只记录举报处理时间，没有完整的管理员操作日志。
7. **评估以功能测试为主**：85 个自动化测试覆盖行为边界，但没有真实用户使用数据与满意度调查。
8. **时间处理简化**：使用本地时间文本，未处理时区与夏令时。

### 12.2 展望

- 接入学校 SSO / 校园邮箱验证，真正实现校内闭环。
- 增加站内消息、议价、预约自提、订单与担保支付。
- 图片压缩、多尺寸与对象存储；上传进度与失败重试。
- 收藏降价提醒、举报处理通知、站内信。
- 管理员操作审计日志、批量审核、敏感词与图片审核。
- 迁移 PostgreSQL，加入缓存、限流与全文搜索。
- PWA / 小程序端，降低移动端使用门槛。
- 用户研究：发布耗时、无效咨询下降比例、成交转化率等指标。

## 13. 结论

### 13.1 中文结论

「校园集市」以商品状态为核心，把校园二手交易中最常见的「信息过期」问题转化为可执行的系统规则：卖家一键切换状态，系统据此控制列表可见性、卡片样式、联系方式和收藏权限。项目完成了从注册、发布、浏览、搜索、收藏、联系到成交后状态更新的完整闭环，并提供管理员审核、分类维护、举报处理和全站统计。技术实现保持轻量，Flask + SQLite + 服务端渲染无需构建步骤和外部服务，适合课程演示与后续扩展。85 个自动化测试和桌面 / 移动端视觉检查验证了主要功能与权限边界。尽管在真实身份认证、支付、通知和并发能力上仍有局限，但本项目证明了「以状态为中心」的设计能够以较低成本显著提升校园闲置信息的准确性与可用性。

### 13.2 English Conclusion

Campus Market treats item status as the core of the system rather than an afterthought. Sellers switch a listing between on sale, sold, and paused; the system then enforces what appears in public lists, how cards are rendered, whether contact details are shown, and whether the item can be saved or reported. The project delivers a complete loop from registration and posting to browsing, search, favourites, contact, and post-sale status updates, together with an admin dashboard for moderation, categories, reports, and site statistics. The implementation remains deliberately lightweight: Flask, SQLite, and server-rendered templates require no build step or external services, making the system easy to demonstrate and extend. Seventy automated tests and desktop/mobile visual checks validate the main behaviours and permission boundaries. Limitations remain in real identity verification, payments, notifications, and concurrency, but the project shows that a status-centred design can improve the accuracy and usefulness of campus second-hand information at low cost.

## 附录 A：原始需求对照

| 原始需求 | 实现 |
|---|---|
| 校园专属、安全可靠 | 学号注册 + 校内场景文案；真实 SSO 为未来工作 |
| 分类清晰 | 7 个校园高频分类，中英文名，后台可维护 |
| 实时在售 / 已售状态 | 三态切换；已售灰化、隐藏联系方式；暂停下架 |
| 发布流程极简 | 单页表单；默认在售；图片预览；1 分钟可完成 |
| 首页导航 / 轮播 / 热门 / 分类入口 | `/` 与 `index.html` |
| 全部商品排序 | 最新 / 价格升降 / 浏览量 |
| 商品卡片信息 | 图片、名称、价格、状态、发布时间、分类、成色、浏览量 |
| 发布必填 / 选填 | 必填 5 项；选填原价、成色、地点 |
| 我的发布编辑 / 状态 / 删除 | `/my/items` + 详情页操作 |
| 个人中心 | 收藏、浏览记录、联系方式、密码 |
| 商品表字段 | 见 `01-数据库设计.md` |
| 后台审核 / 删除 / 分类 / 数据 | `/admin/*` |
| UI 浅蓝白 / 圆角 / 状态色 | `static/css/style.css` |
| 完整用户流程 | 本文与 `02-功能与页面说明.md` |
| 创新点 | 本文第 10 节 |

## 附录 B：演示账号

| 角色 | 学号 | 密码 |
|---|---|---|
| 管理员 | `admin` | `Admin@12345` |
| 学生 | `2023001` | `Demo@12345` |
| 学生 | `2023002` | `Demo@12345` |
| 学生 | `2023003` | `Demo@12345` |

## 附录 C：可用的英文总结（可直接放入报告摘要或 Conclusion）

This campus second-hand trading website provides students with a convenient and standardised platform for publishing and browsing idle items. It supports classified management, price marking, real-time status updating (on sale / sold / unavailable) and independent editing. The platform addresses the problems of messy information, invalid enquiries and unclear transaction status found in traditional campus second-hand group chats. By making item status visible and enforceable, it improves the efficiency of student idle-resource circulation while keeping the implementation lightweight and easy to demonstrate.

## 附录 D：图表与引用建议

- 图 1：系统架构图（可用本文第 7 节文本重绘）。
- 图 2：ER 图（`01-数据库设计.md` 的 Mermaid 可直接渲染）。
- 图 3：商品状态机（`02-功能与页面说明.md` 的 Mermaid）。
- 图 4：首页 / 列表 / 详情 / 后台截图（`docs/screenshots/`）。
- 表 1：技术选型对比；表 2：测试覆盖；表 3：需求对照。
- `[建议补充引用]` 处请补充：校园二手交易相关研究、C2C 信任与信息质量文献、Flask/SQLite 官方文档、WCAG 2.1 指南。不要编造参考文献。
