# 使用说明：证据驱动的 Astra 路由反馈闭环

这个增强版在原有 Astra Advisor 的动态委派基础上增加一个本地、可审计、可撤销的反馈闭环。目标不是让 Astra“训练自己”，而是让它根据历史委派结果逐步校正路由策略，并减少同类错误重复发生。

## 核心原则

1. **先区分失败原因，再学习。** 模型能力不足、规格不清、上下文缺失、文件所有权冲突、验证不足、环境问题和运行时模型不匹配分别处理。只有经过证据确认的能力问题才会提高模型下限。
2. **一次失败不会永久固化。** 单次已确认能力失败只在短期内触发更谨慎的路由；长期升级需要多个独立任务的重复证据，并随时间衰减。
3. **相同任务重试不伪装成多个样本。** 同一个 `task_id` 的重试只作为同一任务的尝试，不会人为放大统计权重。
4. **历史可纠错。** 如果后续发现失败归因错误，可用 `void` 写入新的撤销记录；旧记录仍保留，便于审计。
5. **本地保存。** 数据库和证据目录位于目标 Git 仓库的 common git directory 下，不会自动提交到源码仓库或上传网络。
6. **验收绑定真实快照。** 对重大实现，父线程验证、fresh reviewer 和最终 gate 必须对应同一工作树快照；任何代码或证据变化都会要求重新验证和审查。

## 路由规则

对每个可独立委派任务，Astra 对以下维度按 0–3 评分：

- `judgment`：需要多少自主判断；
- `context`：需要多少跨文件/跨模块上下文；
- `blast_radius`：出错影响范围；
- `spec_gap`：规格和验收条件缺口；
- `uncertainty`：问题本身的不确定程度。

初始总分：

- 0–3：Luna / medium；
- 4–8：Terra / high；
- 9 以上：Sol / high。

只要涉及 `security`、`payments`、`data_loss`、`concurrency`、`public_contract`，或 `blast_radius=3`，最低使用 Sol。若 `spec_gap=3`、任务不 bounded 或不能独立，则留在 Astra 父线程，先补规格或继续拆解。

这些阈值是保守初始策略，不是经过真实模型 benchmark 校准的准确率数字。

## 历史反馈如何改变下一次路由

历史只在非常窄的匹配桶内生效：同一仓库、同一运行时 epoch、同一策略版本、同一 kind/domain/pattern/scope、同一风险向量和关键风险标记。

确认是模型能力不足后：

- 单次近期失败：7 天内把匹配任务提高一个模型层级；
- 长期规则：至少 3 个不同任务发生确认能力失败，并满足衰减后的有效样本与失败比例阈值后，继续维持升级；
- 半衰期：30 天；
- 90 天后退出路由计算；
- Sol/xhigh 仍失败：不无限增加 effort，而是要求 Astra 缩小范围或重新规划。

环境、规格、上下文等失败不会被错误归因成“模型太弱”，而会生成对应的必做纠正动作。

## 使用流程

先在目标工作仓库执行：

```bash
python3 /path/to/routing_memory.py --repo /path/to/project init
```

它会返回私有 `state_dir` 和 `evidence_dir`。将当前 native tool schema、验证记录等精简证据写入该 evidence 目录。

每次委派前：

```bash
python3 routing_memory.py --repo /path/to/project plan \
  --task TASK.json \
  --runtime RUNTIME.json
```

只有返回 `status: ready` 才允许 spawn。返回 `parent_only`、`blocked` 或 `rethink_parent` 时都不能把它当作委派许可。

每次委派结束、失败、取消或后来发现问题时，都要立即记录：

```bash
python3 routing_memory.py --repo /path/to/project feedback \
  --input OUTCOME.json
```

如果后来确认某条反馈归因错误：

```bash
python3 routing_memory.py --repo /path/to/project void \
  --event EVENT_ID \
  --reason misattribution \
  --evidence correction.txt
```

重大实现完成后，Astra 先检查完整 diff 并实际运行验证，再记录：

```bash
python3 routing_memory.py --repo /path/to/project verify \
  --routes ROUTE_ID_1 ROUTE_ID_2 \
  --evidence checks.txt
```

随后创建 fresh read-only reviewer。Reviewer 的最低强度按实际实现模型自动提高：Luna 实现至少 Terra reviewer；Terra 实现至少 Sol reviewer；Sol 实现仍由 fresh Sol reviewer 审查。

Reviewer 返回 `ship` 并记录 feedback 后：

```bash
python3 routing_memory.py --repo /path/to/project gate \
  --review REVIEW_ROUTE_ID
```

只有 gate 成功才满足增强版的 substantial-work 验收条件。

## 查看历史

```bash
python3 routing_memory.py --repo /path/to/project report
```

该报告只提供描述性统计，不能证明“因为反馈机制所以质量提高了”。要证明实际提升，需要积累足够真实任务后做独立对照评估。

完整协议见：

`plugins/astra-advisor/skills/orchestration/references/routing-memory.md`
