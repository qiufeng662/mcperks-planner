<div align="center">

# 麦门权益管家 · McPerks Planner

**基于麦当劳官方 MCP 的优惠券 / 积分 / 活动 / 点餐决策管理 Skill**

把「不知道券何时过期、不知道积分要清零、推荐价和结算价对不上」变成「按紧迫度排序的提醒 + 预算内的可解释规划 + 真实核价」。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.12%2B-blue.svg)](https://www.python.org)
[![Tests](https://img.shields.io/badge/tests-52%20passed-brightgreen.svg)](#%E5%85%AB%E8%87%AA%E5%8A%A8%E5%8C%96%E6%B5%8B%E8%AF%95)

> ⚠️ 非官方产品：本项目为「麦当劳程序员创意开发大赛」参赛作品，由开发者独立创作，非麦当劳官方产品。输出仅供参考，餐品/价格/供应以麦当劳官方实时结果为准。

</div>

---

## 一、项目简介（中英文）

- **中文名**：麦门权益管家
- **英文名**：McPerks Planner
- **一句话**：基于麦当劳官方 MCP，把优惠券、积分、营销活动与门店菜单整合起来，帮你识别临期权益、在预算内规划消费，并用真实核价避免「推荐价 ≠ 结算价」。

**解决的问题**：普通省钱助手只是把几个 MCP 工具包装成提示词；本项目提供**确定性规划算法**与**真实价格核算**，能识别临期权益、解决多券冲突、并区分「估算价」与「实际结算价」。

## 二、功能展示

| 功能 | 说明 | 状态 |
|------|------|------|
| A. 权益自动盘点 | 汇总我的券 / 可领取券 / 积分 / 活动，输出可用、临期、无到期信息 | ✅ |
| B. 智能权益规划 | 按「紧迫度 + 保守估算可省」在预算内排序推荐，支持单次与多日规划 | ✅ |
| C. 真实价格核算 | 以 `calculate-price` 真实返回为准（分→元），区分原价/优惠/应付 | ✅ |
| D. 动态活动关联 | 营销活动与券/餐品关联，未来活动标注「待确认」 | ✅ |
| E. 自然语言交互 | 标准 `SKILL.md`，用户无需理解 MCP 工具名 | ✅ |

## 三、核心差异化价值

1. **临期不漏**：优惠券/积分即将过期会被按紧迫度排序提醒，而不是淹没在列表里。
2. **不把面值当地板**：折扣券/未知面值一律标「未知」，不写虚假可省金额。
3. **价格一致**：唯一可信价格来自 `calculate-price` 真实返回；失败时不展示任何数字。
4. **安全边界**：默认只读与规划，绝不自动下单/领券/兑换；任何交易需你明确确认。
5. **可复现**：核心算法纯函数 + 注入时间，相同输入必然得到相同结果（有测试守护）。

## 四、真实使用案例

> 以下为真实调用麦当劳 MCP 后，经本 Skill 处理的结果（已脱敏，账户真实状态为空）。

**案例 1：权益盘点（真实账户，2026-10-09）**
```
输入：查我的麦当劳优惠券、积分和活动
MCP：query-my-coupons → 暂无可用优惠券
     query-my-account → 积分 0（已脱敏 accountId）
     available-coupons → 6 张可领取券（麦旋风任选、9.9元中杯冰美式…）
     campaign-calendar → 10 月多场活动
输出：临期券 0 张；可领取券 6 张；积分余额 0，无即将过期积分；活动 2+ 场。
      提示：可先领取麦麦省券；活动「蓝莓爆爆珠麦旋风上新」今日进行中。
```

**案例 2：真实价格核算（只读，无订单）**
```
链路：query-nearby-stores(上海人民广场) → storeCode 1450713
      query-meals(1450713) → 巨无霸 code 1100
      calculate-price(items=[1100×1]) → price=2550(分)
输出：原价 ¥25.50 / 优惠 ¥0.00 / 应付 ¥25.50（已确认，单位已换算）
```

**案例 3：预算规划（演示数据，明确标注）**
```
输入：预算 ¥80，购物车约 ¥60
MCP 数据 + 演示用「我的券」(mock)：
  满30减15(10-12到期) → 估算可省 ¥15 (high)
  满40减20(10-15到期) → 估算可省 ¥20 (high)
  8折券(10-20到期)    → 估算可省 未知 (low，不臆造)
输出：推荐优先级 C1 > C2 > C3 > C4；估算合计可省 ¥45.00（保守估算，以实算为准）。
```

## 五、安装步骤

```bash
# 1. 克隆仓库
git clone https://github.com/<你的账号>/mcperks-planner.git
cd mcperks-planner

# 2. （可选）创建虚拟环境
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate

# 3. 安装测试依赖（仅运行测试需要）
pip install pytest

# 4. 运行演示（无需 Token）
python -m mcperks.cli demo
```

## 六、MCP 配置方法

在 WorkBuddy 左侧「连接器」→「自定义连接器」→「配置 MCP」中填入（**替换 `${MCD_MCP_TOKEN}` 为你的真实 Token**）：

```json
{
  "mcpServers": {
    "mcd-mcp": {
      "type": "streamablehttp",
      "url": "https://mcp.mcd.cn",
      "headers": {
        "Authorization": "Bearer ${MCD_MCP_TOKEN}"
      }
    }
  }
}
```

> 脱敏模板见 [`mcp-config.example.json`](mcp-config.example.json)。Token 仅由 WorkBuddy 连接管理，本项目代码与配置中**不包含任何真实 Token**。

## 七、Skill 使用方式

在 WorkBuddy 对话中直接用自然语言即可，例如：

- 「帮我查最近的麦当劳优惠券和积分」
- 「最近 7 天有哪些券或积分要过期？」
- 「这周预算 80 元，帮我规划最值得用的麦当劳权益」
- 「今天不一定消费，先告诉我哪些券应该优先用」
- 「帮我核一下巨无霸的价格」
- 「最近有什么活动，和我手上的券能怎么联动？」

WorkBuddy 会按 [`SKILL.md`](SKILL.md) 的指引调用麦当劳 MCP、提取结构化数据、运行 `mcperks` 规划模块并转述结果。**默认只查询与规划，任何下单/领券/兑换都会先向你确认。**

CLI 直跑（供开发者 / 非 WorkBuddy 平台）：

```bash
python -m mcperks.cli inventory --input bundle.json   # 权益盘点
python -m mcperks.cli plan      --input plan.json     # 预算规划
python -m mcperks.cli reprice   --input calc.json     # 价格核算
python -m mcperks.cli campaigns --input camp.json     # 活动关联
python -m mcperks.cli compare   --input plans.json    # 多方案比较
python -m mcperks.cli demo                            # 示例演示
```

## 八、技术架构

```text
用户自然语言
     │
     ▼
WorkBuddy Agent（按 SKILL.md）
     ├─ 调用麦当劳 MCP（只读）：query-my-coupons / query-my-account /
     │     available-coupons / campaign-calendar / query-nearby-stores /
     │     query-meals / calculate-price
     ▼
提取结构化 JSON
     │
     ▼
mcperks（确定性业务层）
  ├─ models.py      规范化的 Coupon / PointsAccount / Campaign / Meal / PriceResult
  ├─ core.py        纯函数算法：到期排序、积分识别、预算约束、适用性校验、
  │                 组合决策、确定性打分、价格换算、安全降级（无网络、可测试）
  ├─ mcp_adapter.py 真实 MCP JSON 解析 + 可选直连客户端（非必须）
  └─ cli.py         命令行入口（Agent 调用的执行层）
     │
     ▼
结构化结果 → 自然语言转述给用户
```

**设计取舍**：不引入数据库 / Docker / Redis / 独立服务；不硬编码 Token；核心算法与网络完全解耦，保证可复现与可测试。

## 九、自动化测试

- 框架：pytest（本项目开发期使用 pytest 9.1.1）
- 覆盖：优惠券到期排序、积分到期识别、预算约束、适用条件校验、组合决策、确定性、MCP 空数据、401 鉴权失败、429 限流、价格核算失败、数据不完整安全降级、**不产生未经确认的真实订单**
- 结果：**52 passed**

```bash
python -m pytest -q
```

## 十、安全和隐私说明

- 不写入真实 Token / 密钥 / 账号凭证；配置文件仅用环境变量占位符。
- 不泄露他人个人信息；MCP 返回的 `accountId` 等敏感字段在解析层直接丢弃。
- 默认只读与规划；`create-order`、`auto-bind-coupons`、`mall-create-order`、`draw-lottery` 等交易类工具被主动禁用，源码中以测试断言其不存在。
- 价格与活动具有时效性，输出以麦当劳官方实时结果为准。
- 重复执行不会因规划算法产生多次交易或修改用户权益（算法无副作用）。

## 十一、参赛说明与非官方声明

- 本仓库为「麦当劳程序员创意开发大赛」参赛作品，遵循官方活动规则与《参赛声明》（[CONTEST_DECLARATION.md](CONTEST_DECLARATION.md) 原样保留）。
- **非麦当劳官方产品**，与麦当劳官方无隶属关系，不暗示任何官方背书。
- 麦当劳®、麦享会® 等为其各自权利人的商标；本项目仅作技术演示与学习用途。
- 活动数据、价格、券面额以麦当劳官方渠道实时结果为准。

## 十二、目录结构

```text
mcperks-planner/
├─ README.md                 # 项目说明（本文件）
├─ SKILL.md                  # WorkBuddy Skill 定义
├─ CONTEST_DECLARATION.md    # 参赛声明（原样保留，不可改）
├─ MCP_INTEGRATION.md        # MCP 接入说明
├─ mcp-config.example.json   # 脱敏 MCP 配置模板
├─ workbuddy.md              # WorkBuddy 开发记录
├─ LICENSE / .gitignore
├─ mcperks/                  # 业务代码
│  ├─ models.py  core.py  mcp_adapter.py  cli.py
├─ tests/                    # pytest 自动化测试（52 用例）
├─ fixtures/                 # 示例数据（真实抓取 + 明确标注的 mock）
└─ examples/                 # 使用示例
```

---

<p align="center">Made with WorkBuddy · 麦门权益管家 McPerks Planner</p>
