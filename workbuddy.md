# WorkBuddy 开发记录（workbuddy.md）

> 本文件用于核验本项目是否真实使用腾讯 WorkBuddy 智能体完成开发，符合麦当劳程序员创意开发大赛「WorkBuddy 专项奖励」的联动要求。
> 记录基于本次真实开发过程整理，已对账号、Token、手机号、地址、订单等敏感信息脱敏。不含虚构对话。

## 1. 开发需求

用户要求基于已配置的麦当劳官方 MCP，完成一个可实际使用、经过测试、符合官方比赛要求的原创 Skill「麦门权益管家 / McPerks Planner」并正式报名。核心诉求：

- 整合优惠券、积分、活动日历、门店菜单与实时核价，解决「券要过期不知道 / 积分清零 / 推荐价≠结算价 / 多张券冲突」等真实问题。
- 实现 A 权益盘点、B 智能规划、C 真实核价、D 活动关联、E 自然语言交互五大功能。
- 必须有确定性业务算法 + pytest 自动化测试 + 真实 MCP 调用验证。
- 交付 GitHub Public 仓库 + 官方报名 Issue。

## 2. WorkBuddy 实际承担的工作

本次开发全程由 WorkBuddy（Agent 模式）自主完成，未要求用户手动复制粘贴文件。WorkBuddy 实际执行了：

1. **读取官方规则**：通过 WebFetch 拉取赛事仓库 README、activityGuidelines.md、CONTEST_DECLARATION.md 及 mcd-mcp-server 文档，确认参赛文件清单与提交格式。
2. **检测 MCP Schema**：通过 ToolSearch 加载 `mcd-mcp` 全部相关工具的参数 Schema。
3. **真实调用 MCP（只读）**：依次调用 `query-my-coupons`、`query-my-account`、`available-coupons`、`campaign-calendar`、`query-nearby-stores`、`query-meals`、`calculate-price`，验证连接与真实返回结构。
4. **编写业务代码**：产出 `mcperks/` 包（models / core 确定性算法 / mcp_adapter 适配层 / cli 入口）。
5. **编写并运行测试**：产出 `tests/`（12 个测试模块，52 个用例），使用系统 Python 的 pytest 9.1.1 运行并通过。
6. **生成参赛文档**：README、CONTEST_DECLARATION（原样保留）、MCP_INTEGRATION、mcp-config.example、workbuddy.md、LICENSE、.gitignore。
7. **端到端验收**：用真实抓取数据与 CLI 完成盘点和规划验收。

## 3. 真实 MCP 接入过程（脱敏）

- 接入地址 `https://mcp.mcd.cn`（Streamable HTTP），鉴权头由 WorkBuddy 已配置的 `mcd-mcp` 连接器提供，**Skill 代码中不出现 Token**。
- 真实调用结果（2026-10-09）：
  - `query-my-coupons` → 「暂无可用优惠券」（真实空结果）。
  - `query-my-account` → 返回积分字段，`availablePoint=0`，并发现敏感字段 `accountId`，已在 `mcp_adapter.parse_account` 中直接丢弃。
  - `available-coupons` → 返回 6 张可领取券（麦旋风任选、9.9元中杯冰美式 等），无面值/有效期，统一标记「未知」。
  - `campaign-calendar` → 返回 10 月多日活动（真实活动标题与日期）。
  - `query-nearby-stores`（city=上海 keyword=人民广场 beType=1）→ 返回 storeCode（例 `1450713`，已脱敏示例）。
  - `query-meals`（storeCode=1450713）→ 返回含 `currentPrice` 的餐品列表（巨无霸 ¥25.5 等）。
  - `calculate-price`（items=[1100]）→ 返回 `price=2550`（分）= ¥25.50，确认单位换算逻辑。

## 4. 关键开发迭代

- **迭代 1（Schema 校验）**：发现 `query-my-account` 字段为 `currentMouthExpirePoint`（疑似拼写），在解析层做了容错映射。
- **迭代 2（价格单位）**：麦当劳 MCP 价格单位为「分」，初次易误当「元」；在 `reconcile_price` 中统一 `/100` 换算并区分原价/优惠/应付。
- **迭代 3（安全边界）**：明确核心算法不引用任何 `create_order`/`auto-bind-coupons` 等交易工具，并以测试断言源码中不存在此类调用。
- **迭代 4（确定性）**：为所有排序补充 `coupon.id` 兜底排序键，使用注入 `now` 而非 `datetime.now()`，保证测试可复现。
- **迭代 5（测试修复）**：CLI 的 `demo` 子命令漏 `import os`，修复后 52 个用例全部通过。

## 5. 测试与修复结果

- 测试框架：pytest 9.1.1（系统 Python 3.12.5）。受沙箱网络限制，受管 Python 3.13.12 的 venv 无法连接 PyPI 安装 pytest，故使用已预装 pytest 的系统 Python 运行（未向用户环境新增任何包）。
- 用例覆盖：到期排序、积分识别、预算约束、适用条件校验、组合决策、确定性、空数据、401、429、价格失败、安全降级、无真实订单。
- 结果：**52 passed**。

## 6. 最终验证情况

- 源代码已生成，`mcperks/` 可导入、`python -m mcperks.cli` 可用。
- 核心功能（盘点/规划/核价/活动关联）已用真实抓取数据与 mock 数据双轨验证。
- 真实 MCP 调用成功：7 个只读工具已实跑；2 个交易前置工具按 Schema 适配但未实跑；交易类工具被主动禁用。
- 自动化测试 52 个全部通过。
- 参赛必需文件齐全：README、CONTEST_DECLARATION（原样）、MCP_INTEGRATION、mcp-config.example、SKILL、workbuddy（本文件）、LICENSE、.gitignore、源代码、测试、示例。
- 敏感信息检查：未在任何文件中写入真实 Token / accountId / 手机号 / 地址 / 订单。

## 7. 仍在限制内的事项（如实说明）

- 用户当前麦当劳账户「我的优惠券」与「积分」均为 0，因此「临期券/积分清零」功能在真实数据下返回空，属真实状态，未伪造数据填充。算法能力通过明确标注的模拟数据（`fixtures/sample_my_coupons.json`）在测试中验证。
- `query-store-coupons`、`query-meal-detail` 已按官方 Schema 适配，但因需要「先选门店/餐品」且非规划必需，未做真实调用（避免产生交易前置副作用）。
