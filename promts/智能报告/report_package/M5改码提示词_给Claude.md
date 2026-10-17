# 给 Claude 的改码提示词（M5 智能报告）

> 用法：整段复制给 Claude（Code / Cursor / CLI 均可），它需要能读写 `D:\GuangdongEducationStudyAbroadProgram`。

---

## 提示词正文（从这里开始复制）

你是粤教留学项目管理平台的实现者，本次只负责 **M5 智能报告模块**。任务：按任务文档逐条比对现有代码，分批实施修改。先读、再计划、再改、每批改完停下来汇报。

### 一、仓库与环境事实（不要重新探索这些）

- 仓库：`D:\GuangdongEducationStudyAbroadProgram`，当前分支 `master_ZNBG`，HEAD `5d57e4a`（v6.8.7）
- 任务文档（必读，逐条对照）：`C:\Users\Windows\Desktop\项目2\M5智能报告_未完成与二期任务_合并版.md`
- 细项底稿（需要 `文件:行号` 证据时查同目录）：`M5智能报告后端缺口审计.md`、`智能报告模块_前端与接口现状分析.md`、`M5需求与二期任务提取清单.md`
- 后端解释器：`backend\.venv\Scripts\python.exe`（Python 3.11.16，依赖已装，缺 `pypdf`，别为此改依赖）
- 前端：`frontend`，`node v24` + `npm`（`pnpm` 不在 PATH，用 npm）
- 数据库：MySQL 8 端口 **59000**，库名 `GuangdongEducationStudyAbroadProgram`；Redis 6379；`STORAGE_BACKEND=local`
- Docker CLI 已装但引擎可能没启动，先 `docker ps` 确认；E2E 脚本是 `backend/tests/e2e_m3m4_test.py`
- 已知环境噪音：`backend\.pytest_cache` 目录权限异常，读取时报错属正常；工作区外的写操作会被沙箱拒绝，别往仓库之外写文件
- 智能报告的真实代码入口：`backend/app/api/v1/reports.py`、`schemas/report.py`、`services/report_{service,calculator,content,ai_service,drilldown,pdf,mock_data}.py`、`repositories/report_repo.py`、`utils/report_period.py`；**`AiReport` 模型在 `models/crm.py:61-85`，不在 `models/system.py`**

### 二、必读顺序（读完再动手）

1. `AGENTS.md`（项目接手指南，含 7 条硬性规则）
2. 任务文档全文（13 个工作包 / 90 项细项）
3. `promts/智能报告/report_package/00_资料包说明.md`、`02_一期指标口径表V1.md`、`06_后端交付说明V1.md`
4. 上面列出的 M5 代码文件（全读，不要只 grep）
5. `docs/接口契约v1.md` §7 报告（约 716-734 行）、§9 跨模块取数（约 863-879 行）
6. `frontend/src/views/RoleWorkspace.vue:385-395`、`frontend/src/api/platform.ts:96-103`、`frontend/src/data/mock.ts:172-178`

### 三、硬约束（违反任何一条就停下问我）

1. **范围**：只改 M5 及它直接依赖的接口层。不动 M1/M2/M4 的业务表结构（`models/customer.py`、`models/customer_service.py`、`models/student.py` 的既有字段），不动 M0 共用模块的内部实现（`approval_engine.py`、`event_bus.py`、`notification_service.py`、`ai_service.py` 只允许只读复用或新增方法）。
2. **不编造数据**：任何指标取不到数据，必须显式标「数据不可得」或「数据不足」，**禁止填零、禁止用模拟值冒充真实值**。
3. **禁止静默回落**：`production` 模式下取数失败要报错或在报告头标记，不允许悄悄回落到 mock 数据。
4. **枚举收敛**：`report_type` 以代码为准（`customer_analysis / daily_report_summary / weekly_report_summary / psych_weekly / complaint_weekly`），契约与前端向它对齐，不许反向改后端枚举。
5. **文档同步**：每批改完同步 `docs/` 六件套——`更新记录.md`、`AGENTS.md`（根目录 + `docs/AGENTS.md` 两份）、`接口契约v1.md`、`开发路线图.md`、`项目需求文档.md`、`运行日志.md`。
6. **必须验证再报完成**：先跑测试，把命令与结果写进汇报，不允许"看起来对"就报完成。
7. **Git**：只在当前分支做本地 commit（`feat(m5): ...` / `fix(m5): ...`），**不 push、不合并、不切分支**。
8. **遵守项目既有分层**：schemas / repositories / services / api 四层不混用；报告模块只通过各模块已暴露的查询能力取数，不直接跨模块 JOIN 别人的表。

### 四、分批任务（一次只做一批，做完停下等我确认）

#### 批次 A：零业务变更的对齐（先做，风险最低）

| 细项 | 要做的事 |
|---|---|
| M5-13.1 | 修 `docs/接口契约v1.md:723` 的 `report_type` 枚举为代码那套；同步 `docs/开发路线图.md:193-196`；后端加一层枚举校验（见 M5-12.3） |
| M5-13.2 | 契约里 `status` 的 `generating→completed/failed` 与实现对齐（实现失败态在批次 B，本批先把契约改成实际可达的状态集合） |
| M5-13.3 | 解决迁移与模型不一致：`001_initial.py:392-415` 的 ai_report 缺 `version/data_source_status/error_message`，`create_time` vs `created_at`，`file_type String(20)` vs `String(32)`。二选一并说明理由：①新增 `003_report_columns.py` 用可重复执行的 ALTER 补齐；②按当前 models 重生成 baseline。目标：**空库 `alembic upgrade head` 能建出与 ORM 一致的 ai_report** |
| M5-13.5 | 给 `docs/项目需求文档.md` 补智能报告章节（五类报告、口径、权限、下钻、导出），并把 `:2032-2034` 的未完成标记改对 |
| M5-13.6 | `docs/开发路线图.md` 把「模拟数据闭环完成」与「真实数据对接完成」拆成两个状态，别再写"M5 已完成数据接口对接" |
| M5-13.7 | `verify_all.py:174-185` 的报告断言改成从 OpenAPI 动态取，别写死路径与路由总数 |

**验收**：`pytest backend/tests/test_services -q` 全绿；`python backend/verify_all.py` 全绿；空库 `alembic upgrade head` 通过；六件套已同步。

#### 批次 B：后端口径与健壮性（不依赖外部确认）

| 细项 | 要做的事 | 关键点 |
|---|---|---|
| M5-04.1 | `status_overview` 加周期约束 | `report_calculator.py:51-56` 现在无周期过滤 |
| M5-04.2 | 周期合法性校验（周/月对齐、未来周期、跨年、超长跨度） | `report_service.py:41-42` 现在只校验 start<end |
| M5-04.3 | `open_count` 按周期界定 | `report_calculator.py:211` |
| M5-07.1 | 日报与周报拆开 | `report_content.py:40-41` 两类型共用 `calculate_weekly_submission`；启用死函数 `calculate_daily_submission`（`:116`），PDF 分支同步拆（`report_pdf.py:92-109`） |
| M5-03.5 | 特别案例口径统一 | `report_calculator.py:229` 与 `report_drilldown.py:71` 判定不同，抽成一个共用函数 |
| M5-02.2 | `build_mock_dataset(period_start, period_end)` 支持周期 | `report_mock_data.py:265` 现在无参数、周期写死 |
| M5-12.2 | 失败态 + `error_message` + 一次重试 | 现在异常直接 500，`error_message`（`models/crm.py:74`）零写入 |
| M5-12.3 | 列表瘦身（不回传完整 `report_content`）+ `report_type` 枚举校验 | `api/v1/reports.py:28-33` |
| M5-06.4 | 版本号并发保护 | 加 `(report_type, period_start, period_end, version)` 唯一约束 + 冲突重试 |
| M5-08.5 | PDF 文本 XML 转义 | `report_pdf.py:172/181/185/190/193` |
| M5-11.5 | 下载空内容防护 | `report_service.py:100` 现在会抛 `AttributeError` |

**验收**：每个细项至少一条新/改单测（放在 `backend/tests/test_services/test_report_*.py`）；PDF 用含 `&`/`<` 的文本能正常生成；失败场景能落 `status=failed` 且带 `error_message`。

#### 批次 C：真实数据接入（先骨架，不越界）

| 细项 | 要做的事 |
|---|---|
| M5-01 | 产出 `docs/M5_字段映射表.md`：逐指标列出 来源表/字段、计算方式、权限、缺口、责任人。**这份表是给 M1/M3/M4 负责人确认用的，不是代码** |
| M5-02.1 | 四个适配器，放在新文件 `backend/app/services/report_data_source.py`：客户/员工/心理三个可以接（有表有字段），投诉标 `data_unavailable` 并写明缺哪 9 个字段（`models/student.py:49-60`） |
| M5-02.3 | provider 开关：`config.py` 加 `REPORT_DATA_SOURCE=mock|production`，默认 `mock`；`report_service.py` 按开关选 provider |
| M5-02.4/02.5 | `production` 下缺数据必须显式标记，报告头 `data_source_status` 与数据质量提示如实反映；三态区分「无数据 / 读取失败 / 真为 0」 |
| M5-03.x | 阻塞项只记录不实现：投诉 9 字段、客户状态快照、画像 4→3 映射，写进字段映射表的"待确认"列 |

**验收**：`REPORT_DATA_SOURCE=production` 能生成一份报告，其中客户/员工/心理的指标来自真实表，投诉指标显示「数据不可得」；每个指标都能在映射表里指到字段。

#### 批次 D：前端闭环

| 细项 | 要做的事 |
|---|---|
| M5-05.1 | 报告列表（状态/版本/来源/筛选/分页），替换 `RoleWorkspace.vue:385-395` 的 tab 卡片 |
| M5-05.2 | 详情页：渲染 `report_content`（header/summary/metrics/trend/analysis/suggestions/data_notes），加独立路由 |
| M5-05.3 | 生成按钮 + 生成中状态 + 失败提示 + 重新生成 |
| M5-05.4 | 三个下钻页（客户/心理个案/投诉特别案例） |
| M5-05.5 | 枚举映射常量（`CA/DS/WS/PW/CW` ↔ 后端 5 个 type），全项目只留一处 |
| M5-05.6 | 导出接真实 `GET /reports/{id}/download`，删掉 `exportCsv` 的伪造逻辑（`:215-224`） |
| M5-05.7 | 「演示数据」标签 + 加载中/空/无权限/接口未开放四态；去掉 `platform.ts:11-17` 的静默回落（或至少加显式提示） |
| M5-05.8 | 字段消费修正（读 `report_type`/`report_title`，别再读 `code`/`name`） |
| M5-05.9 | 员工端不再请求 `/reports`（`:46-47`） |
| M5-05.11 | 健康周报/投诉周报的两个入口合并 |
| M5-05.12/05.13 | 下架或显著隔离经理页静态演示数字；清掉 `views/manager/Index.vue` 死文件 |

**验收**：用 MANAGER 账号走完「列表 → 生成 → 详情 → 三个下钻 → 导出 PDF」；任何一步失败都有明确提示，页面上不再有无法追溯来源的数字。

#### 批次 E：测试与验收

`M5-10.1`~`M5-10.9`：7 端点权限矩阵与入参边界、编排层（generate/list/version/ai_status）、非参考周期、未落字段回归、calculator 与 drilldown 交叉一致性、AI 降级分支、PDF 渲染质量、E2E 纳入 `/reports`、测试资产入库。

**验收**：`pytest backend/tests` 全绿；`tests/e2e_m3m4_test.py` 增加报告链路用例并通过；`docs/测试报告_*.md` 追加本轮记录（含真实/模拟来源与覆盖率分母）。

### 五、本次明确不做

- 二期 16 项（角色拆分、量表、NL2SQL、ASR、调度、订阅、Word/Excel、投诉分类、高价值客户、自定义第五类报告等）
- M1/M2/M4 的功能开发（客户模块、客服模块、学生端未完成部分）
- 改 M0 共用模块内部逻辑；给 AI 网关加新协议
- `create_all` 与 Alembic 的双轨制暂不动，除批次 A 明确要求的那一处

### 六、必须停下来先问我的事（不要自行决定）

1. 合并版文档第 4 节的 8 个待拍板口径（画像 4→3、投诉字段与复核、客户状态历史来源、心理响应时限、负责人指定、是否自动调度、一期心理授权范围、M2 统计是否纳入）
2. 需要动别人表的改动：投诉 9 字段（`models/student.py`）、客户状态快照（`models/customer.py`）
3. 需要新增取数端点：契约 §9 的 `GET /crm/assessments/{id}`、`GET /student/psych/stats`、`GET /student/tickets/stats` 要不要由你来实现、放在哪个模块
4. 任何要改前端路由结构或 Element Plus 主题的改动
5. 任何需要新依赖（图表库、导出库）的改动

### 七、每批交付的汇报格式

```
## 批次 X 完成：<一句话>

### 变更清单
| 细项 | 文件 | 变更摘要 | 新增/修改测试 |

### 未做 / 降级项
| 细项 | 原因 | 需要谁确认 |

### 验证结果
命令 + 结果摘要（pytest 通过数 / verify_all / alembic / 手动验证步骤）

### 文档同步
更新的六件套文件与变更点

### 风险与回滚点
本次改动可能影响的地方、如何回滚

### 下一批前需要你确认
```

**现在开始**：先做批次 A。读完上述文件后，先用不超过 30 行说明你对现状的理解与批次 A 的执行计划，等我确认后再动手改代码。

## 提示词正文（复制到这里结束）

---

## 附：使用建议

- 若 Claude 一次做完所有批次，叫停并让它只交批次 A。
- 批次 C 之前先让它把 `docs/M5_字段映射表.md` 交给你，你拿着这份表去找 M1/M3/M4 负责人确认字段，再让它写适配器。
- 每批完成后让它跑一次 `docker ps` 与 pytest，把输出贴给你，别只信口头"已通过"。
- 若它想改 `report_type` 枚举，明确拒绝：只许契约与前端向代码对齐。
