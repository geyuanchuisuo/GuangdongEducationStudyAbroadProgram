# 粤教留学 RAG 系统评测

对「粤教留学项目管理平台」的知识库问答 RAG 系统（v6.14.0 双集合混合检索 + 问题改写层）
做质量评测，方法遵循 `wolin_learn-master/rag_examples/07_rag_evaluation` 的 **RAGAS 四指标**，
使用真实 `ragas` 库评估。

## 评测什么

| 维度 | 指标 | 含义 |
|------|------|------|
| 🔵 检索质量 | Context Precision（上下文精确率） | 检索到的上下文里有多少是真相关的（噪音控制） |
| 🔵 检索质量 | Context Recall（上下文召回率） | 标准答案所需信息有多少被检索到了（遗漏控制） |
| 🟢 生成质量 | Faithfulness（忠实度） | 回答是否只依据检索到的上下文（抗幻觉） |
| 🟢 生成质量 | Answer Relevancy（答案相关性） | 回答是否切题、完整 |

综合得分 = 四指标等权均值。评级：≥80% 优秀 / 60–79% 良好 / 40–59% 一般 / <40% 较差。

## 关键设计（零改业务代码）

- **独立环境**：`evaluation/.venv`（Python 3.11），单独装 ragas + 后端最小运行依赖，
  **不碰** `backend/pyproject.toml`、`uv.lock`。
- **进程内直调**：`run_eval.py` chdir 到 `backend/`（`app.config` 的 `env_file=".env"` 是相对路径，
  必须在 backend 下才能加载网关 key），`sys.path` 注入 `backend/` 与 `evaluation/`，
  直接 import 生产 service，复刻真实链路：
  `query_rewriter.rewrite` → `knowledge_service.search_dual(top_k=5)` → `knowledge_qa_service._build_messages + _chat_gateway`。
- **只读评测**：不改数据库、不改向量库、不改业务代码。
- **裁判模型**：项目 `DIFY_MODEL_*` 网关（deepseek-flash）；**嵌入**：本机 Ollama `bge-m3`（与生产同源）。

## 目录

```
evaluation/
├── .venv/                     # 独立虚拟环境
├── requirements.txt           # 依赖清单（留档）
├── dataset/
│   └── golden_set.json        # 黄金题库：33 可答 + 3 拒答
├── ragas_judge.py             # 裁判 LLM / 嵌入 / 四指标装配
├── run_eval.py                # 评测主程序
├── results/
│   ├── pipeline_raw.json      # 阶段一：检索+生成原始结果（可断点）
│   ├── ragas_result.json      # 阶段二：ragas 四指标结果
│   ├── ragas_per_question.csv # 逐题得分表
│   └── summary.json           # 阶段三：汇总（含拒答专项 + 辅助指标）
└── README.md
```

## 前置条件

1. Milvus 已启动（`vector/start.bat`），知识库已导入（110 条：74 长文 + 36 FAQ）。
2. Ollama 已启动且拉取 `bge-m3`。
3. `backend/.env` 已配置 `DIFY_MODEL_API_KEY / DIFY_MODEL_BASE_URL / DIFY_MODEL_NAME`
   （deepseek 网关；裁判与生成都用它）。

## 运行

```bash
cd evaluation

# 冒烟：只跑前 3 题的检索+生成，验证链路与连通性
.venv/Scripts/python.exe run_eval.py --limit 3 --skip-ragas

# 全量评测（检索+生成 → ragas 四指标 → 汇总）
.venv/Scripts/python.exe run_eval.py
```

## 说明与局限

- 裁判模型 deepseek-flash 与被测系统的生成模型同源，存在「自判偏置」（self-judging bias），
  忠实度/相关性分数可能偏乐观，解读时需留意。
- Context Precision/Recall 用 `LLMContextPrecisionWithReference` / `LLMContextRecall`，
  以 `ground_truth` 为参照由裁判 LLM 判定，非严格文档 ID 集合比对。
- 拒答题（知识库无答案）单独统计「拒答正确率」，不计入四指标均分。
