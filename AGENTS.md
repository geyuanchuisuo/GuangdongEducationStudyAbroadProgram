# AGENTS.md - 项目接手指南

> 给下一个接手这个项目的人/AI 的完整指南

---

## 零、快速定位（打开项目先看这里）

> v6.11.17（2026-10-19，ZNBG/M5）：**production 投诉域静默清零缺陷修复**——`report_data_source.py` 漏 import `ComplaintReportInput`（v6.11.0 引入），调用处 NameError 被 v6.9.6 逐行容错当脏行静默吞掉、报告仍 completed → production 任意含工单周期投诉指标恒 0（本库 105 行全跳过；mock 不受影响）；补 import + 防回退用例后实测 orders_total 0→9 / new_count 6 / analyzed_count 8；回归 compileall + pytest 158/158 + Docker E2E 81/81 + production 冒烟 7/7；详见更新记录 v6.11.17 与 LOG-074（ZNBG）。
>
> v6.11.18（2026-10-19，anhoa）：**第十五次同步 origin/master**——M0 公共模块 10 项变更（Dify 共享卷/迁移006/种子补齐/投诉域修复等）经用户批准并入，解 8 冲突；无 M1/M2 业务逻辑变更；回归 compileall + verify_all 29/29 + pytest 164/164 + 前端 build ✅；详见更新记录「merge 第十五次同步」与 LOG-069。

> v6.11.16（2026-10-19）：Dify 1.16 首启脚本修正到 `/console/api/*` 并使用 cookie/CSRF 登录，补入智能报告 app key 映射；Agnes 模型配置仅保存在忽略的 `dify/docker/.env`。Dify API/Postgres/Redis/Sandbox 健康且管理员已创建，但 OpenAI 兼容插件和 DSL 依赖需访问 Marketplace；当前本机及容器均收到 403，dify-init 停在供应商配置，app keys 尚未生成。详见更新记录 v6.11.16、LOG-073。

> v6.11.15（2026-10-19）：Dify 首启阻塞修复——根 `.env.example` 启用默认 PostgreSQL/Weaviate profiles；Dify Redis 使用独立服务名；backend 只读挂载 `dify_app_keys`；init_permissions 首启生成 sandbox 配置和依赖清单；Dify 示例移除可选空值并统一控制台 8081。本地 `.env` 保留但不跟踪。当前模型三项未配置，dify-init 尚未完成。详见更新记录 v6.11.15 与 LOG-073。

> v6.11.13（2026-10-19，ZNBG）：第十次同步 origin/master→master_ZNBG——**M5 阻塞 B5 销账**：上游 M0 4 行补丁（DIFY_REPORT_AGENT_KEY + AgentType.REPORT/映射，经用户批准）并入；M5 配套 session 改 "new"（动态串必被 Dify 拒）；生效差一步：backend/.env 回填报告 key；详见更新记录 v6.11.13 与 LOG-071（ZNBG）。

> v6.11.13（2026-10-19，anhoa）：**Dify 1.16 环境实跑+dify_init.py 重写**——一体化 Dify 在本机首次实跑完整初始化链路（插件安装→模型凭据→4 应用导入/创建/发布→key 回填），dify_init.py 按 1.16 实测 Console API 重写（CSRF/base64、插件制供应商、工作流 publish、agent-chat DSL 改 create+model-config、草稿工作流 hash 补丁重绑模型），E2E 客服对话真实 AI 回复通过；pytest 163/163、verify_all 29/29、build ✅。

> v6.11.12（2026-10-19）：**一体化 Dify 栈首次启动实测失败（exit 1）**，定位两处配置缺陷并按用户决定**暂不修复、仅记录**：**A（Dify 侧）** `dify/docker/.env` 精简模板把可选变量留成空值行（`KEY=`）→ 空串被当作"显式设为空"，Dify `api` 启动即 `ValidationError: INDEXING_MAX_SEGMENTATION_TOKENS_LENGTH unable to parse string as an integer [input_value='']`，api/worker/worker_beat/plugin_daemon/sandbox/agent_backend 全部 Restarting（应改为注释态 = 用默认值）；**B（业务侧）** `docker-compose.yml` backend 的 command 要 `. /run/dify-keys/app_keys.env`，但 `volumes` **缺 `dify_app_keys:/run/dify-keys` 挂载** → 不论 dify-init 成功与否 backend 都起不来（`sh: 1: .: cannot open …: No such file`）。业务侧仍可跑（旧拓扑 4 容器：`/health` ok、107 路由、登录与业务接口全通）；业务后端已用 `docker cp` 空 `app_keys.env` + `up -d --no-deps backend` 临时恢复，**该手段不持久（容器重建即再次失败）**。详见更新记录 v6.11.12、运行日志 LOG-070、开发路线图移交清单第 25 项。

> v6.11.11（2026-10-19）：本机环境修复——① `backend/.env` 数据库密码旧值 `password`→`420821`（实测 `420821` 可连、`password` Access denied；容器内 backend 用 compose 注入串，故该错配长期被掩盖）② 运行库从未走过 alembic（`alembic_version` 为空 + `student_score` 缺 `uq_student_score_unique`，库结构停在 004）→ `alembic stamp 004_m5_drill_ticket_ai` 后 `upgrade head` **只补跑 005、保留全部数据**：`student_score` 104→97（清 7 条重复，每组留最小 id）、唯一索引已建、重复插入实测 `ERROR 1062 Duplicate entry` ③ Dify 指向切打包基线（根 `.env`=`http://dify_nginx`；`backend/.env` 宿主机开发=`http://localhost:8081`）④ 已下线的 `DIFY_REPORT_AGENT_KEY` 在 `.env` 中注释保留，避免"看着配了、实际不生效"。verify_all 29/29；详见更新记录 v6.11.11 与 LOG-069。**遗留**：`dify/docker/.env` 不存在（根 compose 的 `dify-init` 用 `env_file` 依赖它，缺文件则 `docker compose up` 报错）；`dify/docker/.env.example` 的 `EXPOSE_NGINX_PORT=80` 与 v6.11.9 声称基线 8081 不一致。

> v6.11.10（2026-10-19）：同步 origin/master 文档基线并按用户逐项确认处理共用模块：移除 M0 REPORT Agent，恢复 M5 动态会话 ID，模型默认值切换至 Mimo；初始化按 DSL 应用名去重并跳过留档 DSL。保留本地强密码、app key 受限共享卷自动加载、DIFY_BASE_URL 插值与本地 .env 不入库。

> v6.10.7（2026-10-19，anhoa/M2）：缴费账号口径拍板（用户确认）——两路统一「引导联系顾问」不暴露账号（Chatflow 速查表 v6.10.5 起已是此措辞，本次对齐 P5 数据源 cs_faq 第 25 条 + 守卫测试），pytest 163/163；v6.10.6 意图码契约漂移修复（后端 normalize_intent 单点归一到契约 9 码 + converted→lead_capture + seed 换契约码，销 LOG-057 遗留第 3 项）；详见更新记录 v6.10.7/v6.10.6 与运行日志 LOG-066/LOG-067。

> v6.11.5（2026-10-18）：第九次同步 origin/master→master_ZNBG——PROSPECT 注册免审批并入（M0 user_service.py，经用户批准；注册即"正常"立即可登录）+ 学生申请进度布局紧凑化 + REMOTE_ACCESS 补全；pytest 全过 + verify_all 29/29 + npm build；详见更新记录 v6.11.5。；**v6.11.6（ZNBG，2026-10-18）补齐 M0：`config.py` 加 `DIFY_REPORT_AGENT_KEY`、`ai_service.py` 加 `AgentType.REPORT` + `_AGENT_KEY_MAP` 映射（共用模块，经用户授权）；同时修掉 M5 一个隐蔽缺陷——报告 AI 传假 session 被网关当 `conversation_id` 发给 Dify，Dify 要求 UUID → 400 被静默吞掉回落 mock，改成 `"new"` 后实测 `ai_source=dify`；pytest 152/152、verify_all 29/29**

> v6.10.5（2026-10-18，anhoa/M2）：客服 FAQ 两入口无回答修复——Chatflow 内嵌 37 条 FAQ 速查表 + 种子 upsert/问法迁移；VM 在线应用（2f92093f 七分支 + 143c1127 导入版）已发布落地实测通过；**同日第十一次同步 origin/master（d4aa045：注册免审批反转 + M3 成绩三件套，公共模块 2 项经用户批准）**，合并后 pytest 157/157；详见更新记录 merge 条目、v6.10.5 条目与运行日志 LOG-057/LOG-063。

**当前进度**：Phase 0 公共地基已完成（v6.0.1），Phase 1 模块并行开发中；M3 员工模块全部交付（v6.5.0 收官）；v6.6.0 需求对齐差异全部落地；v6.7.0~v6.7.2 管理层端三项+需求核对 52/52；master 已合并 longtrying（62d4cff）与 longtrying_stu（a23fc49，第三次合并）全部工作；**M4 学生模块一期全部交付（v6.8.0 第一批 7 子模块 + v6.8.1 第二批 学生助手Agent/提醒聚合，11 paths / 13 endpoints）；v6.8.2 Docker 环境搭建 + M3/M4 数据库端到端验证通过（E2E 69/69，修复 7 项缺陷）；v6.8.3 指令解析本地兜底 + 提醒聚合缺陷修复（E2E 71/71 幂等全过）；v6.8.4 文件存储改本地磁盘后端（docker compose 移除 MinIO，零额外镜像三容器直跑）+ DIFY_BASE_URL 根因修正；v6.8.5 引入 M5 智能报告 7 paths 与前端界面，M3 dashboard 与《一期指标口径表V1》统一名称+新增差异字段（verify_all 25/25 + M5 测试 32/32 + 对齐 14/14）；v6.8.6 AI 全链路打通：Dify 绑定 mimo-v2.6-flash（api.xiaomimimo.com），3 个 Agent 应用创建并回填 app key，真实 AI 链路 6/6 验证通过，环境缺口全部关闭**；**anhoa 分支 v6.8.0：M1 客户模块 + M2 客服 Agent 一期补齐（客户 8 研判字段/6 态流转/pending_lead 待补全线索/客服 Agent 4 出口），2026-10-17 两次合并 origin/master 并线（v6.8.0 被两条分支并行使用，路由 81→99）**；**v6.9.0（anhoa 分支）：M2 客服 Agent 二期补齐——cs_recommend_log 推荐落库新表 / [SLOTS] 槽位采集与画像更新 / 仅微信号→pending_lead / 公开 /cs/faq + /cs/sessions 接口 / FAQ 种子 37 条 / 前端客服窗接线（pytest 70/70 + verify_all 29/29；Dify 侧输出契约配置待 Docker，未配置时标记解析自动跳过）**；**v6.8.8 P1 运行时缺陷修复：ai_service.py 恢复 M3/M4 依赖的 AgentType/AIService/ai_service（anhoa 合并重写所致，函数内延迟导入绕过静态检查），客服 AiService 与通用 AIService 双服务共存，容器内真实 Dify 调用成功（verify_all 27/27 + pytest 64/64）**；**v6.9.0 远端访问方案（longtrying_test 分支）：docker-compose 增加 nginx 统一 80 入口 + ngrok 内网穿透脚本 + 一键构建启动脚本 + 完整使用指南（REMOTE_ACCESS.md），本地执行 `.\scripts\build-and-serve.ps1` + `.\scripts\start-ngrok.ps1` 即可获得公网 URL**；**v6.9.1 远端访问实测修正：nginx 端口 80→8080（本机 80 被 Dify 占用），新增 localtunnel 免注册方案，公网实测通过（https://wide-cameras-pay.loca.lt 前端 200/API 正常）**；**v6.9.2 master 快进合并 longtrying_test（b84acf3..4c27071，13 文件 +406/-14，无冲突，verify_all 27/27），远端访问能力并入主干；**M5 智能报告 v6.9.0（ZNBG 分支线，与 master v6.9.0 远端访问同名异义）：批次 A~E 连续交付——口径健壮性 11 项 + 真实数据适配器骨架（REPORT_DATA_SOURCE 开关/三态质量标注）+ 前端报告闭环（列表/详情/生成/下钻/真实 PDF）+ 测试资产（全仓 pytest 113/113、verify_all 27/27、npm build 通过）**；**v6.9.5 第六次同步 origin/master（4d6547c，作者 geyuan）：先按硬性规则 5 上报公共模块（config 加 DIFY_MODEL_API_KEY/BASE_URL/NAME、新增 model_ai_service.py 共用模型网关被 M3/M4/M5 三处调用、compose/.env.example/启动脚本凭据、PublicLayout 公共导航），经用户同意后合并；按用户决定①数据库凭据保留 420821+59000（回退 master 的 123456+3306）②恢复 views/manager/Index.vue ③不引入 master 的 health/complaints 静态占位模板（无路由、与智能汇总口径重复）；M5 侧统一走共用网关并新增差异字段 `ai_source`（model/mock/unavailable，PDF 与前端文案同源标注，替代「可用（模拟）」）；修 master 自带缺陷 employee_service.py 缺 logger 导入（/employee/agent/chat 与 /employee/guide/ask 两处 50001）+ 解冲突引入的 TS6133；27/27 + 113/113 + build + E2E 80/80**；**v6.9.8（anhoa，2026-10-18）M2 阶段B Dify VM 侧落地：192.168.184.128:8080 重建「粤教客服Agent」（deepseek-flash 临时代替共用网关，用户决定后续再调），pre_prompt 4336 字符注入三标记契约（[intent:]/[RECOMMEND]/[SLOTS]），4 知识库 7 文档 economy+全文检索兜底（siliconflow embedding 402、本机 ollama 跨网段不可达），dify_client /v1 前缀修复；7 场景端到端全过 + RAG 命中 16 条 + verify_all 29/29**；**v6.9.9（anhoa，2026-10-18）M2 阶段B-B4/B5 Chatflow 重建：advanced-chat 应用 2f92093f，B5 问题分类器 7 类节点编排（确定性 intent 前置），B4 检索工具改知识库兜底（课程活动库 f892116a，VM→宿主机网络不通）；后端 THINK_RE 剥离 reasoning 思考块，.env 换 chatflow key；7 场景端到端全过 + THINK 无泄漏 + pytest 129/130**；**v6.9.10（anhoa，2026-10-18）M1 AI 信息提取兜底：客服对话本地规则提取画像字段——LOCAL_EXTRACT_PATTERNS 5 组正则（name/age/education/gender/study_intent），_local_extract_merge 补缺不覆盖，_normalize_slot_value 清洗对齐；Dify 未输出 [SLOTS] 时自动补充，pytest 129/130 + 本地提取单元测试 5/5**；**v6.9.11（anhoa，2026-10-18）M1 客户注册/登录 PROSPECT 审批门：RegisterRequest 扩展 PROSPECT+phone/wechat/age/education 选填；UserService.register 注册即审批——用户 status=待审批→customer 主表创建（sys_user_id 关联）→审批实例 biz_type=prospect_register 自动分配 MANAGER；approve→用户激活+customer.registered 事件，reject→用户禁用；POST /auth/prospect/approve 审批接口，pytest 129/130**（⚠ 2026-10-18 实测发现 schema 漏改——PROSPECT 注册入口 422，**已由 v6.9.13 补齐**：pattern 扩 `^(STUDENT|EMPLOYEE|PROSPECT)$` + phone/wechat/age/education 选填，端到端实测 6/6 通过；遗留已由 v6.10.0 清）**；**v6.10.0（anhoa，2026-10-18）M1/M2 五项补齐：审批人 JWT+MANAGER 校验（40301）、注册事务原子化（孤儿缺陷消除）、登录待审批 40006、新增 GET /cs/courses 公开课程（路由 103 paths）、前端注册/课程页接线、活动枚举归一——活动报名闭环全通；测试资产 +15（注册审批门/本地提取入库/test_ai 环境隔离），pytest 143/143 + verify_all 29/29**；**v6.10.3（ZNBG，2026-10-18）第七次同步 origin/master 732d43f（fast-forward 零冲突）：公共模块 8 类经用户同意后并入（M0 AI 网关 ai_service.py +243（客服槽位采集/本地提取/推荐落库）、M0 认证 user_service.py +113（PROSPECT 注册审批门 status=待审批 + 40006）、auth.py/schemas/user.py、迁移 001/002 共 8 处 FK BigInteger→Integer、seed_data.py 重写为 drop_all+seed(42)+固定账号、verify_all.py 增 M2 公开客服断言、models/customer_service.py+__init__、dify_client.py、api/v1/ai.py+schemas/ai.py、platform.ts/AgentDock.vue）；按用户授权把 tests/e2e_m3m4_test.py 账号更新为 13810000004/3/2 + Test@123456；空库迁移链验收通过（临时库 upgrade head 001→002→003：32 表/44 外键/8 处 FK 列 int，downgrade base 亦通，验后删库）；回归 compileall + verify_all 29/29（103 路径）+ pytest 143/143 + npm build + Docker E2E 80/80 + M5 mock 5/5 + M5 production 10/10（中文『跟进中』归一后 122 条全入 0 跳过、下钻同源 122 条真实数据、未来周期仍 40002）；销账：清单第 2 项（002 FK）与 seed 撞键 P2**；**v6.10.3（anhoa，2026-10-18；与 ZNBG 线 v6.10.3 复用，沿 v6.8.0 先例按线标签消歧）M2 解耦+开场白闭环：cs_agent_service.py 独立（ai_service.py 回归纯 M0 通用网关，M3/M4 延迟导入零改动，v6.8.8 类事故根除）、GET /cs/greeting+AgentDock 开窗欢迎语（路由 103→104，仅 public 分支）、Dify Chatflow yml v2 实时数据注入（HTTP×2 每轮拉 /courses+/events 含 id，根治 [RECOMMEND] 缺原料）；第九次同步 origin/master 732d43f ff 零冲突（seed_data 幂等+统一密码 Test@123456+4 固定账号）；pytest 143/143 + verify_all 29/29 + build + 浏览器实测全过**；**v6.10.4（anhoa，2026-10-18）M1 客户转留学生审批通过后身份转换（方案A）：M0 审批引擎审批通过后发布 approval.approved 事件，M1 客户模块订阅并处理 biz_type=convert 分支——user.user_type PROSPECT→STUDENT + customer.status→ENROLLED + 发布 customer.converted_to_student 事件；新增 services/customer_event_handlers.py、tests/e2e_convert_test.py；pytest 146/146 + verify_all 29/29 + e2e 12/12；未推送**；**v6.11.0（ZNBG，2026-10-18）M5 一期需求对齐改造（只改 M5 文件）：①画像四类独立（符合/部分符合/不符合/信息不足）+ 分母只计有研判客户 ②期末状态不可得（不用当前值冒充）③数据源失败改部分生成 ④下钻快照化（新表 ai_report_drill + 迁移 004）⑤投诉 AI 独立表 ticket_ai_analysis + 类型来源 + 待分析只计总量 + 特别案例一期 AI 判定 ⑥AI 改报告专用 Agent（未登记即不可用、不回落 mock）⑦前端周期选择/历史版本/月度对比/状态徽标/完整详情 ⑧新增 /reports/versions，下钻带 note ⑨保留归一与容错作防御 ⑩新增 docs/M5_上游接口契约.md；**v6.11.1/v6.11.2（ZNBG）Dify「智能报告」接入**：`DIFY_BASE_URL` 指向 `http://192.168.184.128`（.env + compose）；改用同名 Chatflow（advanced-chat，id 2598b21f…）并发布后 **blocking 实测 200、JSON 契约 PASS**；导出 DSL 至 dify/apps/；M5 加固 think 剥离（pytest 146/146）；剩余阻塞交 M0（config.py 加 DIFY_REPORT_AGENT_KEY、ai_service.py 加 AgentType.REPORT 与映射）；M2/M3/M4 Agent 未接入（key 仍占位）**；**v6.10.4（anhoa，2026-10-18）M1 客户转留学生身份转换（方案 A 事件总线）：M0 审批引擎发布 approval.approved（经用户同意）+ M1 订阅执行 PROSPECT→STUDENT/customer→ENROLLED，e2e 12/12 + pytest 146/146**；**v6.10.5（anhoa，2026-10-18）M2 客服 FAQ 应答修复：实测「公司简称是什么？」两入口（Dify 控制台/后端 chat）均无回答——Chatflow DSL 无知识检索节点而红线 1 要求以【知识库内容】为准恒落兜底、cs_faq 表依赖独立种子（seed_data.py 重建库会清空）；修复=dify/workflows/粤教客服Agent_chatflow.yml 升 v3（LLM system prompt 内嵌 37 条 FAQ 速查表逐字同源 cs_faq_seed.json + 红线 1 权威来源新增【FAQ 速查表】+ FAQ few-shot；契约/图结构/选择器零改动）+ cs_faq_seed.json 问法规范化（公司简称什么?→公司简称是什么？）+2 条 keywords + seed_cs_faq.py 升级按 question upsert+QUESTION_RENAMES 原位改名（重建库后必须补跑）+ 新增 tests/test_cs_faq_match.py 5 项（_match_faq 首次有覆盖）；pytest 151/151 + verify_all 29/29 + 接口实测 P5 命中 card_data.faq；**Dify 侧已落地（方案 B，控制台 API）**：`2f92093f`「粤教客服Agent-Chatflow」（backend key 所指）7 意图分支 prompt 全注入速查表（4302→9244 字符/支）并发布，实测「公司简称是什么？」答 简称"粤教服务"、"德国项目有哪些优势?"命中第 29 条、后端改写问法走 Dify 路径含粤教服务；`143c1127` 导入测试版顺带修复 kr 节点 `dataset_ids=[]` 空绑（绑 FAQ 库 01cd187d）+ 同套补丁已发布；改前备份 `dify/workflows/_vm_backup_v6.10.5/`**；**v6.11.3~v6.11.9（longtrying_test 线，2026-10-18/19）：v6.11.3 M3 成绩三件套（PUT /employee/scores/{id} + uq_student_score_unique 40901 + 口径 0-100 + 迁移 005）+ v6.11.4 REMOTE_ACCESS localtunnel 方案一 + v6.11.5 dify/apps 三 Agent DSL + v6.11.6 Dify 一体化打包（dify/docker/，dify_nginx/8081，客户拉代码即起）+ v6.11.7 DIFY_* 配置对齐（当时默认 mimo-v2.6-flash；v6.11.12 起模型默认值全空、不绑定任何特定模型）+ Dify部署与调用指南 + v6.11.8 dify-init 一键初始化（客户 dify/docker/.env 填模型 Key 全自动配供应商/导入 5 应用/绑模型/导出 app key，init 失败 backend 不启动）+ 合并 master 10 项公共模块（注册免审批=客户模块二期、approval.approved 事件总线 PROSPECT→STUDENT 自动转换、客服 FAQ 修复、CRM 画像、测评工具、前端 6 文件，pytest 157/157）+ v6.11.9 全文档 Dify 配置信息同步（现行基线 DIFY_BASE_URL 本机 8081/容器内 dify_nginx）**

**M5 一期口径与外部阻塞（v6.11.0~v6.11.2，2026-10-18）**：
- ✅ **已按需求文件改造**：画像四类（含「部分符合」）、期末状态标不可得、数据源部分生成、下钻快照、投诉 AI 独立表、报告专用 Agent、前端周期/版本/对比/徽标/完整详情。**口径以 `C:\Users\Windows\Desktop\M5_一期需求确认与执行提示词.md`（2026-10-18）为准，v6.10.1 的「4→3 映射」与「当前值推算」已被推翻**。
- 🔴 **阻塞（需他人改动，M5 不得越权）**：①M1 历史时点状态能力 ②M1/M3/M4 四个报告聚合接口（M5 现为直读表，属登记偏离）③M4 工单 6 字段 ~~④M0 补 4 行~~（✅ **v6.11.11 已落地**：config.py 加 `DIFY_REPORT_AGENT_KEY`、ai_service.py 加 `AgentType.REPORT` + `_AGENT_KEY_MAP` 映射，pytest 157/157）~~⑤Dify 侧建议补 Chatflow 的 system prompt 约束并降温~~（✅ **v6.11.15 已落地**：智能报告 Chatflow system prompt 补 JSON 契约约束 + temperature 0.2）。
- 📄 **新增文档**：`docs/M5_上游接口契约.md`（四份上游契约 + 阻塞清单）、`docs/Dify_接入与智能报告.md`（实例/应用/DSL/阻塞/上云合并）、`dify/apps/智能报告__advanced-chat.yml`（在用）与 `智能报告__agent-chat.yml`（留档）。

**M5 移交待办清单（v6.9.0，接手者从这里继续）**：
1. ✅ **环境级验收（v6.9.3 已实测完成）**：Docker E2E `tests/e2e_m3m4_test.py` **80/80**（含 Section 5.5 M5 报告链路 10 检查）；production 冒烟 `REPORT_DATA_SOURCE=production` 显式传「上一自然周」**7/7**（4/5 类 completed，complaint_weekly 按设计显式拒绝）。**但默认周期调用仅 2/7**——见第 6 项两条 P1，切 production 前必须先修（LOG-040）
2. ✅ ~~**转告 M0/M1/anho**：修 `migrations/versions/002_customer_approval.py` 4 处 FK 列 BigInteger→Integer~~ **v6.9.7 已修复（anhoa，2026-10-17）**：002 的 4 处 + 实测发现的 001 同类 4 处（sys_approval.initiator_id/approver_id、sys_operation_log.user_id、sys_notification.user_id，经用户批准「修类型保留表」）全部 BigInteger→Integer；另修 002.downgrade 的 FK/索引顺序缺陷（errno 1553/1828，先摘 FK 再删列）；空库 upgrade head + downgrade base + upgrade head 三步验收全过，ORM 逐列比对一致——**003 迁移空库验收阻塞解除，可切 `REPORT_DATA_SOURCE=production` 前置条件 +1（仍待清单第 4 项业务确认）**；遗留迁移漂移债见 LOG-045**；**longtrying_test 线：v6.10.0 种子数据规范化（random.seed(42) 可复现 + 统一密码 Test@123456 + 4 核心角色固定账号 13810000001~004 + AiReport version 递增）+ v6.10.2 第八次同步 master（M1/M2 全量并入，公共模块 7 项经批准，AgentType/AIService/ai_service 全保留验证，verify_all 29/29 + pytest 143/143 + 容器冒烟 32 表，新路由 /cs/faq 200 实测）**
3. ✅ ~~P1 缺陷 M3/M4 Agent 断链~~ **已修复**：v6.8.8 上游在 ai_service.py 尾部恢复 M0 网关符号（与 M2 客服 AiService 双服务共存），并随本次合并（eaaea94）进入本分支（LOG-031）
4. 🟡 **业务确认（M1 部分已闭环 2026-10-18，v6.10.1）**：`docs/M5_字段映射表.md` M1 三口径已拍板——期末状态一期接受「当前值推算」近似、4→3 维持保守映射、follow_up_summary 一期不取（映射表 4.2/4.3 有拍板记录，与 `_PROFILE_4_TO_3` 实现一致，零代码）；**余 M3/M4 部分（迟报口径、预警闭环、投诉 9 字段落库）待对应负责人** → 全部确认后才可切 `REPORT_DATA_SOURCE=production`
5. ✅ ~~ZNBG 分支本地提交未推送~~ **已推送**（v6.9.3 起本分支已同步远端；git 凭据本机已恢复，`git ls-remote` 免交互即通）
6. ✅ ~~两条 P1（v6.9.3 实测发现，M5，阻断切 production）~~ **v6.9.6 已修复**：a) 缺省周期改用 `default_completed_week(now)`=上一完整自然周 `[上周一00:00, 本周一00:00)`（原为 `week_range(now)` 恒落未来 → 必 40002）b) `normalize_customer_status()` 复用 M1 词表 `STATUS_CN_TO_EN` 做中英归一 + `fetch_customers` 逐行容错（脏行跳过并写入口径说明，不再拖垮 5 类报告）。**仍留 P2（他模块）**：`seed_data.py` ai_report 段秒级 DATETIME 随机碰撞（2 跑 1 败，共用脚本需确认）、前端 `RoleWorkspace.vue` 部分区块仍为静态演示值（管理层看板 183/21.4%/689/3.2%、学生首屏「李同学」与登录账号不符，作者 ge yuan，属 M3 看板区块）
7. ✅ ~~M5 报告 AI 只用模拟~~ **v6.9.5 已统一到共用网关**：`ReportAIService` 内部走 `model_ai_service`（共用模块名称），失败回落 mock；报告内容新增差异字段 `ai_source`（model/mock/unavailable）并与 `ai_status` 并存，PDF 头部/前端详情按来源标注；契约 §7 已同步。**v6.9.6 补**：三处下钻改为与报告**同源**（`_drilldown_dataset` 按 `data_source_status` 分流），前端「明细下钻」说明同步。**待办**：`DIFY_MODEL_API_KEY` 需在 `backend/.env` 配置后才可验证真实模型链路（当前自动回落 mock，不影响测试）；M3 `employee_service.py` 的 logger 导入为合并期最小修复，待 M3 负责人复审
**数据库**：34张表（含 M5 ai_report_drill、ticket_ai_analysis 等），107条路由路径（106 API + 1 health；含 M1 /crm/assessments/file），MVC分层结构就绪；Docker 数据库、Redis、后端服务按 compose 配置运行；数据库凭据见本机环境配置。
**测试账号（v6.10.0 起规范）**：核心角色固定 `username=手机号`——`13810000001` PROSPECT / `13810000002` STUDENT / `13810000003` EMPLOYEE / `13810000004` MANAGER，**密码统一 `Test@123456`**；其余 `user000~user115` 同密码（角色按 `i % 8` 确定：0=ADMIN、1=MANAGER、2~4=EMPLOYEE、5~6=STUDENT、7=PROSPECT）。`scripts/seed_data.py` 会 `drop_all+create_all` 重建全库（`random.seed(42)` 可复现），重跑前注意数据留存；Docker E2E 已按此规范更新账号常量
**主基线文档**：`promts/lon/提示词整合测试_demo/docs/基础架构方案_五人并行开发.md`（v1.2.0，28项决策）

**接手阅读顺序**：
1. 本文件（AGENTS.md）— 项目全貌、技术栈、环境搭建
2. `docs/项目需求文档.md` — 完整业务需求
3. `promts/lon/提示词整合测试_demo/docs/基础架构方案_五人并行开发.md` — **主基线，权重最高**
4. `docs/开发路线图.md` — 当前进度、下一步任务
5. `docs/接口契约v1.md` — API接口契约（v2.11.3，M3 成绩三件套 + v2.9.9 注册免审批反转/Dify 配置基线）
6. `docs/更新记录.md` — 最近变更（v6.11.13 Dify 1.16 环境实跑+dify_init.py 重写 + v6.11.9 全文档配置同步 + v6.11.5~8 Dify 一体化/dify-init + merge master 公共模块 + v6.11.3/v6.11.4）

**重要规则**：
- 主基线文档（基础架构方案）权重 > 其他参考文档（共用基座方案、公共框架等）
- 每次迭代完成后必须同步更新 docs/ 下全部6个文件
- 代码写完必须先测试验证，再报告完成

**开发硬性规则（所有人/Agent 接手后必须逐条遵守）**：
1. **文档同步**：每次执行完毕都要同步更新对应的 6 份文档——更新记录.md、AGENTS.md（根目录+docs副本）、接口契约v1.md、开发路线图.md、项目需求文档.md、运行日志.md，方便后续人员/新窗口接手（每个 Agent 和人开工前必须先读 AGENTS.md）
2. **必须测试**：每次执行完毕都要进行测试（本地快速验证优先：compileall + verify_all + 静态功能脚本；不优先启动 docker）
3. **先记录再推送**：测试没有问题，先把测试结果写入文档（更新记录.md「测试结果」行 + 运行日志），然后推送到 git 云仓分支
4. **分支绑定模块**：各自的分支接手各自的模块，其他人的模块不要动（longtrying=M3，longtrying_stu=M4，ZNBG/anhoa/architecture/研判等分支勿动）
5. **共用模块先确认**：如果改动影响到共用模块（M0 审批引擎/事件总线/AI网关/通知中心等），暂时绕过并主动提醒，经确认之后才可以动——否则会影响其他模块开发
6. **固定开发顺序**：开发 → 写入相应的文档（更新、agents等）→ 测试 → 测试问题修复 → 写入相应的文档（更新、agents等）→ 推送 git
7. **牢记硬性规则**：开发过程中随时对照本清单执行，不得跳步

---

## 一、项目概述

**项目名称**：粤教留学项目管理平台
**公司名称**：广东省教育服务有限公司（粤教服务）
**项目目标**：构建智能化教育服务管理平台，集成AI能力（Dify）+ 传统业务功能（Python后端）

**核心业务**：
1. 德国双元制职业教育项目
2. 新加坡国际本硕升学项目
3. 国际留学项目（全球）
4. 国际研学项目

---

## 二、技术栈

### 后端
- **框架**：FastAPI 0.109+
- **ORM**：SQLAlchemy 2.0+（异步）
- **数据库**：MySQL 8.0+（端口59000，库名GuangdongEducationStudyAbroadProgram）
- **数据库驱动**：aiomysql（异步MySQL驱动）
- **缓存**：Redis 7+
- **认证**：JWT（python-jose）
- **密码加密**：bcrypt（passlib）
- **Python版本**：3.11（锁定）
- **包管理**：uv（替代pip，速度快10-100倍）
- **依赖管理**：pyproject.toml + uv.lock（确保团队依赖版本一致）

### 前端
- **框架**：Vue 3.4+（Composition API）
- **语言**：TypeScript 5.3+
- **UI库**：Element Plus 2.5+
- **状态管理**：Pinia 2.1+
- **路由**：Vue Router 4.2+
- **HTTP**：Axios 1.6+

### AI能力
- **平台**：Dify 1.16.0-rc1
- **协议**：OpenAI协议接口
- **能力**：Agent编排、RAG知识库、工作流

### 部署
- **容器化**：Docker + Docker Compose
- **反向代理**：Nginx
- **对象存储**：一期本地磁盘（STORAGE_BACKEND=local，落盘 storage_data 卷，零外部依赖）；二期可选 MinIO/S3（STORAGE_BACKEND=s3，代码路径已保留）

---

## 三、项目结构

```
GuangdongEducationStudyAbroadProgram/
├── AGENTS.md                   # 项目接手指南（根目录，agent自动读取）
├── backend/                    # Python后端
│   ├── app/
│   │   ├── api/v1/            # API路由
│   │   ├── core/              # 核心模块（安全、异常、中间件）
│   │   ├── models/            # 数据模型（SQLAlchemy）
│   │   ├── schemas/           # Pydantic模型
│   │   ├── services/          # 业务逻辑
│   │   ├── repositories/      # 数据访问
│   │   └── utils/             # 工具函数
│   ├── migrations/            # 数据库迁移（Alembic）
│   ├── tests/                 # 测试
│   ├── .venv/                 # 虚拟环境（已加入.gitignore，不提交）
│   ├── pyproject.toml         # 依赖配置（替代requirements.txt）
│   ├── uv.lock                # 依赖锁定（提交，确保团队版本一致）
│   └── .python-version        # Python版本锁定（3.11）
│
├── frontend/                   # Vue前端
│   ├── src/
│   │   ├── api/               # API接口
│   │   ├── components/        # 组件
│   │   ├── views/             # 页面
│   │   ├── stores/            # Pinia状态
│   │   ├── router/            # 路由
│   │   └── types/             # TS类型
│   └── package.json
│
├── dify/                       # Dify配置
│   ├── workflows/             # Agent工作流
│   └── knowledge_base/        # 知识库文档
│
├── docs/                       # 项目文档
│   ├── AGENTS.md              # 本文件副本（与根目录AGENTS.md保持同步）
│   ├── 项目需求文档.md
│   ├── 更新记录.md
│   ├── 接口契约v1.md          # API接口契约（v2.0）
│   ├── 开发路线图.md
│   └── 运行日志.md
│
├── .gitignore                  # Git忽略配置
├── docker-compose.yml
└── nginx.conf
```

---

## 四、核心模块说明

### 4.1 用户角色

| 角色 | 编码 | 说明 | 账号来源 | 核心功能 |
|------|------|------|----------|----------|
| 意向客户 | `PROSPECT` | 陌生访客、意向客户，尚未与公司有业务往来 | 自行注册（功能权限需由员工开通） | 浏览课程/活动、提交咨询、活动报名 |
| 留学生 | `STUDENT` | 公司核心服务对象 | 员工申请 → 经理审批后转化 | 请假、考务查询、心理关怀、反馈提交、课程报名、进度追踪、生活支持、更多服务 |
| 员工 | `EMPLOYEE` | 公司工作人员（普通员工） | 管理层创建 | CRM录入/跟进（支持文字/PDF/照片/Word/Excel多格式）、代客户申请留学生（需经理审批）、审批学生流程、口述日报、成绩录入 |
| 管理层 | `MANAGER` | 公司管理人员（含经理/总裁） | 系统管理员创建（测试用）或其他管理层创建 | 全部客户查询、经营看板、智能报告、审批员工流程、员工管理、权限配置 |

**权限模型**：
- PROSPECT/STUDENT/EMPLOYEE：固定权限集
- MANAGER：基础权限 + `sys_user.permissions` JSON 字段中定义的额外权限（由系统管理员逐人配置）
- 系统管理员账号：仅测试用，不参与业务流程
- 意向客户自助注册即时生效（v6.11.5 起规则覆盖：注册即"正常"并可立即登录，原「待开通审批门」已移除——经用户批准并入 qianduan 线变更；`/auth/prospect/approve` 接口保留兼容历史审批实例）
- 员工审批学生流程（单层审批）；留学生转化需经理审批
- 员工数据隔离：普通员工只能看到自己名下的客户
- 二期拆分为3个独立角色：人事（HR，不可看客户/经营）、经理（MANAGER_DIRECTOR，只看下属+自己客户）、总裁（MANAGER_PRESIDENT，看全部）

### 4.2 数据库表（34张，v6.11.7更新）

> **数据库**：MySQL 8.0+，端口59000，库名 `GuangdongEducationStudyAbroadProgram`
> **自动建表**：应用启动时自动创建所有表，无需手动执行SQL

**公共基础表（M0管理）**：
1. **sys_user** - 统一用户表（含permissions JSON字段）
2. **sys_notification** - 站内消息表
3. **sys_event** - 事件总线表
4. **approval_instance** - 审批实例表（v6.0.0 双表设计）
5. **approval_task** - 审批任务表（v6.0.0 双表设计）
6. **sys_operation_log** - 操作日志表

**客户主数据表（v6.0.0 新增）**：
7. **customer** - 客户主表（全系统客户主数据，手机号为业务唯一键）
8. **pending_lead** - 待补全线索表（微信号等无手机号）

**客户模块表（M1）**：
9. **crm_lead** - 线索表（v6.0.0 改为引用 customer）
10. **customer_assessment** - 客户研判记录表
11. **crm_follow_up** - 客户跟进记录表（v6.0.0 改为引用 customer）

**客服模块表（M2）**：
12. **course_project** - 课程与项目表（公共共用，M2维护）
13. **event_lecture** - 活动与讲座表（公共共用，M2维护）
14. **event_registration** - 活动报名表
15. **cs_chat_session** - 客服会话表
16. **cs_chat_message** - 客服消息表
17. **cs_intent_log** - 意图/转化日志表
18. **cs_faq** - 常见问答对表
18a. **cs_recommend_log** - 推荐日志表（v6.9.0 新增：课程/活动推荐逐条落库，session_id/customer_id/course_id/event_id/recommendation_type/item_name）

**员工模块表（M3）**：
19. **employee_daily_report** - 员工日报表（v6.3.0 加 status/is_late）
20. **student_score** - 学生成绩表
21. **employee_org** - 组织架构表
22. **employee_todo** - 员工待办事项表
23. **daily_report_annotation** - 日报批示表（v6.4.0 新增）

**学生模块表（M4）**：
24. **student_admin_service** - 学生行政服务表
25. **student_psych_profile** - 心理健康画像表
26. **student_psych_alert** - 心理预警表
27. **student_feedback_ticket** - 售后反馈工单表
28. **student_academic** - 学生学业考务表
29. **student_application_progress** - 留学申请进度表

**报告模块表（M5）**：
30. **ai_report** - 智能报告表
31. **ai_report_attachment** - 报告附件表
32. **ai_report_drill** - 报告下钻快照表（v6.11.0）
33. **ticket_ai_analysis** - 投诉工单 AI 分析结果表（v6.11.0）

### 4.3 API接口分组

- `/api/v1/auth/*` - 认证相关
- `/api/v1/users/*` - 用户管理
- `/api/v1/customers/*` - 客户主数据管理（v6.0.0新增）
- `/api/v1/students/*` - 学生服务
- `/api/v1/employees/*` - 员工服务
- `/api/v1/crm/*` - CRM客户管理
- `/api/v1/courses/*` - 课程项目
- `/api/v1/events/*` - 活动管理
- `/api/v1/ai/*` - AI服务（统一网关，禁止直连Dify）
- `/api/v1/approvals/*` - 审批引擎（v6.0.0 升级双表设计）
- `/api/v1/notifications/*` - 通知中心
- `/api/v1/files/*` - 文件存储
- `/api/v1/cs/*` - 公开客服（v6.9.0：/cs/faq 公开FAQ、/cs/sessions/{id}/messages 会话历史；对话入口为 /ai/customer-service/chat）
- `/api/v1/reports/*` - 智能报告（M5，v6.8.5 合并 master 引入；与 `/employee/reports` 员工日报区分）

### 4.3.1 模块划分与职责边界（v5.0.0新增）

> 详见 `promts/lon/提示词整合测试_demo/docs/基础架构方案_五人并行开发.md`

| 模块 | 核心职责 | 对外查询接口（供M5报告取数） |
|------|---------|---------------------------|
| **M0 公共基础设施** | 认证鉴权、统一响应/异常、AI网关、事件总线、审批引擎、通知中心、文件存储、数据权限 | - |
| **M1 客户模块** | 客户主数据管理、画像研判、线索跟进、6态状态流转 | `GET /api/v1/customers/{id}`, `GET /api/v1/customers` |
| **M2 客服模块** | 7大场景对话、知识库RAG、活动报名闭环、转线索 | `GET /api/v1/cs/courses`, `GET /api/v1/cs/events` |
| **M3 员工模块** | CRM管理、日报、成绩、审批、口述日报 | `GET /api/v1/employee/reports`, `GET /api/v1/employee/reports/summary` |
| **M4 学生模块** | 请假、心理关怀、售后反馈、学业考务 | `GET /api/v1/student/psych/stats`, `GET /api/v1/student/tickets/stats` |
| **M5 报告模块** | 5类报告生成、经营看板 | **v6.8.5 已实现**（合并 master：7 paths，一期 mock 数据，口径见 promts/智能报告/report_package） |

**模块间解耦原则**：
- 模块间业务流转走事件总线（`sys_event`），不直接import对方service
- 报告模块只调各模块暴露的查询接口，不直接查别人的表
- 所有模块共用M0的AI网关，禁止直连Dify

### 4.4 AI Agent（3个，均置顶显示）

1. **智能客服Agent** — 公开主页置顶，7大场景智能应答 + 主动信息采集 + 年轻化人设
2. **企业智能助手Agent** — 员工端置顶，CRM管理、口述日报整理、待办提醒、指令式处理（需二次确认）、权限感知（员工/管理层不同能力）
3. **学生智能助手Agent** — 留学生端置顶，行政服务代办、心理关怀（限制预期：不承诺退费/不给出医疗级建议）、学业提醒、主动推送

### 4.5 页面结构概览

**公开主页（无需登录）**：
- 公司介绍、业务展示、课程/活动浏览、留学政策、FAQ
- 注册/登录入口
- 智能客服Agent窗口（右下角置顶）

**员工端（登录后）**：
- 普通员工：工作台 → CRM录入/查询 → 代客申请 → 审批学生 → 成绩录入 → 口述日报 → 组织架构 → 新人指引 → 待办 → 个人信息
- 管理层（一期）：经营看板 → 全部客户 → 智能报告(5类) → 审批中心 → 用户管理 → 权限配置 → 个人信息
- 企业智能助手Agent窗口（右下角置顶）

**留学生端（登录后）**：
- 工作台 → 请假 → 心理关怀 → 售后反馈 → 学业考务 → 进度追踪 → 生活支持 → 更多服务 → 个人信息
- 学生智能助手Agent窗口（右下角置顶）

### 4.6 关键业务规则

**客户信息采集**：
- 三渠道：意向客户自行注册 / 员工录入（多格式：文字/PDF/照片/Word/Excel） / 管理层录入
- 有效性判断：电话号码为唯一有效性标准，有电话号码=有效线索，无联系方式=仅记录咨询日志
- 客户去重：按电话号码去重，先录入的员工获得跟进权；管理层可变更归属
- 研判结果：仅员工和管理层可见，意向客户和留学生不可查看

**审批流程**：
- 学生请假等流程：负责的员工单层审批
- 意向客户→留学生转化：员工申请 → 经理审批

**消息通知**：站内消息 + Agent主动推送（学生登录后）

**活动报名**：必须注册登录后才可报名，未登录跳转登录页，登录后跳回继续

**指令式业务处理**：Agent执行前需二次确认

### 4.7 一期/二期范围

**一期（核心业务闭环，15周）**：
- 公开主页 + 智能客服Agent
- 员工端（CRM/审批/日报/成绩）+ 企业助手Agent
- 管理层端（看板/报告/审批/权限配置）
- 留学生端（7个子模块）+ 学生助手Agent
- 4个业务角色：PROSPECT/STUDENT/EMPLOYEE/MANAGER

**二期（扩展功能）**：
- 人事模块拆分（独立HR角色）
- 经理/总裁拆分（MANAGER_DIRECTOR + MANAGER_PRESIDENT）
- 专业心理测评量表
- NL2SQL增强
- 语音输入增强

### 4.8 已确认的设计决策

| # | 决策 |
|---|------|
| 1 | 电话号码为客户信息唯一有效性标准 |
| 2 | 客户研判结果页面可见（员工+管理层） |
| 3 | 一期用AI对话式情绪评估，二期引入专业量表 |
| 4 | 学生界面用"更多服务"替代"增值转化" |
| 5 | 一期人事并入MANAGER，二期拆分 |
| 6 | 新增customer客户主表，crm_lead改为引用customer_id（v6.0.0） |
| 7 | 审批引擎升级为双表设计：approval_instance + approval_task（v6.0.0） |
| 8 | 保持code:200响应码风格（v6.0.0） |
| 9 | 图片OCR二期实现，一期不做（v6.0.0） |
| 10 | 保持EMPLOYEE/MANAGER/ADMIN三角色体系，按主文件来（v6.0.0） |
| 11 | 单Vue应用，通过路由守卫区分三端（v6.0.0） |
| 12 | 保持5位HTTP风格错误码（v6.0.0） |

---

## 五、开发环境搭建

### 5.1 后端（使用 uv 管理 Python 虚拟环境）

> **重要**：本项目使用 `uv` 替代传统的 `pip + venv`，速度更快、依赖管理更可靠。
> 所有团队成员必须使用相同的 Python 版本（3.11）和依赖版本（通过 uv.lock 锁定）。

#### 第一步：安装 uv

**Windows（PowerShell，以管理员身份运行）**：
```powershell
irm https://astral.sh/uv/install.ps1 | iex
```

**Mac/Linux**：
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**验证安装成功**：
```bash
uv --version
# 应输出版本号，如：uv 0.12.14
```

#### 第二步：克隆项目并进入后端目录

```bash
git clone http://47.106.207.27:3000/longtrying/GuangdongEducationStudyAbroadProgram.git
cd GuangdongEducationStudyAbroadProgram/backend
```

#### 第三步：安装 Python 3.11

```bash
uv python install
```

> 说明：uv 会读取 `backend/.python-version` 文件（内容为 `3.11`），自动安装对应的 Python 版本。
> 如果已安装会跳过，不会重复安装。

**验证**：
```bash
uv python list
# 应看到 3.11.x 版本标记为已安装
```

#### 第四步：创建虚拟环境并安装依赖

```bash
uv sync
```

> 说明：这一步会做三件事：
> 1. 在 `backend/.venv/` 创建虚拟环境（Python 3.11）
> 2. 根据 `pyproject.toml` 安装所有依赖
> 3. 生成/更新 `uv.lock` 锁定文件（确保团队依赖版本完全一致）

**验证**：
```bash
.venv/Scripts/python --version    # Windows
# 或 source .venv/bin/python --version  # Mac/Linux
# 应输出：Python 3.11.x

uv pip list
# 应看到所有已安装的依赖包列表
```

#### 第五步：激活虚拟环境

**Windows**：
```bash
.venv\Scripts\activate
```

**Mac/Linux**：
```bash
source .venv/bin/activate
```

**验证激活成功**（命令行前面会出现 `(base)` 或 `.venv` 标识）：
```bash
python --version
# 应输出：Python 3.11.x

pip list
# 应看到所有已安装的依赖包
```

#### 第六步：配置环境变量

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑 .env 文件，填写实际配置
# 必须配置的项：
#   DATABASE_URL - MySQL数据库连接地址（端口59000，库名GuangdongEducationStudyAbroadProgram）
#   REDIS_URL - Redis连接地址
#   SECRET_KEY - JWT密钥（请用随机字符串）
#   DIFY_BASE_URL - Dify API 地址（v6.11.6 起一体化打包：本机 http://localhost:8081，容器内由 compose 覆盖为 http://dify_nginx）
#   DIFY_*_AGENT_KEY - 各Agent的API Key（app-开头；dify-init 启动时自动创建应用并输出到 dify/docker/app_keys.txt，复制回填即可）
#   STORAGE_BACKEND - 文件存储后端：local（默认，本地磁盘）/ s3（MinIO，二期可选）
```

#### 第七步：启动开发服务器

```bash
# 确保 MySQL 已启动且数据库 GuangdongEducationStudyAbroadProgram 已创建
# 应用启动时会自动创建所有17张表，无需手动执行迁移
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**验证**：浏览器访问 http://localhost:8000/docs ，应看到 FastAPI 自动生成的 API 文档页面。

#### 日常开发命令速查

| 操作 | 命令 | 说明 |
|------|------|------|
| 激活虚拟环境 | `.venv\Scripts\activate` (Win) / `source .venv/bin/activate` (Mac/Linux) | 每次打开新终端都要执行 |
| 添加生产依赖 | `uv add <包名>` | 自动更新 pyproject.toml 和 uv.lock |
| 添加开发依赖 | `uv add --dev <包名>` | 如 pytest、black 等 |
| 同步依赖 | `uv sync` | 拉取代码后执行，确保依赖一致 |
| 查看已安装依赖 | `uv pip list` | - |
| 代码格式化 | `black app/` | - |
| 代码检查 | `ruff check app/ --fix` | - |
| 运行测试 | `pytest` | - |
| 退出虚拟环境 | `deactivate` | - |

#### 常见问题排查

**Q: `uv sync` 报错 "Unable to determine which files to ship"**
A: 确保 `backend/app/__init__.py` 文件存在。

**Q: 激活虚拟环境后 `python --version` 不是 3.11**
A: 删除 `.venv/` 目录，重新执行 `uv sync`。

**Q: 依赖冲突怎么办？**
A: 删除 `uv.lock` 和 `.venv/`，重新执行 `uv sync`。

**Q: 拉取代码后项目跑不起来？**
A: 执行 `uv sync` 同步依赖（可能有人添加了新依赖）。

**Q: Windows 下激活脚本报错 "无法加载文件，因为在此系统上禁止运行脚本"？**
A: PowerShell 以管理员身份运行：`Set-ExecutionPolicy RemoteSigned`，然后重新激活。

### 5.2 前端

```bash
# 1. 进入前端目录
cd frontend

# 2. 安装依赖
npm install

# 3. 配置环境变量
cp .env.example .env

# 4. 运行开发服务器
npm run dev

# 5. 访问页面
# http://localhost:5173
```

### 5.3 Dify（**v6.11.9 起一体化部署与初始化**）

Dify（1.16.0-rc1）已作为子 compose 纳入项目，随 `docker compose up -d` 启动。先将 `dify/docker/.env.example` 复制为本地 `dify/docker/.env`，再配置模型 API Key、管理员密码及 Dify 内部服务强密钥；本地 `.env` 和 app keys 均不入库。**v6.11.8 新增 `dify-init` 服务**；**v6.11.13 重写为 Dify 1.16 Console API 适配版**（base64 密码+cookie/CSRF、插件制供应商 marketplace 安装+轮询、模型凭据实时校验、advanced-chat 导入后 publish、agent-chat 创建+model-config、草稿工作流 hash 补丁重绑模型）：自动完成管理员创建/登录、模型供应商插件安装、模型凭据添加、应用导入/创建、模型绑定、app key 写入受限共享卷 `dify_app_keys` 供 backend 启动时自动加载，客户全程无需进入 Dify 控制台。

> 📖 **完整配置说明、调用规则、降级机制、失败排查见 [Dify部署与调用指南.md](./docs/Dify部署与调用指南.md)**

```bash
# 一体化启动后，Dify 相关服务自动运行：
#   dify-init（一次性初始化容器，成功后退出）
#   dify_nginx（控制台入口，端口 8081）
#   api / worker / worker_beat / web / sandbox / plugin_daemon / agent_backend / local_sandbox
#   db_postgres（Dify 元数据库）/ dify_redis / weaviate（向量库）/ ssrf_proxy

# 控制台入口：http://localhost:8081
# 首次配置：Copy-Item dify/docker/.env.example dify/docker/.env，再按 docs/Dify部署与调用指南.md 设置强密钥
# 管理员：由本机 dify/docker/.env 中 DIFY_ADMIN_EMAIL / DIFY_ADMIN_PASSWORD 自动创建
# 模型默认值：Mimo；DIFY_MODEL_BASE_URL / DIFY_MODEL_NAME 可按需改为其他 OpenAI-compatible 模型
```

> ⚠️ **外部模型需自行配置（不绑定任何特定模型）**：模型供应商为 OpenAI-API-compatible 通用协议，`DIFY_MODEL_API_KEY` / `DIFY_MODEL_BASE_URL` / `DIFY_MODEL_NAME` 三项**默认全空**，由客户按自己所用的服务商填写（API Key 属于客户凭据，未入库）。填好后 `docker compose up -d` 由 dify-init 自动完成全部配置。

#### 5.3.1 接手者 AI 配置清单（v6.11.9 自动化版）

> 后端服务 + Dify + dify-init 均随 `docker compose up -d` 自动启动。dify-init 失败则 backend 不启动（长期挂载，配置必须完整）。

| 步骤 | 操作 | 说明 |
|------|------|------|
| ① 填写模型配置 | 编辑 `dify/docker/.env`，填入 `DIFY_MODEL_API_KEY` / `DIFY_MODEL_BASE_URL` / `DIFY_MODEL_NAME`（三项必填，默认留空） | OpenAI-API-compatible 通用协议，key/url/模型名由客户自定义，**不绑定任何特定模型**；API Key 勿入库 |
| ② 启动全部服务 | `docker compose up -d` | dify-init 自动（v6.11.14）：创建管理员→装模型插件→配供应商→注册自定义模型→导入 5 个 yml（占位符注入）→绑定模型→发布工作流→输出 app key |
| ③ 查看 init 日志 | `docker compose logs -f dify-init` | 成功标志：`🎉 Dify 初始化全部完成` |
| ④ 回填 app key | app key 由 dify-init 写入 `dify_app_keys` 共享卷，backend 启动时自动加载（无需手动复制） | `DIFY_CUSTOMER_AGENT_KEY` / `DIFY_EMPLOYEE_AGENT_KEY` / `DIFY_STUDENT_AGENT_KEY` / `DIFY_REPORT_AGENT_KEY`（留档版不回填） |
| ⑤ 重启 backend | `docker compose restart backend` | 使 app key 生效 |
| ⑥ 验证 AI | 调用任一 AI 端点，确认返回 `source: "dify"` | 如返回 `fallback` 则检查 app key 是否回填正确 |

> **降级说明**：Dify 不可用时 AI 端点走三级降级（Dify Agent → 直连模型 → 本地话术），不影响核心业务。dify-init 失败排查见 [Dify部署与调用指南.md 第七章](./docs/Dify部署与调用指南.md#七dify-init-失败排查)。

### 5.4 Docker一键启动

```bash
# 启动全部服务（mysql + redis + backend + nginx + Dify 全套）
docker compose up -d

# 只启动核心三件套（不需要 Dify/AI 时，省资源）
docker compose up -d mysql redis backend

# 查看日志
docker compose logs -f backend

# 停止服务
docker compose down

# 上传文件持久化位置：命名卷 backend_storage（容器内 /app/storage_data）
docker volume inspect guangdongeducationstudyabroadprogram_backend_storage
```

---

## 六、关键配置文件

### 6.0 环境特异配置清单（接手必读，先看这里再改代码）

> **核心原则：环境特异配置 = 每台机器/每个人不一样的东西，禁止把某个人电脑上的具体值硬编码入库**（真实教训：v6.10.3 合并曾把成员内网 IP 写进 docker-compose.yml，v6.10.4 修复并记 LOG-060）。

**接手第一步：按下面清单逐项检查并改成你自己的值**

| 配置项 | 位置 | 该填什么 | 常见错误 |
|--------|------|----------|----------|
| `DATABASE_URL` | backend/.env、docker-compose.yml | 你本机 MySQL 地址与密码 | 直接沿用别人的密码导致连不上库 |
| `REDIS_URL` | backend/.env、docker-compose.yml | 你本机 Redis 地址 | - |
| `SECRET_KEY` | backend/.env | 随机字符串（自行生成） | 沿用仓库示例值上线 |
| `DIFY_BASE_URL` | backend/.env、docker-compose.yml | **本机：`http://localhost:8081`；Docker 容器内：`http://dify_nginx`**（v6.11.6 起 Dify 一体化打包，勿再用 host.docker.internal/3000/旧内网 IP） | ❌ 写成其他成员的内网 IP（如 192.168.x.x）或旧 VM 地址——你的机器上必不通 |
| `DIFY_*_AGENT_KEY` | backend/.env（不入库，.env 已 gitignore） | dify-init 自动输出到 `dify/docker/app_keys.txt`，复制四个业务 Agent key 回填 | 直接用别人的 key（对方撤销后全体失效） |
| `DIFY_MODEL_API_KEY` / `DIFY_MODEL_BASE_URL` / `DIFY_MODEL_NAME` | dify/docker/.env（模型供应商） | 你自己的模型配置（任一 OpenAI-API-compatible 服务，key/url/模型名全部客户自定义，**三项默认全空、不绑定任何特定模型**），dify-init 自动配供应商 | 任一项填错/留空 → dify-init 失败，backend 不启动 |
| `STORAGE_BACKEND` | backend/.env、docker-compose.yml | 一期默认 `local` | - |
| `VITE_API_BASE_URL` | frontend/.env | 本机 `http://localhost:8000/api/v1`；生产构建用相对路径 `/api/v1`（.env.production 已配） | 指到别人的机器 |

**规则**：
1. docker-compose.yml / 代码里只允许出现**通用别名**（localhost、compose 服务名 mysql/redis/dify_nginx），具体 IP 一律不入库
2. 个性化值放 `.env`（已 gitignore）或 `.env.example` 只放占位符
3. 合并公共 compose/config 后，先检查环境变量类差异（IP/端口/URL）再启动，别只做代码冒烟
4. 不确定某配置是不是环境特异 → 按环境特异处理

### 6.1 后端环境变量（.env）

```bash
# 数据库（MySQL 8.0+，端口59000）
DATABASE_URL=mysql+aiomysql://root:your_password@localhost:59000/GuangdongEducationStudyAbroadProgram

# Redis
REDIS_URL=redis://localhost:6379

# JWT
SECRET_KEY=your-secret-key-here
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# Dify（版本1.16.0-rc1，Service API：/v1/chat-messages，v6.11.6 起一体化打包）
# 本机 http://localhost:8081（Dify 控制台+Service API 同端口）；容器内 http://dify_nginx
DIFY_BASE_URL=http://localhost:8081
DIFY_VERSION=1.16.0-rc1
DIFY_API_PROTOCOL=openai
DIFY_STUDENT_AGENT_KEY=app-xxx
DIFY_EMPLOYEE_AGENT_KEY=app-yyy
DIFY_CUSTOMER_AGENT_KEY=app-zzz
# 三个 key 来源：dify-init 输出的 dify/docker/app_keys.txt（勿提交）

# 直连模型降级（可选）：Dify Agent 不可用时直连 OpenAI-API-compatible 模型兜底
# 三项默认全空（不绑定任何特定模型），启用时由客户自定义填写
DIFY_MODEL_API_KEY=
DIFY_MODEL_BASE_URL=
DIFY_MODEL_NAME=

# 文件存储（local=本地磁盘，默认零外部依赖；s3=MinIO，仅二期生产需要时切换）
STORAGE_BACKEND=local
STORAGE_LOCAL_DIR=./storage_data
# 以下仅 STORAGE_BACKEND=s3 时生效
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=admin
MINIO_SECRET_KEY=password
MINIO_BUCKET=education
```

### 6.2 前端环境变量（.env）

```bash
VITE_API_BASE_URL=http://localhost:8000/api/v1
```

---

## 七、开发规范

### 7.1 Git规范

**分支**：
- `master` - 主干（**2026-10-17 四次合并：cba3303（v6.5.0+v6.6.0）→ 62d4cff（v6.7.0~v6.7.2+硬性规则）→ a23fc49（v6.8.2~v6.8.5 全量：M4 学生模块+Docker E2E+存储本地化+M5 智能报告+前端界面+口径统一）→ e6c06d0（anhoa 并入：M1 客户模块+M2 客服 Agent v6.8.0 一期补齐+v6.8.6 AI 全链路+v6.8.7 前端修复，快进无冲突）**；保护分支已解除，当前可直推）
- `longtrying` - 开发分支（M3 员工模块，已全部收官并合入 master）
- `longtrying_stu` - 开发分支（**M4 学生模块，2026-10-17 从 longtrying e3b0160 新建**；v6.8.2~v6.8.5 全量工作已合入 master a23fc49）
- `develop` - 开发（预留）
- `feature/*` - 功能
- `fix/*` - 修复
- 其他成员分支：ZNBG / anhoa / architecture / 研判 等（勿动他人分支）

**longtrying → master 合并流程**（实测记录见运行日志 LOG-007）：
```
git fetch gitea
git checkout master
git merge --ff-only gitea/master          # 1. 先同步远端 master 最新
git merge longtrying -X theirs --no-edit  # 2. 合并（冲突以 longtrying 为准；站在 master 上，theirs=longtrying）
git push gitea master                     # 3. 推送
git checkout longtrying                   # 4. 切回开发分支
```

**Commit格式**：
```
feat: 新功能
fix: 修复
docs: 文档
style: 格式
refactor: 重构
perf: 性能
test: 测试
chore: 构建
```

### 7.2 代码规范

**Python**：
- 遵循PEP 8
- 使用类型提示
- black格式化
- ruff lint检查

**Vue**：
- Composition API
- TypeScript严格模式
- ESLint + Prettier

### 7.3 统一响应格式

```json
{
    "code": 200,
    "message": "success",
    "data": {},
    "timestamp": 1697270400
}
```

### 7.4 错误码

| 错误码 | 说明 |
|--------|------|
| 200 | 成功 |
| 40001 | 用户名或密码错误 |
| 40002 | 参数验证失败 |
| 40003 | 账号已被禁用 |
| 40004 | 用户名已存在 |
| 40006 | 账号待开通 |
| 40101 | 未登录或Token过期 |
| 40301 | 无权限 |
| 40901 | 数据冲突（客户重复录入） |
| 50001 | 服务器错误 |

---

## 八、常见问题

### Q1: 数据库连接失败？

检查：
1. MySQL是否启动（端口59000）
2. DATABASE_URL配置是否正确
3. 数据库 `GuangdongEducationStudyAbroadProgram` 是否已创建
4. 用户名密码是否正确
5. MySQL字符集是否为utf8mb4

### Q2: Dify接口调用失败？

检查：
1. DIFY_BASE_URL是否正确（本机 `http://localhost:8081`；容器内 `http://dify_nginx`。v6.11.6 起 Dify 一体化打包，**不是 3000、不是 host.docker.internal、不是旧内网 IP**）
2. API Key是否正确（app-开头；dify-init 输出在 `dify/docker/app_keys.txt`，复制回填 backend/.env 后重启 backend）
3. Agent应用是否已发布（`docker compose logs dify-init` 看导入/绑定是否成功）
4. 网络是否可达（容器内验证：docker exec edu-backend python -c "import socket;socket.create_connection(('dify_nginx',80))"）
5. Key 未配置/AI 不可用时系统自动降级：agent/chat 返回能力清单话术，commands/parse 走本地规则兜底（source=local），不阻断业务

### Q3: 前端跨域问题？

开发环境：vite.config.ts配置proxy
生产环境：Nginx反向代理

### Q4: Token过期怎么处理？

前端拦截器会自动跳转到登录页，用户重新登录即可。

---

## 九、重要联系人

| 角色 | 姓名 | 联系方式 |
|------|------|----------|
| 项目负责人 | 待定 | - |
| 后端开发 | 待定 | - |
| 前端开发 | 待定 | - |
| AI工程师 | 待定 | - |
| 测试工程师 | 待定 | - |

---

## 十、文档索引

| 文档 | 路径 | 说明 |
|------|------|------|
| **AGENTS.md** | **./AGENTS.md**（根目录） | **项目接手指南（agent自动读取，这是主文件）** |
| AGENTS.md 副本 | docs/AGENTS.md | 与根目录保持同步的副本 |
| 项目需求文档 | docs/项目需求文档.md | 完整需求、架构、接口、数据库 |
| 更新记录 | docs/更新记录.md | 版本变更记录（当前 v6.9.0 anhoa M2 二期 + 主线 v6.8.6/v6.8.7 条目） |
| 开发路线图 | docs/开发路线图.md | 分期任务表（Phase 0已完成，M3 收官，M1/M2 v6.8.0 补齐，M4/M5 后端已交付，AI 已接通） |
| 运行日志 | docs/运行日志.md | 排查记录与教训（当前 LOG-025） |
| 测试报告 | docs/测试报告_v6.8.2_M3M4端到端.md | v6.8.2 Docker E2E 69/69 检查明细+7项缺陷+7轮迭代留档 |
| 接口契约v2 | docs/接口契约v1.md | API接口契约（v2.11.6，34张表，107路由路径=106 API+1 health） |
| **基础架构方案** | **promts/lon/提示词整合测试_demo/docs/基础架构方案_五人并行开发.md** | **主基线文档（v1.2.0，28项决策），所有参考文档权重低于此文件** |

> **文档优先级**：基础架构方案_五人并行开发.md > 其他参考文档（共用基座方案、公共框架等）
> **接手顺序**：本文件 → 项目需求文档 → 基础架构方案 → 开发路线图 → 接口契约

---

## 十一、接手检查清单

新接手项目时，按顺序检查：

- [ ] 阅读本文件（AGENTS.md）
- [ ] 阅读项目需求文档
- [ ] 查看开发路线图，了解当前进度
- [ ] 查看更新记录，了解最近变更
- [ ] 查看运行日志，了解已知问题
- [ ] 安装 uv（参考 5.1 节第一步）
- [ ] 进入 `backend/` 目录，执行 `uv python install` 安装 Python 3.11
- [ ] 执行 `uv sync` 创建虚拟环境并安装依赖
- [ ] 激活虚拟环境，验证 `python --version` 输出 3.11.x
- [ ] 配置 `.env` 环境变量
- [ ] 启动开发服务器，访问 http://localhost:8000/docs 验证
- [ ] 阅读核心代码，理解架构
- [ ] 联系项目负责人，了解背景

---

**最后更新**：2026-10-19（**v6.11.13 第十次同步 origin/master→master_ZNBG（ZNBG）**：合并 `55c7b81..38f396d`（上游 v6.11.10 配置审计 + v6.11.11 **M0 4 行补丁落地**——config `DIFY_REPORT_AGENT_KEY` + `AgentType.REPORT`/映射，经用户批准；**M5 阻塞 B5 销账**）+ 本机线 v6.11.9~v6.11.12（Dify 一体化打包基线/文档同步/本机环境修复/首启失败记录）先行提交保护后并入；**代码冲突 2 处按上游登记解决**（config.py/dify_init.py——本地 v6.11.10 曾移除 REPORT 登记，上游 v6.11.11 经批准重新登记，以最后决策为准）+ AGENTS.md 阻塞清单④销账；**M5 配套一行修**：报告 AI 调用 session 由动态串改 `"new"`（网关 `session!="new"` 即作 conversation_id 发送，动态串必 400；v6.11.6 同因实测结论），并同步过期注释；冲突 docs 按线标签消歧（双方 v6.11.9/10/11 同号异义并存）；生效仍差一步：`backend/.env` 回填报告 key（dify-init 导出 dify/docker/app_keys.txt），未回填恒 unavailable；回归 compileall + verify_all **29/29** + pytest 全过 + alembic 单头；详见更新记录 v6.11.13 与 LOG-071（ZNBG））

**上一版记录（v6.11.11，origin/master 线）**：2026-10-19（**M0 4 行补丁落地：智能报告 Agent 登记（经用户批准）**——config.py/ai_service.py/.env.example/dify_init.py 注释/调用指南 5 处，pytest **157/157**，阻塞清单④销账；不填 key 行为不变恒 unavailable）

**上一版记录（v6.11.11，ZNBG 本机线，同号异义）**：2026-10-19（本机环境修复：backend/.env 密码 password→420821；运行库 alembic stamp 004 后 upgrade head 只补跑 005 保留全部数据（student_score 104→97 清 7 条重复）；Dify 指向切打包基线（根 .env=dify_nginx、backend/.env=localhost:8081）；已下线 REPORT key 注释保留；verify_all 29/29）

**上一版记录（v6.11.12，ZNBG 本机线）**：2026-10-19（一体化 Dify 栈首启实测失败（exit 1）记录：A dify/docker/.env 精简模板空值行致 api ValidationError 全容器 Restarting；B compose backend command 依赖 /run/dify-keys/app_keys.env 但 volumes 缺 dify_app_keys 挂载；按用户决定**暂不修复、仅记录**；业务侧旧拓扑 4 容器可用；详见 LOG-070（ZNBG）与路线图移交清单第 25 项）

**上一版记录（v6.11.10，origin/master 线，同号异义）**：2026-10-19（交付前全面配置审计：5 类滞留修复（REMOTE_ACCESS 一体化说明/文档索引版本/进度行补 v6.11.3~9/Dify_接入与智能报告旧 VM 值标注/M5 上游契约 §5.2 历史标注），纯文档）

**上一版记录（v6.11.10，ZNBG 本机线，同号异义）**：2026-10-19（同步 origin/master 文档基线并按用户逐项确认处理共用模块：M0 移除 REPORT Agent 登记、M5 报告调用恢复动态 session ID、模型默认切 Mimo——**REPORT 登记已由上游 v6.11.11 经批准重新落地，本条决策被取代**）

**上一版记录（v6.11.4 上游三笔：qianduan + longtrying_test）**：2026-10-18（①访客 PROSPECT 注册免审批（v6.11.3 规则覆盖：注册即"正常"并可立即登录，注册成功即发布 customer.registered 并创建 customer 主数据，pytest 144/144 + npm build + 注册 200 后立即登录 200）②学生端留学申请进度布局紧凑化（内容不变）③REMOTE_ACCESS.md 补 localtunnel 方案一与 503 已知问题（原方案顺延二/三/四））

**上一版记录（v6.11.4，ZNBG 第八次同步）**：2026-10-18（**第八次同步 origin/master→master_ZNBG**：合并 `107f256..beb0b4e`（5 提交，longtrying_test 线）——M3 成绩三件套 v6.11.3（PUT /employee/scores/{id} + student_score 唯一约束 40901（semester 归一空串）+ 0-100 口径 + 迁移 005 清理 4 条存量重复）+ AGENTS.md §6.0 环境特异配置清单 + compose DIFY_BASE_URL 回通用别名；**共用文件经用户批准「插值方案」处理**：compose 改 `${DIFY_BASE_URL:-http://host.docker.internal}`（默认合规 §6.0），本机根 .env（gitignore）配 VM 地址覆盖，`docker compose config` 实测解析 `http://192.168.184.128`，M5 Docker 内真实 AI 不断、其他成员零影响；迁移链线性单头（005 down_revision=我方 004）；M0 零改动（AgentType/AIService/ai_service 不受影响）、M5 代码零被改；AGENTS.md 并集修复（恢复我方 v6.11.0~v6.11.2 条目 + 上游 v6.11.3 条目去重 3→1）；回归 compileall + verify_all **29/29** + pytest **154/154** + alembic 单头 + compose config 插值验证；npm build 未跑（前端零变更）；详见更新记录 v6.11.4 与 LOG-063（ZNBG））

**上一版记录（v6.11.3，longtrying_test）**：2026-10-18（v6.11.3 M3 成绩三件套：新增 PUT /employee/scores/{id} 修改接口（不存在→40401）+ student_score 唯一约束 uq_student_score_unique（重复→40901，semester 归一空串）+ 成绩口径统一 0-100 + 迁移 005 清理存量 4 条重复 + E2E 幂等适配；HTTP 冒烟 7/7 + pytest 154/154 + E2E 两轮；同轮完成前端联通诊断（LOG-062）：双 MySQL 环境下 .env 3306→59000 已修、Dify 响应 13~30s 属环境性能）

**上一版记录（v6.11.0~v6.11.2，ZNBG）**：2026-10-18（**M5 一期需求对齐改造（只改 M5 文件）**：①画像四类独立（符合/部分符合/不符合/信息不足）+ 分母只计有研判客户 ②期末状态不可得（不用当前值冒充）③数据源失败改部分生成 ④下钻快照化（新表 ai_report_drill + 迁移 004）⑤投诉 AI 独立表 ticket_ai_analysis + 类型来源 + 待分析只计总量 + 特别案例一期 AI 判定 ⑥AI 改报告专用 Agent（未登记即不可用、不回落 mock）⑦前端周期选择/历史版本/月度对比/状态徽标/完整详情 ⑧新增 /reports/versions，下钻带 note ⑨保留归一与容错作防御 ⑩新增 docs/M5_上游接口契约.md；**v6.11.1/v6.11.2 Dify「智能报告」接入**：改用同名 Chatflow（advanced-chat）发布后 blocking 实测 200、JSON 契约 PASS、DSL 已导出 dify/apps/；M5 加固 think 剥离；回归 pytest **146/146**、verify_all **29/29**、compileall、`npm run build`、Docker E2E **80/80**、production 16/16、迁移 004 上下往返通过；剩余唯一阻塞交 M0（4 行补丁：config DIFY_REPORT_AGENT_KEY + ai_service AgentType.REPORT））

**上一版记录（v6.10.5 anhoa FAQ）**：2026-10-18（**v6.10.5（anhoa）客服 FAQ 应答修复**：实测「公司简称是什么？」两入口均无回答——根因①Chatflow DSL 无知识检索节点而红线 1 要求公司信息以【知识库内容】为准→恒落兜底；②cs_faq 表依赖独立种子脚本，`seed_data.py` 重建库清空后不补跑即 P5 空转；③种子问法「公司简称什么?」差异。修复：Chatflow v3 内嵌 37 条 FAQ 速查表（逐字同源 cs_faq_seed.json，导入即生效零基础设施依赖）+ 红线 1 权威来源新增【FAQ 速查表】+ FAQ few-shot；种子 upsert+`QUESTION_RENAMES` 问法迁移+keywords；新增 `tests/test_cs_faq_match.py` 5 项。回归 pytest **151/151**、verify_all **29/29**、compileall、YAML 静态检查、种子连跑两次幂等、本机接口实测 P5 命中（answer=简称"粤教服务"、card_data.faq 正确）；**Dify 侧方案 B 已落地**：VM `2f92093f`（key 所指，v6.9.9 七分支编排）7 支 prompt 全注入速查表并发布实测三问全过 + `143c1127` 导入版修 kr 空绑并发布；备份 `dify/workflows/_vm_backup_v6.10.5/`；注意速查表第 25 条缴费账号在提示词内按红线 3 改为引导顾问，P5 路径仍按原文返回、两路径口径差异待业务确认；新发现意图码契约漂移（business/policy/event_signup vs 后端 9 码）待 M2 对齐；⚠ **本条中「注册审批门失效致 40006/审批实例不再触发」的表述已随 v6.11.3 免审批规则调整成为既定方向**）

**上一版记录（v6.10.4）**：2026-10-18（**v6.10.4（anhoa）M1 客户转留学生审批通过后身份转换（方案A 事件总线）**：M0 审批引擎审批通过后发布 `approval.approved` 事件（经用户同意改 M0），M1 客户模块新建 `customer_event_handlers.py` 订阅并处理 `biz_type=convert` 分支——`user.user_type PROSPECT→STUDENT` + `customer.status→ENROLLED` + 发布 `customer.converted_to_student` 事件；`main.py` 注册订阅；新增 `tests/e2e_convert_test.py` 端到端 12/12；边界保护三层（biz_type 过滤/关联完整性/user_type 幂等）；回归 pytest **146/146**、verify_all **29/29**、compileall；按用户要求未推送）

**上一版记录（v6.11.0~v6.11.2）**：2026-10-18（**v6.11.0~v6.11.2**：M5 一期需求对齐改造（画像四类/期末状态不可得/部分生成/下钻快照/投诉 AI 表/报告专用 Agent/前端闭环）+ Dify「智能报告」改 Chatflow 接入（发布后 `blocking` 200、JSON 契约 PASS、DSL 已导出）；回归 pytest **146/146**、verify_all **29/29**、compileall、`npm run build`、Docker E2E **80/80**、production 16/16、迁移 004 上下往返通过；剩余唯一阻塞交 M0（4 行补丁）；已提交推送 `master_ZNBG`，未合并 master）

**上一版记录（v6.10.2）**：2026-10-18（**v6.10.2 第八次同步 origin/master→longtrying_test**：并入 M1/M2 全量（v6.9.8~v6.10.1：PROSPECT 审批门 + 客服Agent阶段B + 五项补齐）与 v6.9.7 迁移链修复，39 文件 +1793/-140；公共模块 7 项变更（ai_service 纯新增/user auth 审批门/dify_client URL/迁移链 FK/main.cs 路由+CsRecommendLog 31→32 表/verify_all 32表断言/schemas+wechat）按规则先上报后合并获用户同意；**重点验证 ai_service.py 的 AgentType/AIService/ai_service 全保留**（v6.8.8 教训落地为标准检查动作）；回归 compileall + verify_all **29/29** + pytest **143/143** + 容器重启导入冒烟 **32 表** + /docs 200 + 新路由 /api/v1/cs/faq 200；运行日志编号双线并行（anhoa LOG-044~053 / longtrying_test LOG-044~046）后缀标注区分，勿重编号他人条目；详见更新记录 v6.10.2 与 LOG-046（longtrying_test））  

**上一版记录（v6.10.1）**：2026-10-18（**v6.10.1 docs+数据，零代码**：①M5 字段映射表 M1 三口径拍板定稿——期末状态一期接受「当前值推算」近似（不新增流水表，二期评估 customer_status_log 另批）、4→3 维持保守映射（partial 归「信息不足」防高估，与 `_PROFILE_4_TO_3` 实现一致，二期可拆「部分符合」第四档）、follow_up_summary 一期不取——**M5 切 production 的 M1 前置全部闭环**，余 M3/M4 待对应负责人 ②课程状态 `open`→`上架` 归一（本地库 3 条遗留漂移，前端课程页 tag 恢复中文）③第 3 项其余按计划保持：驳回申诉=二期、Dify 语义检索/实时推荐=等 VM 网络与 embedding 供应商；回归 compileall + pytest 143/143 + verify_all 29/29 + LOG-053）  

**上一版记录（v6.10.0）**：2026-10-18（**v6.10.0 M1/M2 五项补齐**，按用户批准的审查清单执行、严格限界我方模块：①`POST /auth/prospect/approve` 审批人改 JWT 取+MANAGER 校验（40301），v6.9.11 的 query 临时方案移除 ②注册事务原子化——先查可用 MANAGER、user+customer 同一请求会话单事务提交，LOG-051 实测的孤儿数据缺陷消除，服务层同步改为 repo 会话不再绕过 DI ③登录待审批改 40006「账号待开通」（原误用 40003）④新增 `GET /cs/courses` 公开课程（路由 103 paths=102 API+1 health），前端课程页切真实接口 + 注册页提交四画像字段/加微信号输入/提示等审批 ⑤本地库活动枚举归一（published→报名中）——活动报名闭环全通；测试资产 +15：tests/test_user_register.py 7 项（M0 审批引擎/事件总线打桩隔离）+ tests/test_local_extract.py 6 项（v6.9.10 逻辑入库）+ test_ai.py monkeypatch 隔离 .env；回归 compileall + pytest **143/143** + verify_all **29/29** + npm build + 端到端（JWT 审批激活 PROSPECT/四标准账号 13810000001~04 登录/报名成功+防重/课程 3 条真实数据）；遗留：M0 通用 /approvals/{id}/approve 无角色校验（他模块仅记录）、审批实例创建事务贯通待 M0 另批、课程种子 status=open 待统一、M5 映射表 3 个 M1 口径待业务确认 + LOG-052）  

**上一版记录（v6.9.8~v6.9.13）**：2026-10-18（anhoa v6.9.8~v6.9.11 四连交付 + 文档截断修复：①**v6.9.8** M2 阶段B Dify VM 侧落地——192.168.184.128:8080 重建「粤教客服Agent」+ pre_prompt 4336 字符三标记契约 + 4 知识库 7 文档（siliconflow 402/ollama 跨网段不可达→economy+全文检索兜底）+ dify_client /v1 前缀修复 + 前端活动报名接线（Events.vue/platform.ts 切真实 GET /events 与 POST /events/{id}/register，登录回跳恢复报名意图）②**v6.9.9** Chatflow 重建——advanced-chat 2f92093f、B5 问题分类器 7 类节点编排、B4 检索改知识库兜底（f892116a，VM→宿主机不通）、THINK_RE 剥离思考块、.env 换 chatflow key ③**v6.9.10** M1 AI 信息提取本地兜底——LOCAL_EXTRACT_PATTERNS 5 组正则补缺不覆盖 ④**v6.9.11** M1 PROSPECT 注册审批门——注册即审批→MANAGER 审批→激活发 customer.registered 事件，⚠ **RegisterRequest schema 漏改**（user_type pattern 仍 STUDENT|EMPLOYEE、缺 4 选填字段，PROSPECT 注册实测 422），待补 schema 后闭环；另遗留：approver_id 暂从 query 传入待改 JWT、test_chat_unconfigured 环境依赖用例待 mock 化 ⑤**文档事故修复**——docs/更新记录.md 与 运行日志.md 曾被截断（历史条目全失），已自 git HEAD 恢复全部历史并重建 v6.9.8/v6.9.9、LOG-046/LOG-047 条目（均标注「重建」）；本日回归 compileall 通过 + pytest 129/130 + verify_all 29/29；收尾编 **v6.9.12**（docs，零代码）+ LOG-050；**v6.9.13**（经用户批准补齐 RegisterRequest schema——仅 schemas/user.py 一个文件，PROSPECT 审批门端到端实测 6/6，遗留：approver_id 待改 JWT、注册多步写入无整体事务、test_chat_unconfigured 待 mock 化）+ LOG-051）  

**上一版记录（v6.9.7）**：2026-10-17（anhoa v6.9.7 迁移链修复：**M5 移交清单第 2 项闭环**——002 迁移 4 处 FK BigInteger→Integer + 实测扩大的 001 同类 4 处（sys_approval/sys_operation_log/sys_notification，经用户批准「修类型保留表」）+ 002.downgrade 两轮顺序修复（errno 1553 索引依赖 FK、errno 1828 列依赖 FK，先摘 FK 再删列，`_drop_column_fks` 运行时探测）；**空库 upgrade head + downgrade base + upgrade head 三步验收全过**，ORM 44 个 FK 列逐列比对一致，回归 pytest 130/130 + verify_all 29/29；模型/业务代码/契约零变更；遗留迁移漂移债（2 处 session_id 类型 + 5 项 ORM 演进未进迁移）见 LOG-045，建议后续专项对齐；详见更新记录 v6.9.7 与 LOG-045）  

**上一版记录（第五次合并）**：2026-10-17（anhoa 第五次合并 origin/master（e6c06d0→0edd5e9，34 提交）：M5 批次 A~E + v6.9.6 修复 + 远端访问 + v6.9.5 共用模型网关并入，**公共模块 7 项更新经用户批准**（config 3 项 DIFY_MODEL_*/ai_service 追回 AIService/新增 model_ai_service.py/.env.example/依赖组/verify_all 动态断言/compose nginx）；冲突 10 文件并集解决（ai_service.py 客服 AiService 与通用 AIService 双服务共存、verify_all 取 master 动态断言、文档并集）；我方 M1/M2 模块零被改动，32 表/101 paths 不变；pytest 130/130 + verify_all 29/29 + build 通过；详见更新记录 merge 条目与 LOG-044）  

**上一版记录（v6.9.6）**：2026-10-17 17:20（**v6.9.6 M5 三项缺陷修复**，未触碰其他模块代码：①production 缺省周期改用 `default_completed_week()`=上一完整自然周（原 `week_range(now)` 恒落未来必 40002）②`normalize_customer_status()` 复用 M1 的 `STATUS_CN_TO_EN` 做中英 6 态归一 + `fetch_customers` 逐行容错（脏行跳过并写入口径，不再拖垮 5 类报告）③三处下钻改 `_drilldown_dataset()` 与报告同源（production 读真实表、mock 读模拟），前端说明同步；新增 `tests/test_services/test_report_fixes_v696.py` 11 项含防回退断言；回归 compileall / verify_all **27/27** / pytest **124/124** / `npm run build` / Docker E2E **80/80** / **production 冒烟全过**（4 类默认周期 completed、中文状态行不再 500、客户下钻 122 条真实数据脱敏、PDF 5373 bytes、未来周期仍 40002）；详见更新记录 v6.9.6 与 LOG-043）  

**上一版记录（anhoa v6.9.0）**：2026-10-17（anhoa v6.9.0：M2 客服 Agent 二期补齐——依据《客服Agent开发任务书》《客服Agent提示词_纯提示词版》核对现状后落地：①新增 cs_recommend_log 推荐落库表（[RECOMMEND] 标记逐条落库，31→32 张表）②[SLOTS] 槽位采集闭环（slots_json 留档+转线索建档携带画像+老客户画像更新，信息采集/信息更新策略落地）③仅微信号无手机号→pending_lead 待补全线索（同号去重，converted=true；CrmLeadCreate 贯通 wechat 字段）④公开接口 GET /cs/faq + GET /cs/sessions/{id}/messages（路由 99→101）⑤FAQ 种子脚本 scripts/seed_cs_faq.py（36 组问答对+退费红线 QA，幂等）⑥前端：AgentDock public 分支接 /ai/customer-service/chat + 推荐卡片渲染、Faq 页接真实接口；pytest 70/70 + verify_all 29/29 + npm build 通过；**遗留：阶段B Dify 侧配置（pre_prompt 换纯提示词版+输出契约三标记+知识库4目录+课程/活动工具+问题分类器）待 Docker 启动，未配置时标记解析自动跳过；统一 AI 网关（任务书阶段5）属 M0 待审批暂缓**；历史：anhoa 第三次合并 origin/master 并入 v6.8.7 前端交付、LOG-027 本机 MySQL 3306 直连；详见更新记录 v6.9.0 条目与 LOG-029）  

**上一版记录（v6.9.5）**：2026-10-17 16:10（**v6.9.5 第六次同步 origin/master 4d6547c**：①按硬性规则 5 先上报公共模块并取得用户同意——config 新增 `DIFY_MODEL_API_KEY`/`DIFY_MODEL_BASE_URL`/`DIFY_MODEL_NAME`、**新增 `app/services/model_ai_service.py` 共用模型网关**（M3/M4/M5 三处调用）、compose/.env.example/启动脚本凭据、`PublicLayout.vue` 公共导航 ②用户三项决定落地：**数据库凭据保留 420821+59000**（回退 master 的 123456+3306）、**恢复 views/manager/Index.vue**、不引入 master 的 health/complaints 静态占位模板（无路由 + 与智能汇总口径重复）③命名统一 + 差异字段：M5 `ReportAIService` 统一走 `model_ai_service`，报告内容新增 `ai_source`（model/mock/unavailable），PDF/前端文案同源标注 ④合并引入缺陷修复：`employee_service.py`（M3）缺 logger 导入致两处 50001、解冲突后前端 TS6133 未用变量 ⑤回归：compileall / verify_all **27/27** / pytest **113/113** / `npm run build` / Docker E2E **80/80**（修复前 78/80）/ 接口实测 `ai_source=mock`；详见更新记录 merge 条目与 LOG-042）  

**上一版记录（v6.9.3/v6.9.4）**：2026-10-17 14:50（**v6.9.3 环境级验收 + 前后端全量实测，零代码改动**：①环境修复——Docker 卷内 MySQL root 密码仍是旧值 `password`（卷早于「统一 420821」那次改动，`MYSQL_ROOT_PASSWORD` 仅首启生效），edu-backend 启动即崩却显示 Up；`ALTER USER` 对齐 420821 + 重启后 `/health` ok、31 表自动建表 ②测试全绿：compileall / verify_all **27/27** / pytest **113/113** / `npm run build` / Docker E2E **80/80** / **前端 Chrome CDP 自研 E2E 36/36**（真填表登录 + PROSPECT/STUDENT/EMPLOYEE/MANAGER 四端 31 个 section，0 console 错误 / 0 个 4xx-5xx）/ M5 production 冒烟（显式上一自然周）**7/7** ③移交清单第 1、5 项销；新增第 6 项两条 P1（production 缺省周期恒落未来必 40002；客户中文 6 态击穿 CustomerReportInput Literal 必 500 且拖垮 5 类报告）+ 两条 P2（seed ai_report 唯一键随机碰撞、前端部分区块仍静态演示值）；截图存 docs/测试截图_2026-10-17/；详见更新记录 v6.9.3 与 LOG-040）  

**更早记录**：2026-10-17 22:11（第五次同步 origin/master eaaea94→master_ZNBG——并入 v6.8.8 **P1 修复**（ai_service.py 尾部恢复 M0 网关符号，M3/M4 Agent 断链关闭，移交清单第 3 项销，导入实测通过）+ v6.9.0~v6.9.2 远端访问（nginx 8080/ngrok+localtunnel 脚本/REMOTE_ACCESS.md）+ dev 组依赖并集（aiosqlite+pytest-asyncio）；冲突 7 文件并集解决（v6.9.0 双线同名异义已注明：master=远端访问、ZNBG=M5 批次 A~E，ZNBG 线 pytest 113/113+verify_all 27/27）；遗留：推送待用户凭据、002 迁移 FK 未修（上游）、E2E/production 冒烟待环境、M5 字段映射表待业务确认；详见更新记录 merge 条目与 LOG-039）  

**维护人**：开发团队


---

## v6.8.7 前端交付修复与账号登录（2026-10-17）

### 本次变更

- 修复一键启动脚本与 Docker Compose 的 MySQL 密码不一致问题：统一为 420821。
- 修复一键启动脚本错误启动已移除的 MinIO 服务，改为启动 MySQL、Redis。
- 测试账号初始化脚本同步使用数据库密码 420821。
- 删除智能对话预置测试消息，对话框初始为空。
- 对话框新增自动滚动到最新一轮对话，并标识最新消息。
- 学生助手和企业助手已接入真实 Agent 接口。
- 学生行政服务、心理对话、反馈工单等前端动作已接入学生接口。
- 新增独立账号文档：docs/测试账号.md。
- 非前端阻塞项继续预留：公开客服 /cs/*、公开注册角色字段、短信服务和公网部署。

### 测试结果

- backend/verify_all.py：25/25 通过。
- frontend npm run build：通过。
- 学生登录、心理画像、工单、学业、进度、FAQ、更多服务、提醒接口：200/200。
- 学生心理对话、反馈提交、行政服务提交、学生 Agent 对话：200/200。
- 真实账号登录与学生/员工/管理端页面路由：通过。
- 智能对话初始消息为空，发送消息后正常显示最新一轮并自动滚动。
- 浏览器控制台无报错。

### 待后端或部署侧解决

1. /cs/courses、/cs/events、/cs/faq、/cs/sessions 等公开客服接口尚未挂载。
2. /auth/register 当前仅接受 STUDENT、EMPLOYEE，PROSPECT/MANAGER 由初始化脚本写入。
3. 注册接口尚未完整接收性别、年龄、学历、职业需求、德语能力等字段。
4. 短信发送与验证码校验接口不存在。
5. 非同一局域网访问需要公网部署或正式域名。

## v6.9.3 merge and AI environment update - 2026-10-17
- Merge baseline: master v6.9.2 remote access names are retained, including nginx, ngrok and localtunnel.
- Local runtime uses MySQL 8 on localhost port 3306, database GuangdongEducationStudyAbroadProgram, user root, password 123456.
- backend .env is ignored and contains the real Mimo model key. Never copy the key into Git or documentation.
- Native Dify app keys remain placeholders until the Dify workspace publishes real app keys.
- Mimo is the common model fallback for student agent, student psych chat, employee agent, employee guide and smart report analysis. Deterministic fallback remains the final layer.
- A customer cannot submit more than one pending student conversion application. Duplicate submission returns business code 40901.
- Regression result: compileall passed, verify_all 27 of 27, pytest 64 of 64, frontend build passed and live AI smoke passed.

### v6.9.3 merge test result - 2026-10-17
- Merged origin/master remote access capability with the existing AI environment and duplicate submission fixes.
- Conflict policy applied: common deployment names nginx, ngrok and localtunnel are retained; AI model fallback and business difference fields are preserved.
- Backend compileall passed.
- verify_all passed 27 of 27.
- pytest passed 64 of 64 with non-blocking aiomysql cleanup warnings.
- Frontend production build passed.
- Docker Compose configuration validation passed; Docker Desktop config access produced a non-blocking warning.
- Live backend health check returned status ok.

### v6.9.4 login entry fix - 2026-10-17
- Fixed missing login access on mobile public pages by adding login and register actions to the mobile menu.
- Logged-in public header now keeps My Center and adds Logout.
- My Center now routes to the current user role instead of always opening PROSPECT.
- Frontend production build passed after the fix.


---

## v6.9.3 前端问题修复（2026-10-18）

- **已修复**：删除 RoleWorkspace.vue 重复的成绩录入分支；统一成绩页面中文文案；补充成绩录入/编辑的 0-100 校验和错误提示；补全日报日期、内容校验及提交后刷新；清理行尾空格。
- **已修复**：vite.config.ts 拆分 Element Plus、Vue、通用 vendor 构建包，并为 vite preview 增加 /api 代理，预览登录接口验证通过。
- **测试结果**：前端生产构建通过（1719 modules，构建包拆分后无超大包警告）；preview 登录接口 200；此前成绩创建/重复拦截/修改接口冒烟 200/40901/200。
- **未修改**：backend、数据库配置、Dify 配置及接口实现均未改动。
- **仍需后端/基础设施处理**：三个 Dify Agent 未接通；员工助手 fallback 的 logger 未定义；客服 Dify URL 缺少 /v1；数据库端口 3306/59000 文档不一致。

> Git 推送状态（v6.9.3）：本地分支 `codex/frontend-v6.9.3` 已提交；远端认证失败，待补凭据后推送。

> 合并验证（2026-10-18）：云端最新 master 已并入本地 master；四个本地后端 WIP 按用户要求放弃，后端以云端为准；verify_all 29/29 + pytest 143/143 + npm build 通过。

> 文档索引补充：`docs/前端无法解决问题清单.md`（前端无法根治问题、后端解决方案、验收标准）。

> v6.11.3 规则覆盖（qianduan 线，2026-10-18）：访客 PROSPECT 注册免审批，注册即"正常"并可立即登录；详见更新记录。

> v6.11.4（qianduan 线）：学生端留学申请进度布局紧凑化，内容不变；npm build 通过。

**最后更新**：2026-10-19（**v6.11.17 M5 production 投诉域静默清零缺陷修复（ZNBG）**：`report_data_source.py` 补 `ComplaintReportInput` 导入（v6.11.0 投诉域改写遗漏；局部注解不求值掩盖至调用处 NameError，被 v6.9.6 逐行容错静默吞掉、报告仍 completed，production 任意含工单周期投诉指标恒 0）+ 新增防回退用例（test_report_data_source 9/9）；实测含工单周期 orders_total 0→9 / new_count 6 / analyzed_count 8；同轮回归 compileall + verify_all 29/29 + pytest 158/158 + Docker E2E 81/81 + production 冒烟 7/7 + npm build；另含同日 v6.11.15/v6.11.16 Dify 一体化部署修复与 Dify 1.16 初始化兼容修复（用户交付，见 LOG-073）；详见更新记录 v6.11.17 与 LOG-074（ZNBG））

**最后更新**：2026-10-19（**v6.11.14 第十一次同步 origin/master→master_ZNBG（ZNBG）**：合并 `ff20368..027874d`——上游 v6.11.12 **M0 config.py 直连模型默认值去供应商化**（`DIFY_MODEL_BASE_URL`/`DIFY_MODEL_NAME` mimo→全空，经用户批准）+ `.env.example`/`dify/docker/.env` 模板同步 + dify-init DSL `your-model-name` 占位符注入（导入时替换为客户模型名，解决 Chatflow LLM 节点改不到模型的固有问题）+ 删「模型 key 为空即 fail」强阻塞 + 5 个 dify/apps yml 去绑定；M5 零影响（报告 AI 走 REPORT Agent 不依赖直连降级）；行为变化：模型三件套未配置的机器直连降级跳过、走本地话术兜底（本机 .env 已配则无感）；冲突 9 处（3 yml 说明注释取上游去供应商版 + 6 docs 并集线标签消歧，双方 v6.11.12 同号异义并存）；回归 compileall + verify_all 29/29 + pytest 全过 + alembic 单头；详见更新记录 v6.11.14 与 LOG-072（ZNBG））

> v6.11.12：Dify 模型配置去供应商绑定——`DIFY_MODEL_API_KEY`/`DIFY_MODEL_BASE_URL`/`DIFY_MODEL_NAME` 默认值全空（OpenAI-API-compatible 通用协议，key/url/模型名全客户自定义，不绑定任何特定模型）；dify-init 三变量必填校验（缺任一项初始化失败并阻塞 backend）；dify/apps 5 个 yml 模型统一 `your-model-name` 占位符（dify-init 导入时注入客户配置模型名，Chatflow 工作流节点同源生效）；详见更新记录 v6.11.12。

> v6.11.13：种子数据差异补齐 + 迁移链漂移债清偿——数据 vs 字段审计 16 类缺口以 `backend/scripts/seed_supplement_v6_11_13.py`（固定种子 20261019、幂等只填 NULL）补真实数据；迁移 005 防御式 + 006_schema_drift（40 列/2 表/52 处类型/7 主键加宽/16 索引）对齐 ORM，空库全链 001→006 建库与 ORM diff 归零、downgrade↔upgrade 双向过、开发库 `alembic stamp 006`（数据零改动）；pytest 157/157；详见更新记录 v6.11.13。

> v6.11.14：dify-init Dify 1.16 真实环境适配（10 项）——console API 路径/密码双契约（login base64、setup 明文）/cookie 会话+CSRF/供应商接口迁移/模型插件自动安装/自定义模型注册（models/credentials）/DSL 两步导入/工作流发布/yml model_config 0.5.0 结构+mode chat+LLM 节点 context/`your-model-provider` 占位符；`docker compose up -d` 一条命令全链拉起，AI 三端 source=dify 真实可用；pytest 157/157；详见更新记录 v6.11.14。

> v6.11.15：遗留问题清零——`start-project.bat` 旧 Dify 实例冲突预检（docker-* 检测→提示 down）；dify_init.py 文案/日志语义修正；**阻塞清单⑤销账**（智能报告 Chatflow 补 system prompt JSON 契约约束 + temperature 0.2，实例已重导一致）；pytest 157/157；详见更新记录 v6.11.15。

**最后更新**：2026-10-19（v6.11.15 遗留问题清零：启动防冲突预检、dify_init 文案语义、阻塞清单⑤销账（报告 Chatflow system prompt 约束+降温）；v6.11.14 dify-init Dify 1.16 适配：10 项契约修复（路径/密码/CSRF/插件安装/模型注册/两步导入/工作流发布/yml 结构），一条命令全链拉起、AI 三端 source=dify 真实可用、pytest 157/157；v6.11.13 种子数据差异补齐 + 迁移链漂移债清偿：seed_supplement_v6_11_13.py 补 16 类字段缺口真实数据；005 防御式 + 006_schema_drift 对齐 ORM，全链建库 diff 归零、开发库 stamp 006；v6.11.12 Dify 模型配置去供应商绑定：三变量默认值全空 + dify-init 必填校验 + yml 模型占位符注入，全仓 MiMo/供应商绑定痕迹清零，历史日志仅作留痕标注；2026-10-18 合并 gitea/master→longtrying_test：10 项公共模块经用户逐项审批并入，pytest 157/157）

> 合并回归（2026-10-18）：qianduan 已并入 origin/master 成绩三件套、环境修复与远端访问文档更新；verify_all 29/29、pytest 152/152、npm build 通过。
