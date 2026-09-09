# 低 Token 子代理 Profile

这一版采用 OpenAI 官方文档所强调的原则：只有独立并行工作、上下文隔离或独立审查
能明显改善速度或质量时才委派；优先把代码探索、测试、日志分析、资料核查和摘要等
读密集工作交给子代理。小任务、严格串行任务和写入范围冲突的任务留在 Astra 主线程。

## Profile 不是长角色设定

每个任务只使用一个基础 Profile，最多加一个修饰器：

| 任务 | Profile | 行为重点 |
| --- | --- | --- |
| research | `EXPLORE` | 只读追踪真实路径，给出文件、符号或工件证据。 |
| docs | `EXPLORE+DOCS` | 核对权威、版本相关文档。 |
| implementation/refactor | `WORK` | 最小范围修改，保持合同，跑针对性检查。 |
| debug | `WORK+DEBUG` | 先复现，再验证竞争假设，根因有证据前不做大改。 |
| test | `WORK+TEST` | 验证可观察行为，报告准确命令和结果，只改已分配文件。 |
| review | `REVIEW` | 全新只读上下文，优先找正确性、安全、回归和测试缺口。 |

Profile 只描述执行纪律，不写“你是一名专家”之类的人格文本，也不携带具体模块、
路由评分或成本信息。安全、支付、数据完整性等风险放入任务的约束和验收条件。

## 最小任务合同

`profile_handoff.py` 生成的消息按下面顺序排列：

```text
稳定 BASE
短 PROFILE
TASK
GOAL
SCOPE
KEEP
INPUT / CONTEXT（新 worker）
DELTA（复用 worker）
CHANGE / VERIFY（独立 review）
DONE
STOP
RETURN
```

稳定规则放在动态任务之前；这符合 OpenAI 关于可复用前缀的建议，但不代表一定命中
缓存。新 worker 得到完成局部任务所需的最少完整信息；复用 worker 只得到本轮变化、
仍适用的约束和验收条件，不重放父线程对话；reviewer 始终使用新的独立只读上下文。

不发送 Astra 的私有推理、模型路由表、成本分析、完整对话、大段 diff 或原始日志。
需要大量内容时，提供子代理可访问的工件引用。消息超过 6000 字节会失败关闭，要求
先删除重复背景；该限制是本仓库保护值，不是官方 token 上限。

## 执行顺序

```text
profile_handoff.py assess
  → routing_memory.py plan
  → agent_reuse.py plan
  → profile_handoff.py prepare
  → profile_handoff.py claim
  → 原生 spawn / follow-up
  → routing feedback
  → agent_reuse.py finish
  → 父线程验证
  → 全新独立 review
  → profile_handoff.py gate
```

`profile_handoff.py` 复用原有 `handoff.py` 的输入校验、预约和验收机制，只替换消息渲染
及策略版本。旧的 `handoff.py` 仍用于兼容，但不能据此声称已经执行 handoff-v2。

这套优化减少的是重复样板和无关上下文。子代理仍会产生自己的模型与工具 token；
上下文复用、稳定前缀和更短提示都不自动证明净省钱，必须用真实运行数据评估。
