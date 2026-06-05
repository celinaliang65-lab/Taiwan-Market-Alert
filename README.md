# 🇹🇼 Taiwan Market Alert｜台股大盤定時警報系統

## 系統說明

每個交易日自動在 **09:30 / 10:30 / 11:30 / 12:30** 檢查台股加權指數，
若與**前一交易日收盤價**相比漲跌幅 **≥ ±0.3%**，即時推播 LINE 警報。

| 時間 | 版本 | 內容 |
|------|------|------|
| 09:30 | 完整版 | 台股指數 + 美股昨夜收盤（道瓊、那斯達克）+ 美元/台幣匯率 + 最新新聞 |
| 10:30 | 精簡版 | 台股指數相關數據 + 最新新聞 |
| 11:30 | 精簡版 | 台股指數相關數據 + 最新新聞 |
| 12:30 | 精簡版 | 台股指數相關數據 + 最新新聞 |

未達門檻 → 靜默，不推播。
無 2 小時內新聞 → 新聞區塊完全不顯示。

---

## 事前準備

### 1. 申請 FinMind API Token（免費）

1. 前往 [https://finmindtrade.com](https://finmindtrade.com)
2. 右上角註冊帳號並完成 email 驗證
3. 登入後點右上角 **User → 使用者資訊**
4. 複製 **api token 金鑰**（永久期限那一組）

> 免費版每小時 600 次，本系統一天只用 4 次，完全足夠。

---

### 2. 取得 LINE Channel Access Token

使用現有 LINE Bot 的 Channel Access Token 即可，與其他系統共用不衝突。

---

## GitHub Secrets 設定

前往 repo → **Settings → Secrets and variables → Actions → New repository secret**

| Secret 名稱 | 說明 | 備註 |
|------------|------|------|
| `LINE_CHANNEL_ACCESS_TOKEN` | LINE Bot Token | 必填 |
| `FINMIND_TOKEN` | FinMind API Token | 必填 |
| `LINE_USER_ID_1` | 第 1 位收件人 LINE User ID | 至少填一個，須以 U 或 C 開頭 |
| `LINE_USER_ID_2` | 第 2 位收件人 | 選填，空白自動跳過 |
| `LINE_USER_ID_3` | 第 3 位收件人 | 選填，空白自動跳過 |
| `LINE_USER_ID_4` | 第 4 位收件人 | 選填，空白自動跳過 |
| `LINE_USER_ID_5` | 第 5 位收件人 | 選填，空白自動跳過 |

> 新增或移除收件人：直接在 Secrets 填入或清空對應的 `LINE_USER_ID_N`，不需修改程式碼。
> 格式不符（非 U/C 開頭）的 ID 會自動跳過，不影響其他收件人。

---

## 排程說明

GitHub Actions 的 cron 觸發時間有時會延遲，本系統設定**提早 30 分鐘觸發**：

| 目標時間（台灣）| GitHub Actions cron（UTC）| 預計實際執行 |
|---------------|--------------------------|------------|
| 09:30 | `0 1 * * 1-5` | 09:10–09:35 |
| 10:30 | `0 2 * * 1-5` | 10:10–10:35 |
| 11:30 | `0 3 * * 1-5` | 11:10–11:35 |
| 12:30 | `0 4 * * 1-5` | 12:10–12:35 |

---

## 警報門檻調整

如需修改門檻（預設 0.3%），編輯 `market_alert.py` 第 32 行：

```python
ALERT_THRESHOLD = 0.003  # 0.3%，可改為 0.005 = 0.5%
```

---

## 手動測試

**注意：需在台股交易時間（09:00–13:30）內執行，才能取得當日即時資料。**

GitHub → **Actions → Taiwan Market Alert → Run workflow**

---

## 檔案結構

```
Taiwan-Market-Alert/
├── market_alert.py          # 主程式
├── requirements.txt         # 套件清單（requests, pytz, beautifulsoup4）
├── README.md                # 說明文件
└── .github/
    └── workflows/
        └── market_alert.yml # GitHub Actions 排程設定
```

---

## 資料來源

| 資料 | 來源 |
|------|------|
| 台股加權指數即時 + 前日收盤 | Yahoo Finance `^TWII` |
| 美股昨夜收盤（道瓊、那斯達克） | Yahoo Finance |
| 美元／台幣匯率 | Yahoo Finance |
| 大盤新聞（2 小時內） | Google News RSS |

---

## 推播卡片說明

- 上漲：紅色主題；下跌：綠色主題
- 指數顯示至小數點第二位（例如 45071.32）
- 09:30 完整版額外顯示美股與匯率區塊
- 新聞每則顯示前 30 字，無 2 小時內新聞時不顯示新聞區塊
- 底部顯示日期與推播時間
