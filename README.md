# 🇹🇼 Taiwan Market Alert｜台股大盤定時警報系統

## 系統說明

每個交易日自動在 **09:30 / 10:30 / 11:30 / 12:30** 檢查台股加權指數，
若與**前一交易日收盤價**相比漲跌幅 **≥ ±0.3%**，即時推播 LINE 警報。

|時間   |版本 |內容                             |
|-----|---|-------------------------------|
|09:30|完整版|台股指數 + 美股昨夜收盤（道瓊、那斯達克）+ 美元/台幣匯率|
|10:30|精簡版|台股指數相關數據                       |
|11:30|精簡版|台股指數相關數據                       |
|12:30|精簡版|台股指數相關數據                       |

未達門檻 → 靜默，不推播。

-----

## GitHub Secrets 設定

前往 repo → **Settings → Secrets and variables → Actions → New repository secret**

|Secret 名稱                  |說明                           |必填     |
|---------------------------|-----------------------------|-------|
|`LINE_CHANNEL_ACCESS_TOKEN`|LINE Bot Channel Access Token|✅      |
|`FINMIND_TOKEN`            |FinMind API Token（提高抓取配額）    |✅      |
|`LINE_USER_ID_1`           |第 1 位收件人 LINE User ID        |✅ 至少填一個|
|`LINE_USER_ID_2`           |第 2 位收件人                     |⬜ 選填   |
|`LINE_USER_ID_3`           |第 3 位收件人                     |⬜ 選填   |
|`LINE_USER_ID_4`           |第 4 位收件人                     |⬜ 選填   |
|`LINE_USER_ID_5`           |第 5 位收件人                     |⬜ 選填   |


> **新增或移除收件人**：直接在 Secrets 新增 / 清空對應的 `LINE_USER_ID_N` 即可，不需修改程式碼。

-----

## 警報門檻調整

如需修改門檻（預設 0.3%），編輯 `market_alert.py` 第 22 行：

```python
ALERT_THRESHOLD = 0.003  # 0.3%，可改為 0.005 = 0.5%
```

-----

## 手動測試

在 GitHub → **Actions → Taiwan Market Alert → Run workflow** 可手動觸發測試。

-----

## 資料來源

|資料        |來源           |
|----------|-------------|
|台股加權指數（即時）|FinMind API  |
|美股昨夜收盤    |Yahoo Finance|
|美元/台幣匯率   |Yahoo Finance|

-----

## 推播卡片範例

- **上漲**：紅色主題，顯示漲幅超過 +0.3% 警報
- **下跌**：綠色主題，顯示跌幅超過 -0.3% 警報
- 09:30 版本額外顯示美股與匯率區塊
