---
name: delegate-to-cursor
description: 根据已经完成的 SPEC 和 PLAN，按计划顺序把实现、测试、独立验证和修复分别委派给不同的 Cursor CLI 会话；Codex 只负责维持可审计的执行闭环。仅在用户明确要求按既有规划委派 Cursor 执行时使用。
---

# 委派给 Cursor

仅当用户显式调用 `$delegate-to-cursor` 时使用。如果当前运行环境本身是 Cursor Agent，立即停止，不得递归委派。

## 职责边界

本 skill 的输入是**已经完成并由用户认可的 SPEC 和 PLAN**。不得在这里重新创建、扩写或重新设计 SPEC/PLAN。

- **Codex 编排者：** 读取既有 SPEC/PLAN，按 PLAN 顺序取出下一个依赖已满足的任务，构造任务包，启动独立 Cursor 委派，维护隔离工作树，检查运行器结构状态，并在各阶段之间转交结构化结果。
- **Cursor 实现者：** 只实现当前计划项，不承担测试、验证或修复职责。
- **Cursor 测试者：** 在全新只读会话中执行 PLAN 规定的测试和检查，不修改实现。
- **Cursor 验证者：** 在另一个全新只读会话中，独立对照 SPEC/PLAN 检查结果并提供验收证据。
- **Cursor 修复者：** 在全新写入会话中，根据测试和验证问题实施修复；不得恢复或复用实现者会话。

实现、测试、独立验证和每一轮修复必须是彼此独立的 Cursor 委派。不得用同一个 `session_id` 承担两个阶段，也不得用 `--resume` 跨阶段复用会话。

Codex 只保证委派闭环正常运行，不代替 Cursor 实现、不运行测试、不读取完整 diff 做语义复审，也不自行判断功能是否正确。

如果找不到既有 SPEC/PLAN，或者 PLAN 缺少执行顺序、验收标准、允许修改的范围或验证命令，应停止委派并报告缺失项；不得在本 skill 内补写规划。

## 1. 按 PLAN 取得下一项任务

严格按照既有 PLAN 的依赖顺序逐项执行，不并行委派。每次只处理一个计划项，并保持 PLAN 中定义的目标、边界、非目标和验收标准不变。

为当前计划项确认：

- 对应的 SPEC 要求和 PLAN 项标识；
- 精确基础 Git OID；
- 权威入口文件和允许修改的路径 glob；
- 验收标准、边界情况和兼容性要求；
- Cursor 测试者必须执行的聚焦测试命令；
- Cursor 验证者必须核验的验收证据；
- 完成所有计划项后的集成测试与集成验证要求。

## 2. 构造四类任务包

所有任务包只包含当前计划项所需的 SPEC/PLAN 摘要和仓库上下文，不要求 Cursor 重新规划整个项目。

- **实现包：** 计划项标识、目标、停止边界、允许修改的路径、实现约束和非目标。要求报告已修改路径、未完成内容和意外发现，不要求给出通过结论。
- **测试包：** 原始测试要求、精确工作树、命令、期望结果和结构化报告格式。不得包含实现者的自我评价。
- **验证包：** 原始 SPEC/PLAN 验收标准、精确基础 OID、当前工作树和证据要求。不得包含实现者或测试者的结论。
- **修复包：** 测试者和验证者返回的原始结构化问题、允许修改的路径及停止边界。修复者只处理明确问题，不扩大当前计划项。

全局状态和交接文件不得进入计划项写入白名单。不得传入密钥，也不得包含未经用户授权的外部副作用。

出现输入 token 警告时，停止当前尝试并报告该 PLAN 项过大；不得由本 skill 改写 PLAN，也不得提高硬上限强行完成。

## 3. 准备隔离执行环境

首次实现使用 `execute --isolate`，隔离工作树只包含 `--worktree-base` 指定的内容。

前一个计划项通过后，将已验收树保存为不可变 Git 对象，作为下一个计划项的精确基础 OID。准备基础版本时必须保留用户原有工作树和索引状态。

根据 PLAN 中的修改范围生成 `--allow-path` glob，并包含该项测试与 fixture；不得使用覆盖整个仓库的通配符。

## 4. 独立委派 Cursor 实现

相对于本文件解析 `scripts/cursor_delegate.py`：

```bash
python3 <skill-dir>/scripts/cursor_delegate.py \
  --mode execute \
  --workspace <repo> \
  --isolate \
  --worktree-base <exact-oid> \
  --sandbox auto \
  --accept-allowlist-risk \
  --force \
  --model composer-2.5 \
  --allow-path 'src/seam/**' \
  --allow-path 'tests/seam/**' \
  --allow-shell git \
  --prompt-file <implementation-packet>
```

记录 `actual_workspace` 和实现委派的 `session_id`，但后续阶段不得恢复该会话。Codex 只检查 `runner.accepted` 这一结构状态；它覆盖进程、token、Git、路径白名单和 diff-check 完整性，不代表测试或验收通过。

## 5. 独立委派 Cursor 测试

针对 `actual_workspace` 启动一个全新的只读 Cursor 会话，让测试者亲自执行 PLAN 指定的全部聚焦命令：

```bash
python3 <skill-dir>/scripts/cursor_delegate.py \
  --mode ask \
  --workspace <actual-worktree> \
  --model composer-2.5 \
  --require-result-json \
  --allow-shell git \
  --allow-shell pytest \
  --prompt-file <test-packet>
```

测试结果必须包含以下 JSON 字段：

```json
{
  "status": "pass | fail",
  "commands": [
    {"command": "实际命令", "exit_code": 0, "evidence": "关键输出"}
  ],
  "failures": ["失败原因和定位"],
  "unverified": ["未执行的命令及原因"]
}
```

测试 `pass` 要求所有规定命令均已执行、退出码符合预期、`failures` 和 `unverified` 都为空。Codex 只解析和转交结果，不自行重跑命令。

## 6. 独立委派 Cursor 验证

测试委派结束后，再启动另一个全新的只读 Cursor 会话。验证者必须独立读取当前 diff，对照原始 SPEC/PLAN 逐项验收，并亲自获取必要证据；不得接收实现者或测试者的结论。

```bash
python3 <skill-dir>/scripts/cursor_delegate.py \
  --mode ask \
  --workspace <actual-worktree> \
  --model composer-2.5 \
  --require-result-json \
  --allow-shell git \
  --allow-shell pytest \
  --prompt-file <verification-packet>
```

验证结果必须包含以下 JSON 字段：

```json
{
  "status": "pass | fail",
  "findings": [
    {
      "criterion": "验收标准 ID",
      "severity": "blocking | non_blocking",
      "evidence": "文件:行号、命令及退出码，或观察到的行为",
      "repair": "明确要求的修改"
    }
  ],
  "verified_commands": ["命令 + 退出码"],
  "unverified": ["未验证的标准及原因"]
}
```

验证 `pass` 要求每项验收标准都有直接证据、没有 `blocking` 问题且 `unverified` 为空。Codex 不补充自己的语义结论。

## 7. 独立委派 Cursor 修复

实现运行器结构失败、测试失败或验证失败时，启动一个**全新的 Cursor 写入会话**。不得恢复实现者、测试者或验证者的会话。

修复发生在当前专用工作树中，因此使用 `--accept-dirty-worktree`，但不使用 `--resume`：

```bash
python3 <skill-dir>/scripts/cursor_delegate.py \
  --mode execute \
  --workspace <actual-worktree> \
  --accept-dirty-worktree \
  --sandbox auto \
  --allow-path 'src/seam/**' \
  --allow-path 'tests/seam/**' \
  --prompt-file <repair-packet>
```

修复运行的 `runner.accepted` 通过后，必须再次启动一个全新的测试会话和一个全新的验证会话。修复者不得验证自己的结果。

每个计划项最多修复三轮。以下任一情况必须停止闭环并向用户升级：同一问题连续两轮仍存在、第三轮验证失败、不同 Cursor 验证结果彼此矛盾，或修复要求超出当前 PLAN 项范围。Codex 只报告状态和证据，不自行扩展 PLAN 或接管实现。

## 8. 接受任务并进入下一项

一个计划项只有在以下三项同时成立时才可接受：

1. 最近一次实现或修复运行的 `runner.accepted` 为 true；
2. 一个独立 Cursor 测试者返回 `pass`，且没有 `failures` 或 `unverified`；
3. 另一个独立 Cursor 验证者返回 `pass`，且没有 `blocking` 或 `unverified`。

接受后，把该工作树保存为下一个任务的精确基础 OID，再按 PLAN 顺序委派下一项。必须保留用户无关的现有修改。

所有 PLAN 项完成后，分别启动一个全新的 Cursor 集成测试会话和一个全新的 Cursor 集成验证会话。只有两者均返回 `pass`，整个委派流程才算完成。

## 安全边界

Git 审计无法观察 ignored 文件、服务、数据库或外部 MCP 修改。除非用户明确授权并且 PLAN 已定义独立验证方式，否则这些内容必须排除在委派闭环之外。

提交、推送、部署、凭据变更和具有破坏性的外部操作不得进入任务包，除非用户已经明确授权。Codex 的编排职责不会扩大用户原有授权范围。
