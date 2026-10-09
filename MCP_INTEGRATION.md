# MCP 接入说明（MCP_INTEGRATION.md）

本项目真实使用麦当劳中国官方 MCP Server 能力。本文记录实际使用的 Server、工具、调用链路、典型输入输出与业务价值，并明确区分「已真实调用验证」「仅单元测试覆盖（模拟数据）」与「尚未验证」。

## 1. 接入的 MCP Server

| 项 | 值 |
|----|----|
| 服务名（WorkBuddy 连接器） | `mcd-mcp` |
| 接入地址 | `https://mcp.mcd.cn` |
| 传输协议 | Streamable HTTP |
| 鉴权方式 | `Authorization: Bearer <MCP Token>`（Token 由用户在 WorkBuddy 配置，Skill 代码中不出现） |
| 官方文档 | https://github.com/M-China/mcd-mcp-server |
| 频率限制 | 每 Token 每分钟最多 600 次（超限返回 429） |

> Token 获取：登录 https://open.mcd.cn/mcp → 控制台 → 激活 → 复制 Token。

## 2. 实际使用的工具与状态

| MCP 工具 | 用途 | 接入状态 |
|----------|------|----------|
| `query-my-coupons` | 查询我的优惠券 | ✅ 真实调用验证（返回「暂无可用优惠券」） |
| `query-my-account` | 查询积分账户 | ✅ 真实调用验证（返回积分/到期字段） |
| `available-coupons` | 查询可领取的麦麦省券 | ✅ 真实调用验证（返回券列表） |
| `campaign-calendar` | 查询当月营销活动 | ✅ 真实调用验证（返回多日活动） |
| `query-nearby-stores` | 查询附近门店 | ✅ 真实调用验证（返回 storeCode 等） |
| `query-meals` | 查询门店餐品与价格 | ✅ 真实调用验证（返回餐品/现价） |
| `calculate-price` | 价格核算（只读） | ✅ 真实调用验证（巨无霸 ¥25.5，单位分） |
| `query-store-coupons` | 指定门店可用券 | ⚠️ 已按 Schema 适配，未做真实调用（需先选门店且为交易前置） |
| `query-meal-detail` | 餐品详情/套餐组成 | ⚠️ 已按 Schema 适配，未做真实调用 |
| `create-order` / `auto-bind-coupons` / `mall-create-order` 等 | 下单/领券/兑换 | 🚫 主动禁用：本项目默认只查询与规划，绝不自动执行交易类操作 |

## 3. 典型调用链路

### 链路 A：权益盘点（功能 A）
```
query-my-coupons  → 提取结构化 JSON
query-my-account  → 提取积分/到期
available-coupons → 提取可领取券
campaign-calendar → 提取活动
        │
        ▼
python -m mcperks.cli inventory --input bundle.json
        │
        ▼
标准化报告：临期券 / 无到期信息 / 活动 / 积分风险
```

### 链路 B：价格核算（功能 C，只读无订单）
```
query-nearby-stores (beType=1, city, keyword)
        → storeCode (例: 1450713)
query-meals (storeCode, orderType=1, beType=1)
        → productCode (例: 1100 巨无霸)
calculate-price (storeCode, items=[{productCode:1100,quantity:1}], orderType=1, beType=1)
        → data 段（单位：分）
        │
        ▼
python -m mcperks.cli reprice --input '{"calc_data": <data 段>}'
        → 原价/优惠/应付（元），并标记已确认
```

### 链路 C：活动关联（功能 D）
```
campaign-calendar → campaigns[]
query-my-coupons → coupons[]
        │
        ▼
python -m mcperks.cli campaigns --input '{"campaigns":[...],"coupons":[...],"meals":[...]}'
        → 关联建议；未来活动统一标注「待确认」
```

## 4. 真实返回结构样例（已脱敏）

### 4.1 query-my-account（真实，2026-10-09）
```json
{
  "success": true, "code": 200, "message": "请求成功",
  "data": {
    "availablePoint": "0",
    "accountId": "02006******（已脱敏，代码层直接丢弃）",
    "accumulativePoint": "0",
    "currency": "麦享会积分",
    "currentMouthExpirePoint": "0",
    "expiredPoint": "0",
    "frozenPoint": "0",
    "nextMouthExpirePoint": "0",
    "usedPoint": "0"
  }
}
```
> 说明：返回含 `accountId` 等敏感字段，Skill 在 `mcp_adapter.parse_account` 中直接丢弃，绝不进入模型或文件。当前账户积分与优惠券均为 0，属真实状态。

### 4.2 calculate-price（真实，巨无霸，单位：分）
```json
{
  "productOriginalPrice": 2550, "productPrice": 2550,
  "originalPrice": 2550, "discount": 0, "price": 2550,
  "productList": [
    {"productCode": "1100", "productName": "巨无霸", "quantity": 1,
     "originalSubtotal": 2550, "subtotal": 2550}
  ],
  "takeWayList": [
    {"code": "eat-in", "title": "堂食", "subtitle": "店内用餐"},
    {"code": "locker-out", "title": "外带", "subtitle": "店外取餐柜"}
  ]
}
```
> Skill 将「分」自动换算为「元」：2550 分 → ¥25.50。

### 4.3 available-coupons（真实，已脱敏标题）
返回若干「可领取」券，如：麦旋风任选、巧克力味厚松饼猪柳蛋套餐、薯薯任选、免费脆薯饼、人气麦旋风买一送一、9.9元中杯冰美式。此类券无面值/有效期字段，统一标记为「未知」，不臆造金额。

## 5. 业务价值

- **临期预警**：把「有券但不知道何时过期」转化为按紧迫度排序的提醒。
- **积分防清零**：识别本月/下月将过期积分并提示使用。
- **预算规划**：在用户预算内，按「紧迫度 + 保守估算可省」给出可解释的消费建议。
- **价格一致**：以 `calculate-price` 真实返回为唯一可信价格来源，杜绝「推荐价 ≠ 结算价」。
- **安全边界**：默认只读；任何交易需用户明确确认，从根本上避免误下单。

## 6. 错误处理与降级

| 场景 | 处理 |
|------|------|
| 返回空数据（如我的券为空） | 明确提示「当前未查询到」，不做伪数据填充 |
| 401 鉴权失败 | 抛出 `MCPAuthError`，提示检查 Token |
| 429 限流 | 抛出 `MCPRateLimitError`，提示降频 |
| calculate-price 失败/空 | 抛出 `PriceCalcUnavailable`，不展示任何虚构金额 |
| 字段缺失 | 置为 `null`，标记为「未知」，不臆造 |

## 7. 验证状态小结

- ✅ 已真实调用验证：query-my-coupons、query-my-account、available-coupons、campaign-calendar、query-nearby-stores、query-meals、calculate-price。
- ⚠️ 已按 Schema 适配但未真实调用：query-store-coupons、query-meal-detail（需交易前置的门店/餐品上下文，且非规划必需）。
- 🚫 主动禁用（安全）：create-order、auto-bind-coupons、mall-create-order、draw-lottery、party-order-create 等交易类工具。
- 🧪 单元测试：以上所有工具对应的解析、规划、降级逻辑均有 pytest 覆盖（见 `tests/`），共 52 个用例全部通过。
