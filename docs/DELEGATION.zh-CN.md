# 委派判断与任务交接

本版把两个问题分开：**这件事值得委派吗？值得的话，worker 究竟需要知道什么？**
规则参考 OpenAI 官方 Subagents、Astra Model Guidance 和 Codex 工作流指南；
来源和本仓库自定义策略的边界见[运行协议](../plugins/astra-advisor/skills/orchestration/references/delegation-handoff.md)。

## 什么时候委派

小而明确、主线程直接做更省事的修改，留给 Astra，不创建一套额外任务文件。
有价值的候选包括独立代码探索、需要大量读取但只返回摘要的分析、接口已经明确的
并行实现，以及独立审查。必须说明具体收益、边界、Astra 同时做什么、何时汇合。

如果 Astra 派完就等，不能把它说成并行加速；确实需要隔离大段上下文或独立检查，
仍可说明理由后委派。依赖未就绪、同一工作已在执行、写入边界不清时先等待或协调，
不再启动一份重复工作。用户限制、预算、当前工具能力都不能被绕过。

重大修改所需的全新独立 review 是质量要求，不能因为开销较大而自动省略。
`handoff.py assess` 可输出 `delegate / parent / wait / blocked`，判断依据来自 Astra
对真实任务的评估，不是模型测速或节约金额预测。简单的 solo 工作不必运行它。

## 传给 worker 的内容

| 情况 | 收到的信息 |
| --- | --- |
| 新 worker | 本地目标、可访问输入和接口、事实与假设、写入边界、不变约束、验收检查、停止条件、返回格式。 |
| 复用 worker | 本轮目标、新发现、变动文件/接口、仍适用的约束和检查；不重放完整父对话。 |
| 全新 reviewer | 当前真实变更、父线程验证证据、应保持的行为约束和只读审查要求；不把实现者的成功总结当结论。 |

复用时必须重读变动文件和相关依赖，不能拿记忆里的代码当当前事实。
新 worker 不继承父对话时，Astra 必须给足完成这个小任务需要的信息。
引用材料应确认子代理能访问；私有路径、父线程附件或不支持的工具不能假定自动可见。

实际消息由 `handoff.py` 生成：

```text
ASTRA HANDOFF TASK / DELTA / REVIEW
Task
GOAL
BOUNDARIES
INPUTS
RELEVANT CONTEXT（区分 observed / hypothesis）
CHANGES SINCE YOUR LAST TURN（仅复用）
INDEPENDENT REVIEW（仅独立审查）
ACCEPTANCE / EVIDENCE
STOP / ESCALATE
RETURN
```

消息只包含子任务合同，不带主线程的模型路由表、成本计算、整段日志、完整对话或
私有推理过程。要求返回文件/符号引用、实际做过的检查与结果、未验证项和阻塞原因。
超出范围、信息矛盾、需要额外权限或无新证据仍反复失败时，停止并向 Astra 报告。
worker 不自行扩展任务，也不自行提交、推送或部署；这些动作仍由父线程按用户授权处理。

## 如何执行

Skill 已接入以下顺序；脚本路径须解析到安装目录，`--repo` 则指向正在工作的仓库：

```text
委派判断
  → routing_memory.py plan
  → agent_reuse.py plan
  → handoff.py prepare --decision ID --input PRIVATE_PACKET.json
  → handoff.py claim --handoff ID
  → Astra 实际调用原生 spawn / follow-up
  → routing_memory.py feedback
  → agent_reuse.py finish
  → 父线程验证 → 全新 review → handoff.py gate
```

`handoff.py claim` 内部已经调用原来的预约逻辑，不能再对同一次任务重复 claim。
它会检查消息输入是否被改动、任务 ID、文件归属、模型决策和源码/证据是否过期。
只把返回的 `message` 作为子代理提示词，其他字段留给主线程映射到真实工具接口。
消息不完整、缺验收条件、复用却没有变化说明、审查不是全新只读上下文，都会被拒绝。

新验收入口组合已有的复用与源码快照检查。历史反馈、错误归因、经验衰减和 reviewer
能力下限继续保留，不会为了复用上下文而降低选定模型。旧接口为兼容而保留，但只用
旧接口不能声称已执行新交接流程。升级中的未完成任务应重新规划，不补造旧调用记录。

## 仍然需要知道的边界

这不是自动拦截所有原生工具的 hook；Astra 需要实际执行 Skill 的流程。任务包准备好
并不代表子代理已收到它，最终还要保留实际调用与执行证据。结构检查不能证明任务
分解一定合理、事实一定真实，或子代理一定遵从提示词，也不是操作系统权限隔离。

任务正文放在工作仓库 Git 元数据目录内的私有证据文件，数据库只记哈希和标识；
不会自动提交或上传个人信息、任务正文和历史。24 KB 是本实现的消息保护上限，
不是官方 token 限额。复用不保证缓存命中、历史输入免费或净省钱。

[示例判断](../plugins/astra-advisor/examples/handoff-assessment.example.json)和
[示例任务包](../plugins/astra-advisor/examples/handoff-task.example.json)仅供理解结构，
不能当作真实运行时能力或任务证据。
