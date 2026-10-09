# 使用示例

## 1. 快速体验（无需 Token）

```bash
python -m mcperks.cli demo
```

会用 `fixtures/` 下的示例数据跑一遍「盘点 + 规划」。注意：其中的「我的券」(`sample_my_coupons.json`) 为**明确标注的模拟数据**，用于演示算法；「可领取券」与「活动」(`sample_available_coupons.json` / `sample_campaigns.json`) 为**真实抓取的脱敏数据**。

## 2. 真实接入（WorkBuddy）

在 WorkBuddy 中按 [`SKILL.md`](../SKILL.md) 的指引，用自然语言发起请求即可。WorkBuddy 会：

1. 调用麦当劳 MCP 只读工具（query-my-coupons / query-my-account / available-coupons / campaign-calendar / query-nearby-stores / query-meals / calculate-price）。
2. 提取结构化 JSON，运行 `mcperks` 规划模块。
3. 转述结果。**默认只查询与规划，任何真实交易都会先向你确认。**

## 3. CLI 输入格式

### inventory（权益盘点）

`bundle.json`：
```json
{
  "my_coupons": [{"id":"C1","title":"满30减15","source":"my","status":"可用",
                  "expire_at":"2026-10-12","value_type":"fixed","value":15,"min_spend":30}],
  "available_coupons": [{"id":"A1","title":"9.9元中杯冰美式","source":"available","status":"可领取"}],
  "campaigns": [{"date":"2026-10-09","status":"today","title":"蓝莓爆爆珠麦旋风上新"}],
  "points": {"availablePoint":"0","currentMouthExpirePoint":"0"}
}
```
```bash
python -m mcperks.cli inventory --input bundle.json
```

### plan（预算规划）

```json
{"coupons":[ ... ],"budget":80.0,"context":{"cart_total":60.0},"days":7}
```
```bash
python -m mcperks.cli plan --input plan.json
```

### reprice（价格核算）

`calc.json` 传入 `calculate-price` 返回的 `data` 段（单位：分）：
```bash
python -m mcperks.cli reprice --input calc.json
```

## 4. 诚实性原则

- 缺失字段一律标「未知」，不编造优惠金额或有效期。
- 折扣券/未知面值的「实际可省金额」标为未知。
- `calculate-price` 失败或返回空时，不展示任何虚构价格。
- 任何下单/领券/兑换都不在本 Skill 默认行为内，需你明确确认。
