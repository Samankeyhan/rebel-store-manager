# Calculations

Every formula the UI depends on, with the worked numbers that appear in the sample screens. Money is integer Toman; round only when displaying, except where noted.

## 1. Order profit (record sale, order detail, orders list, reports)

```
itemsGross   = Σ (qty × unitPrice)
discountSum  = Σ lineDiscount
itemsNet     = itemsGross − discountSum
customerTotal= itemsNet + shippingCharge          ← what the customer pays
productCost  = Σ (qty × product.cost at time of sale)
profit       = customerTotal − productCost − kitCost − postageEstimate − transactionFee
margin       = profit ÷ customerTotal
```

- If any line's product has `cost == null`, `profit` is **unknown** → display «نامشخص», never 0.
- `kitCost` = cost of the chosen packaging kit at the time of sale (see §5), 0 for «بدون بسته‌بندی».
- `postageEstimate` = the store-wide estimate (§2) if the channel has postage on, else 0.
- Worked example (sample order INV-000042 / the default record-sale form):
  `2,450,000 + 2×290,000 = 3,030,000` − `80,000` = `2,950,000` + `180,000` = **3,130,000**;
  cost `1,380,000 + 2×95,000 = 1,570,000`; kit `95,000`; postage `199,273`; fee `30,000`;
  profit = `3,130,000 − 1,570,000 − 95,000 − 199,273 − 30,000` = **1,235,727** (margin ≈ ۳۹٪).

### Shipping result for one order (shown as a note in the summary)
```
shippingResult = shippingCharge − (kitCost + postageEstimate)
               = 180,000 − (95,000 + 199,273) = −114,273
```

## 2. Postage estimate (store-wide, one number)

```
estimate = Σ payment.totalPaid ÷ Σ payment.ordersShipped      over the last N payments
N is a setting, default 3
```
- Current sample: `(3,960,000 + 3,400,000 + 3,600,000) ÷ (18 + 17 + 20)` = `10,960,000 ÷ 55` = **199,273**.
- It is **not** the mean of the three per-order rates (that would be 200,000). Always show the hint «جمع پرداختی ÷ جمع سفارش‌ها».
- Channels only switch it on/off: وب‌سایت، اینستاگرام، عمده‌فروشی = on; حضوری، سایر = off.
- The estimate is **copied onto the order at save time**. Changing the estimate later never rewrites past orders; the difference surfaces as «مغایرت هزینه پست» in the P&L (§7).
- Adding the pending sample payment (4,600,000 / 20 orders) makes the last three `(4,600,000 + 3,960,000 + 3,400,000) ÷ (20 + 18 + 17)` = `11,960,000 ÷ 55` = **217,455** (+18,182).

## 3. Weighted-average cost (purchases and production)

```
newAverage = (stockOnHand × currentAverage + incomingValue) ÷ (stockOnHand + incomingQty)
```
- Purchase example: 38 blank discs at 620,000 + 50 bought for 33,500,000 (unit 670,000)
  → `(38 × 620,000 + 33,500,000) ÷ 88` = **648,409**.
- Past orders/productions are never re-costed.

## 4. Production batch

```
batchCost = Σ (perUnitMaterial.qty × unitCost × batchQty)
          + Σ (perBatchMaterial.qty × unitCost)
unitCost  = batchCost ÷ batchQty
newAverage= (productStock × productCost + batchCost) ÷ (productStock + batchQty)
maxBuildable = min over per-unit goods materials of floor(material.stock ÷ recipeQty)
```
- Sample recipe «وینیل آلبوم اول»: per unit → صفحه خام 620,000 + کاور 180,000 = 800,000; per batch → مسترینگ 12,000,000 + طراحی جلد 4,000,000 = 16,000,000.
- 30 units: batch `40,000,000`, unit `1,333,333`, average `(14 × 1,380,000 + 40,000,000) ÷ 44` = **1,348,182**.
- 50 units: shortage — صفحه خام needs 50, stock 38 (short 12); کاور needs 50, stock 45 (short 5); `maxBuildable = 38`.
- Service-type materials (`type: service`) have no stock and never cause a shortage.

## 5. Packaging kit cost and availability

```
kitCost   = Σ (qtyPerKit × material.currentUnitCost)
kitsReady = min over materials of floor(material.stock ÷ qtyPerKit)
```
- جعبه استاندارد = کارتن 1×60,000 + نوار چسب 0.1×150,000 + کاغذ پرکننده 0.2×90,000 + برچسب 1×2,000 = **95,000**; limiting material کاغذ پرکننده (1.5 kg) → **7 kits**.
- جعبه وینیل = 95,000 + 15,000 + 18,000 + 2,000 + محافظ گوشه 10,000 = **140,000**.
- پاکت کوچک = پاکت حباب‌دار 24,000 + برچسب 2,000 + نوار چسب 0.06×150,000 = **35,000**.
- بدون بسته‌بندی = 0.
- Kit cost is computed from *current* material costs, so it changes after a purchase; the value copied onto an order is the cost at sale time.

## 6. Stock effects by order status

| Status | Stock | Allowed transitions | Cancel | Refund |
|---|---|---|---|---|
| پیش‌نویس | not reserved | در انتظار، پرداخت‌شده، تکمیل‌شده | yes | no |
| در انتظار | deducted | پرداخت‌شده، تکمیل‌شده | yes | no |
| پرداخت‌شده | deducted | تکمیل‌شده | yes | yes |
| تکمیل‌شده | deducted | — | no | yes |
| لغوشده / مرجوعی | returned | — | no | no |

- **Cancel** (unshipped only): products **and** the packaging kit return to stock. No postage cost is recorded (nothing was posted). The only loss is the transaction fee, if the order had one. Money already received must be returned to the customer (recorded as a refund of money, outside the app).
- **Refund** (paid/completed): **products only** return to stock. The kit is consumed, postage was paid, the fee is not recoverable → `refundLoss = kitCost + postageEstimate + transactionFee` (sample: `140,000 + 199,273 + 31,000 = 370,273`), and the order's profit becomes `−refundLoss`. **No refund amount is captured in the app** — only the status and an optional reason.

## 7. Profit & loss statement (period report)

```
itemsRevenue
+ shippingRevenue
= totalRevenue
− costOfGoodsSold                  (product cost recorded on each order)
− packaging                        (kit cost recorded on each order)
− postageEstimated                 (estimate recorded on each order)
− transactionFees
= grossProfit
− postageVariance                  (actual paid to the post office − estimates recorded on orders)
− refundAndCancelLosses
− waste                            (ONLY ضایعات; stock corrections never appear here)
− operatingExpenses
= netProfit
```
- Sample month (شهریور ۱۴۰۵): 174,900,000 + 11,520,000 = **186,420,000**; −91,336,000 −7,120,000 −14,347,656 −1,260,000 = **72,356,344**; −412,344 −1,610,000 −1,288,000 −27,000,000 = **42,046,000** (۲۲٫۶٪).
- `postageEstimated` = 72 shipped orders × 199,273 = 14,347,656. `postageVariance` = 14,760,000 − 14,347,656 = 412,344.
- Drafts are excluded from every report. Cancelled and refunded orders leave revenue and appear only in `refundAndCancelLosses`.

## 8. Waste vs. stock correction

- **ضایعات (waste)** always decreases stock and is a real loss. Value = `qty × item.cost on the day it was recorded`, stored with the record; later cost changes never alter it. Appears in the P&L «ضایعات» line and in the waste report.
- **اصلاح موجودی (correction)** may be + or −. It only fixes the count and the inventory value. It **never** appears in the P&L or the waste report.
- A correction that adds stock may carry an optional unit cost; if given, it updates the weighted average by §3, otherwise the existing average is used for the added units.

## 9. Profit distribution (partners)

```
periodNetProfit    = net profit of the chosen Jalali period (§7)
undistributedTotal = carried-over undistributed + periodNetProfit
share(partner)     = amountToDistribute × partner.percent ÷ 100
remaining          = undistributedTotal − amountToDistribute
```
- Sample: carried over 12,400,000 + 42,046,000 = **54,446,000**; distributing 40,000,000 → 24,000,000 / 10,000,000 / 6,000,000; remaining 14,446,000.
- Blocking: partner percentages must sum to exactly 100; the period must not overlap any previously distributed period.
- Warning + explicit confirmation: `amountToDistribute > undistributedTotal` (sample: 60,000,000 → over by 5,554,000, remaining −5,554,000).
