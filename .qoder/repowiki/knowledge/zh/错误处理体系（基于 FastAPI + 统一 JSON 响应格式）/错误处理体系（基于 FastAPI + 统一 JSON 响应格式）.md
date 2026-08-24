---
kind: error_handling
name: 错误处理体系（基于 FastAPI + 统一 JSON 响应格式）
category: error_handling
scope:
    - '**'
source_files:
    - docs/hiagent_辅助_Web_服务需求说明_task-242.md
---

## 1. 系统/方法概述

该仓库目前仅包含需求说明书 `docs/hiagent_辅助_Web_服务需求说明_task-242.md`，尚未实现任何代码。但文档已明确定义了错误处理的整体方案：

- **框架**：FastAPI（Python Web 框架），结合 Pydantic 做请求/响应校验。
- **统一响应格式**：所有 API 返回统一的 JSON 结构 `{code, message, data, request_id}`，其中 `code` 用于区分成功与失败、`message` 描述错误信息、`data` 承载正常数据或错误上下文、`request_id` 用于追踪。
- **错误码分段规范**：按模块划分错误码区间——1xxx 通用、2xxx 数据处理、3xxx 可视化、4xxx 文件文档、5xxx API 编排、6xxx Pipeline 引擎。这为后续实现提供了明确的错误分类约定。
- **认证错误**：通过 `X-API-Key` Header 进行 API Key 认证，未携带或无效时应在统一响应中返回对应错误码。

## 2. 关键文件

当前仓库仅有需求文档，无实现代码：
- `docs/hiagent_辅助_Web_服务需求说明_task-242.md` — 定义统一响应格式、错误码分段、Pipeline 步骤级错误处理策略等。

## 3. 架构与约定

根据需求文档，错误处理将贯穿以下层次：

| 层次 | 错误处理方式 |
|------|-------------|
| 认证层 | 校验 `X-API-Key` Header，失败返回统一 JSON 错误响应 |
| 连接器层 | database/api/file_upload/file_url/file_s3 等 Connector 出错时向上抛出，由上层捕获并映射到统一响应 |
| Pipeline 引擎 | 每步独立记录日志和耗时；支持条件分支与**步骤级错误处理（skip/abort）**，即某一步失败可选择跳过继续执行或中止整个流水线 |
| 输出组装器 | 图表/报告/表格渲染失败时返回对应错误码（3xxx / 4xxx） |
| 原子 API | 每个 `/api/v1/data/*`、`/api/v1/visual/*`、`/api/v1/file/*`、`/api/v1/proxy/*` 端点均使用统一 JSON 响应封装错误 |

Pipeline 引擎的错误处理是核心设计：步骤顺序执行，遇到异常可按配置选择 `skip`（忽略该步骤继续）或 `abort`（立即终止流水线），并在日志中记录步骤耗时与错误原因。

## 4. 约定与约束

- **必须使用统一 JSON 响应格式**：所有接口返回 `{code, message, data, request_id}`，禁止裸抛异常或返回非标准格式。
- **错误码必须落在预定义区间**：1xxx（通用）、2xxx（数据处理）、3xxx（可视化）、4xxx（文件文档）、5xxx（API 编排）、6xxx（Pipeline 引擎），不得随意扩展新段。
- **Pipeline 步骤必须支持 skip/abort 两种错误恢复策略**，以便在部分步骤失败时仍能尽可能完成流程。
- **可观测性要求**：结构化日志需包含 `scenario_id`、步骤耗时等信息，便于定位错误来源。
- **安全约束**：凭据不硬编码（从环境变量读取），SQL 注入防护，文件沙箱隔离。

由于仓库尚未包含实现代码，以上均为需求阶段约定的设计决策，实际落地时需严格遵循这些约定来构建 FastAPI 中间件、异常处理器与 Pipeline 错误传播机制。