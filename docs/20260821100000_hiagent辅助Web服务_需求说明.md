# hiagent 辅助 Web 服务 — 需求说明书

---

## 一、项目背景与定位

hiagent 是基于现有平台（如 Dify / Coze）构建的 AI Agent 应用，面向**多种业务分析场景**，包括但不限于：

- **竞品分析**：对比多个竞品的规模、收益、费率等指标，输出对比报告和排名图表
- **机构行为分析**：分析机构的申赎行为、持仓变化、资金流向，输出行为画像
- **产品规模增量分析**：追踪产品规模变动、增量归因、趋势预测，输出趋势图表和归因表

每种场景的**底层数据来源不同**，**处理逻辑不同**，**输出结果也不同**。因此需要设计一个**通用架构**，以配置驱动的方式支撑所有场景。

核心原则：无状态、单一职责、输入输出标准化、容错优先、安全隔离、**场景可配置**、**组件可复用**。

---

## 二、技术选型

FastAPI + pandas/numpy + DuckDB + matplotlib/plotly + WeasyPrint + httpx + Pydantic + PyYAML + SQLAlchemy + jsonpath-ng + Docker/uvicorn

---

## 三、统一接口规范

- 统一 JSON 响应格式（code/message/data/request_id）
- 错误码按模块分段：1xxx 通用、2xxx 数据处理、3xxx 可视化、4xxx 文件文档、5xxx API 编排、6xxx Pipeline 引擎
- API Key 认证（X-API-Key Header）

---

## 四、通用架构设计 — 场景驱动的流水线引擎（核心新增）

### 架构总览
```
Agent 请求 -> Pipeline API 入口 -> 场景配置加载器 -> 数据获取层(Connector) -> 数据处理流水线(Step链) -> 输出组装器 -> 统一响应
```

### 场景配置模型（YAML）
每个业务场景用一份 YAML 配置描述：
- `data_sources`：数据源定义（connector 类型 + 连接配置 + SQL/API 参数 + 请求参数映射）
- `pipeline`：处理流水线步骤（action 调用原子能力 + input/output 命名引用）
- `outputs`：输出定义（chart/table/report/file/summary 类型 + 数据源引用）

### 连接器层（Connector Layer）
| 连接器类型 | 适用场景 |
|-----------|---------|
| database | 直连数据库（MySQL/PostgreSQL/ClickHouse） |
| api | 调用外部 REST API |
| file_upload | Agent 上传文件 |
| file_url | 从 URL 下载文件 |
| file_s3 | 对象存储（后期扩展） |

所有连接器返回统一 DataFrame，凭据从环境变量读取，注册表模式扩展。

### 流水线引擎（Pipeline Engine）
- 步骤顺序执行，通过命名引用传递中间数据（PipelineContext）
- 支持条件分支、步骤级错误处理（skip/abort）
- 每步独立记录日志和耗时

### 输出组装器（Output Assembler）
chart / table / report / file / summary 五种输出类型，其中 summary 专为 Agent 设计。

### 两种调用模式
- **模式 A：Pipeline API**（`POST /api/v1/pipeline/run`）— 传入 scenario_id + 参数，一次完成全流程
- **模式 B：原子 API**（`/api/v1/data/*`、`/api/v1/visual/*` 等）— 逐步调用，Agent 自行编排

---

## 五、功能模块详细设计

### 5.1 数据处理 `/api/v1/data`
- 数据导入解析（CSV/Excel/JSON，自动编码检测、类型推断）
- SQL 查询（DuckDB）、筛选、聚合、透视、排序、去重
- 数据清洗（空值、类型转换、文本清洗、异常值）
- 统计分析（描述性统计、相关性、频率分布）

### 5.2 可视化与渲染 `/api/v1/visual`
- 图表生成（柱状图/折线图/饼图/散点图/热力图/雷达图等，支持 PNG/SVG/HTML）
- 报告渲染（Jinja2 HTML 模板、Markdown 转 HTML）
- 数据表格渲染（条件着色、排序）

### 5.3 文件与文档操作 `/api/v1/file`
- 格式转换（CSV/Excel/JSON/Markdown/HTML 互转）
- 文档生成（PDF/Word/Excel/PPT，支持模板）
- 文件打包解压、元信息查询
- 临时文件管理（2 小时自动清理、流式下载）

### 5.4 API 编排 `/api/v1/proxy`
- HTTP 代理（单次/批量并发/链式请求）
- 数据转换（jq 风格、XML-JSON、扁平化）
- 超时重试、速率限制、鉴权模板

---

## 六、非功能性需求

- 性能：简单接口 < 500ms，数据处理 < 3s，Pipeline 全流程 < 10s
- 安全：API Key 认证、文件沙箱、SQL 注入防护、凭据不硬编码
- 可观测性：结构化日志含 scenario_id + 步骤耗时、`/health`、`/api/v1/pipeline/scenarios` 列表
- 部署：Docker、环境变量配置、场景配置热加载

---

## 七、项目结构

关键新增目录：
- `app/core/pipeline_engine.py` — 流水线引擎
- `app/core/scenario_loader.py` — 场景配置加载器
- `app/core/connectors/` — 数据连接器（base/database/api/file）
- `app/core/output_assembler.py` — 输出组装器
- `app/scenarios/*.yaml` — 场景配置文件目录
- `app/api/v1/pipeline.py` — Pipeline 路由

---

## 八、开发路线图

### Phase 1 — 基础框架 + 原子能力
项目骨架、数据解析/查询/统计、基础图表、统一规范

### Phase 2 — Pipeline 引擎 + 连接器
场景配置模型、Pipeline 引擎、数据库/API 连接器、输出组装器、第一个场景落地（竞品分析）

### Phase 3 — 文档与报告
HTML 报告、PDF/Word/Excel 生成、预置模板库

### Phase 4 — 完善与扩展
更多场景接入、API 编排、性能优化、配置热加载、文档完善

---

## 九、关键决策记录

| 决策项 | 选择 | 理由 |
|--------|------|------|
| 核心架构 | Pipeline + 原子 API 双模式 | Pipeline 减少 Agent 编排复杂度，原子 API 保留灵活性 |
| 场景配置格式 | YAML | 可读性好，支持注释 |
| SQL 引擎 | DuckDB | DataFrame 查询性能优于 pandasql |
| 连接器模式 | 注册表模式（BaseConnector） | 新增连接器改动最小 |
| 文件存储 | 本地临时目录 | 初期简单，后期可扩展 OSS |