# 委派判断与最小任务交接

本版按 OpenAI Codex Subagents、Codex Best Practices、GPT-6 Astra Model Guidance 和
Prompt Caching 文档收敛委派规则。官方原则是：子代理适合独立并行工作，尤其是探索、
测试、日志分析、资料核查和摘要；每个子代理会产生自己的模型与工具 token，所以小任务、
严格串行任务和写入冲突任务通常留在主线程。

## 什么时候委派

任务必须具体、有边界、可独立完成、输入已就绪，并且没有重复执行或文件归属冲突。
然后至少满足一个实际收益：

- `parallel_progress`：Astra 和子代理能在汇合前同时做有用且不重叠的工作；
- `context_isolation`：把大量搜索、日志、测试输出或文档处理移出主线程，只返回摘要；
- `independent_check`：独立视角能明显提高质量。

协调成本超过收益时由 Astra 自己做。依赖、归属或重复工作未解决时等待。重大修改的
最终独立 review 是质量门，不能为了少用 token 直接省略。`profile_handoff.py assess`
只记录 Astra 的判断，不声称测量了节省金额或准确率。

## 最少需要传什么

OpenAI 推荐提示词明确 Goal、Context、Constraints 和 Done when。子代理任务因此只保留：

```text
GOAL    局部终态
SCOPE   只读或精确可写文件
KEEP    会影响行动的不变约束
INPUT   子代理能访问的权威工件
CONTEXT 有来源的事实和明确标注的假设
DELTA   复用 worker 时的新发现和变化
DONE    检查及预期证据
STOP    信息、权限、归属或范围升级条件
RETURN  状态、引用、实际检查结果和剩余风险
```

不发送 Astra 的私有推理、模型路由表、成本分析、完整对话、大段 diff 和原始日志。
需要大量内容时提供可访问工件引用。新 worker 得到最小完整任务；复用 worker 只得到
增量和仍然有效的约束；最终 reviewer 得到实际改动和验证证据，并保持全新只读上下文。

## 短 Profile

每个任务只加一个基础 Profile，最多一个修饰器。实际边界决定基础 Profile：
只读任务用 `EXPLORE`，明确分配可写文件的任务用 `WORK`，最终独立审查用
`REVIEW`。任务类型需要改变执行纪律时再加 `+DEBUG`、`+TEST` 或 `+DOCS`。
这样不会出现 Profile 要求只读、任务合同却分配写权限的矛盾。

Profile 只有几十个词的行为规则，不写人格设定。安全、支付、数据完整性和公开接口等
风险放在任务约束、验收条件和模型路由下限中。

## 实际顺序

```text
profile_handoff.py assess
  → routing_memory.py plan
  → agent_reuse.py plan
  → profile_handoff.py prepare
  → profile_handoff.py claim
  → 原生 spawn / follow-up
  → routing_memory.py feedback
  → agent_reuse.py finish
  → Astra 验证实际 diff 和检查
  → 全新独立 review
  → profile_handoff.py gate
```

只有成功的 prepare 和 claim 才允许真正派发。claim 会重新检查任务包、模型决策、源码、
证据、worker 和文件预约。返回 JSON 中只有 `message` 是子代理提示词，其余字段由 Astra
映射到当前真实工具接口，不能猜测工具参数。

稳定行为规则放在消息前部，动态任务内容放在后部，这符合 OpenAI 对可复用前缀的建议；
但短消息可能达不到具体模型的缓存门槛，原生 Codex 的上下文管理也可能不同，因此不能
从排列方式推断缓存命中或净省钱。

完整 Profile 规则见
[`token-efficient-profiles.md`](../plugins/astra-advisor/skills/orchestration/references/token-efficient-profiles.md)，
委派协议见
[`delegation-handoff.md`](../plugins/astra-advisor/skills/orchestration/references/delegation-handoff.md)。
