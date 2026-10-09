---
name: 麦门权益管家 / McPerks Planner
description: 基于麦当劳官方 MCP 的优惠券、积分、营销活动与点餐决策管理 Skill。当用户需要查询麦当劳优惠券/积分/活动、识别临期权益、在预算内规划麦当劳消费、或核价时使用。默认只做查询与规划，绝不自动下单或兑换。
---

# 麦门权益管家 McPerks Planner

一个把「麦当劳官方 MCP 真实数据」与「确定性权益规划算法」结合的 Skill。它解决的核心问题：
用户不知道优惠券/积分什么时候过期、不知道哪些券真正划算、不知道未来几天怎么安排麦当劳消费、以及推荐价和结算价不一致。

## 何时使用本 Skill

- 「帮我查一下我的麦当劳优惠券 / 积分 / 活动」
- 「最近 7 天有哪些优惠券或积分要过期？」
- 「我这周预算 80 元，帮我规划最值得用的麦当劳权益」
- 「今天不一定消费，先告诉我哪些券应该优先用」
- 「比较几种使用方案 / 帮我核价」
- 「最近有什么麦当劳活动，和我手上的券能怎么联动」

## 安全底线（必须遵守）

1. **默认只读与规划**：只调用查询类 MCP（见下），绝不调用 `create-order`、`cancel-order`、`auto-bind-coupons`、`mall-create-order`、`draw-lottery`、`party-order-create` 等任何有交易副作用的工具。
2. **任何真实交易（下单/领券/兑换/抽奖）都必须先向用户明确确认**，得到肯定答复后再由用户本人或在其授权下执行。
3. **不展示虚构价格**：只有 `calculate-price` 真实返回时才展示到手价；失败时明确说「价格核算暂不可用，以官方结算页为准」。
4. **不臆造优惠金额**：优惠券面值不等于实际可省金额；折扣券/未知面值一律标「未知」，不写具体可省数字。
5. **不泄露敏感信息**：MCP 返回的 `accountId`、手机号、地址、订单号等一律脱敏，不写入任何产出文件。
6. **不硬编码 Token**：Token 仅来自 WorkBuddy 已配置的 mcd-mcp 连接，Skill 代码与配置中不得出现真实 Token。

## 可用 MCP 工具（只读，优先使用）

| 意图 | MCP 工具 | 关键参数 |
|------|----------|----------|
| 我的优惠券 | `mcp__mcd-mcp__query-my-coupons` | page, pageSize |
| 我的积分 | `mcp__mcd-mcp__query-my-account` | 无 |
| 可领取券 | `mcp__mcd-mcp__available-coupons` | 无 |
| 活动日历 | `mcp__mcd-mcp__campaign-calendar` | specifiedDate(可选) |
| 附近门店 | `mcp__mcd-mcp__query-nearby-stores` | beType, searchType, city, keyword |
| 餐品列表 | `mcp__mcd-mcp__query-meals` | storeCode, orderType, beType |
| 餐品详情 | `mcp__mcd-mcp__query-meal-detail` | storeCode, code, orderType, beType |
| 门店可用券 | `mcp__mcd-mcp__query-store-coupons` | storeCode, orderType, beType |
| 价格核算 | `mcp__mcd-mcp__calculate-price` | storeCode, items, orderType, beType |

## 标准工作流

### 功能 A：权益自动盘点
1. 调用 `query-my-coupons`、`query-my-account`、`available-coupons`、`campaign-calendar`（按需）。
2. 把返回文本中的结构化字段提取为如下 JSON，保存为 `bundle.json`：
   ```json
   {
     "my_coupons": [{"id":"...","title":"...","source":"my","status":"可用",
                     "expire_at":"YYYY-MM-DD 或 null","value_type":"fixed|percent|unknown",
                     "value":数字或null,"min_spend":数字或null,"conditions":"..."}],
     "available_coupons": [ ... 同上，source 为 available ... ],
     "campaigns": [{"date":"YYYY-MM-DD","status":"past|today|future","title":"...","description":"..."}],
     "points": {"availablePoint":"...","currentMouthExpirePoint":"...","nextMouthExpirePoint":"..."}
   }
   ```
   缺失字段一律写为 `null`，**不要编造**。
3. 运行：`python -m mcperks.cli inventory --input bundle.json`，把 JSON 结果用自然语言转述给用户。

### 功能 B：智能权益使用规划
1. 在 bundle 基础上，构造 `plan.json`：`{"coupons":[...全部 my/available 券...],"budget":数字或null,"context":{"cart_total":数字或null,"store":"门店码"},"days":7}`。
2. 运行：`python -m mcperks.cli plan --input plan.json`。
3. 向用户说明：临期券优先、估算可省金额（含置信度）、预算是否够用、是否需选好具体餐品后再核价。

### 功能 C：真实价格核算
1. 用户选定餐品后，调用 `query-nearby-stores` → `query-meals` 拿到 storeCode 与 productCode。
2. 调用 `calculate-price`（**只读、不产生订单**）拿到真实价格（单位为「分」）。
3. 运行：`python -m mcperks.cli reprice --input '{"calc_data": <calculate-price 返回 data 段>}'`。
4. 展示「原价 / 优惠 / 应付（元）」，并标注已确认；若有配送费/餐具费等不确定项，单独提示。
5. 若 `calculate-price` 失败/返回空：明确告知用户价格核算暂不可用，不展示任何数字。

### 功能 D：动态活动关联
1. 运行：`python -m mcperks.cli campaigns --input '{"campaigns":[...],"coupons":[...],"meals":[...]}'`。
2. 未来活动一律标注「待确认」，不承诺未来优惠必然有效。

### 功能 E：多方案比较 / 重新核价
1. 运行：`python -m mcperks.cli compare --input '{"plans":[ plan1, plan2 ]}'`。
2. 用户改了餐品或券后，重复功能 C 重新核价。

## 快速自检（demo）

`python -m mcperks.cli demo` 会用随仓库附带的示例数据跑一遍盘点+规划，便于用户理解能力边界（注意：其中的「我的券」为明确标注的模拟数据，可领取券与活动为真实抓取）。

## 备注

- 本 Skill 的确定性算法位于 `mcperks/core.py`，全部有 pytest 覆盖；相同输入必然得到相同输出。
- 仓库根目录 `mcperks/` 为业务代码，`tests/` 为自动化测试，`fixtures/` 为示例数据。
- 本项目为非官方、仅供参赛与学习使用的创意作品。
