# 02｜Workflow：用 superpowers + mattpocock/skills 討論專案方向

> 目的：不是一開始就寫程式，而是先讓 AI 用固定流程「逼問」我，把專案方向、範圍、資料限制講清楚，再拆成可執行的任務。
> 兩套 skills 都是 [Skill Leaderboard](https://www.skillleaderboard.com/) 規劃類排名前兩名（#1 obra/superpowers、#2 mattpocock/skills）。

---

## 0. 安裝（一次性）

✅ 已於 2026-10-28 安裝完成（使用者層級，所有專案都能用）：superpowers 6.4.2、mattpocock-skills 1.3.1。

實際可用的安裝指令（Claude 桌面版內建的 CLI 不在 PATH，要用完整路徑或在終端機版 `claude` 執行）：

```bash
claude plugin install superpowers@anthropic-plugin-directory
```

```bash
claude plugin marketplace add mattpocock/skills
```

```bash
claude plugin install mattpocock-skills@mattpocock
```

> mattpocock-skills 不在內建的 Anthropic 外掛目錄裡，所以要先加作者的 GitHub marketplace。

**裝好後要開一個新 session 才會載入。** 在專案資料夾的新 session 先跑一次：

```
/setup-matt-pocock-skills
```

它會問 issue tracker（選 GitHub Issues 或 本地 Markdown 都可以）和文件要放哪裡（建議 `docs/`）。

---

## 1. 整體流程圖

```
 ┌───────────── 階段 A：想清楚（本週，諮詢前完成）─────────────┐
 │                                                              │
 │  ① /brainstorming        (superpowers)  發散：列出 3~4 個方向 │
 │          ↓                                                   │
 │  ② /grill-me             (mattpocock)   收斂：逐條被逼問      │
 │          ↓                                                   │
 │  ③ /grill-with-docs      (mattpocock)   產出名詞表 + 決策紀錄 │
 │          ↓                                                   │
 │  ④ /to-spec              (mattpocock)   寫成專案規格書        │
 │                                                              │
 └──────────────────────────────┬───────────────────────────────┘
                                │  ← 帶去給 Adam 老師諮詢
 ┌───────────── 階段 B：拆任務（諮詢後）─────────────────────────┐
 │  ⑤ /to-tickets           (mattpocock)   拆成有相依關係的票     │
 │  ⑥ writing-plans         (superpowers)  每張票寫成實作步驟     │
 └──────────────────────────────┬───────────────────────────────┘
                                │
 ┌───────────── 階段 C：做出來（11 月）──────────────────────────┐
 │  ⑦ executing-plans / implement   一張票一張票做              │
 │     ├ prototype   (mattpocock)  先做丟棄式原型驗證想法        │
 │     ├ tdd         資料清理函式用測試保護                      │
 │     └ systematic-debugging      遇到怪資料時用                │
 │  ⑧ verification-before-completion  確認成果真的跑得動        │
 │  ⑨ /retro          每週回顧，調整做法                         │
 └──────────────────────────────────────────────────────────────┘
```

| 步驟 | Skill | 來源 | 這個專案拿它做什麼 | 產出檔案 |
|---|---|---|---|---|
| ① | `brainstorming` | superpowers | 根據資料能做的事，發散出幾個專案方向 | `docs/brainstorm.md` |
| ② | `grill-me` | mattpocock | 對選中方向逐條追問：誰會用、要預測什麼、資料夠不夠、6 週做得完嗎 | 對話紀錄 |
| ③ | `grill-with-docs` | mattpocock | 把「站點、車柱、租借紀錄、淨流量、缺車」等名詞定義清楚，記下關鍵決策 | `docs/glossary.md`、`docs/adr/` |
| ④ | `to-spec` | mattpocock | 把討論結果寫成規格書 | `docs/spec.md` |
| ⑤ | `to-tickets` | mattpocock | 拆成任務票（例如：收集器 → 清理 → EDA → 模型 → 儀表板） | GitHub Issues |
| ⑥ | `writing-plans` | superpowers | 每張票寫出檔案路徑、步驟、怎麼驗證 | `docs/plans/*.md` |
| ⑦ | `executing-plans` / `implement` | 兩者 | 照計畫實作 | 程式碼 |
| ⑧ | `verification-before-completion` | superpowers | 交付前跑一次完整流程 | — |
| ⑨ | `retro` | mattpocock | 每週回顧 | — |

---

## 2. 每一步要丟給 AI 的提示詞（可直接複製）

### ① brainstorming
```
/brainstorming
我要做一個 YouBike 資料分析專題，作為 12 月求職作品。
可用資料：臺北市 YouBike2.0 即時站點 JSON（每分鐘更新）、2020/04 起每月租借紀錄（約 76 個月）、
TDX 運輸資料、中央氣象署天氣資料。
我過去做過：GitHub Actions 每日排程選股、LINE Bot 推播、多模型每日追蹤驗證。
時間：11/7 ~ 12/中，一個人。請提出 3~4 個方向並比較。
資料定義請參考 docs/01_資料來源與資料定義.md。
```

### ② grill-me
```
/grill-me
我選定方向：「YouBike 站點供需預測與缺車預警」。請一題一題逼問我，直到規格每個分支都定案。
```
預期會被問到、要先想好答案的問題：
1. 使用者是誰？（通勤族 / 營運調度人員 / 都市規劃）
2. 預測目標是「站點可借車數」還是「每小時淨流量（借出 − 歸還）」？
3. 即時資料沒有歷史，要從哪天開始自己收集？收集頻率？存在哪？
4. 要涵蓋全臺北 1,800 站，還是先挑某一區（如大安區、信義區）？
5. 模型要贏過什麼 baseline？（例如「上週同一時段」）
6. 成果形式：儀表板、LINE Bot、還是兩者？

### ③ grill-with-docs
```
/grill-with-docs
請根據剛才的結論建立 docs/glossary.md，並把「預測目標」「資料範圍」「收集方式」三個決策寫成 ADR。
```

### ④ to-spec → ⑤ to-tickets
```
/to-spec
/to-tickets
```

---

## 3. 本次已先跑過的方向討論（brainstorming 結果）

> 以下是我先用 brainstorming 的方式整理出的方向，正式諮詢前會再用 `grill-me` 逐條確認。

| 方向 | 內容 | 用到的資料 | 技術亮點 | 難度 | 求職展示度 |
|---|---|---|---|---|---|
| **A. 站點供需預測＋缺車預警**（建議主軸） | 預測各站未來 30~60 分鐘「借不到車／還不了車」的機率，LINE Bot 推播 | 即時快照（自建收集）＋歷史租借紀錄＋天氣 | 時間序列、分類模型、GitHub Actions 排程、LINE Bot | 中高 | ★★★★★ |
| B. 通勤流動（OD）分析 | 找出熱門路線、早晚潮汐站點、捷運接駁熱區 | 歷史租借紀錄 | 網路分析、地圖視覺化 | 中 | ★★★★ |
| C. 調度建議 | 根據預測產生「哪些站要補車／移車」清單 | A 的預測結果 | 最佳化 | 高 | ★★★★ |
| D. 外部因素分析 | 天氣、假日、距捷運站遠近對使用量的影響 | 歷史紀錄＋天氣＋站點座標 | 迴歸／特徵重要度 | 低中 | ★★★ |

**建議組合：A 為主軸，B、D 當 EDA 章節，C 為加分項（時間夠才做）。**

理由：
- A 能直接沿用過去 `stock-system`（GitHub Actions 排程＋LINE Bot）與 `stock-ml-tracker`（多模型每日驗證）的經驗，作品集故事連貫。
- B、D 只需要歷史資料，第一週就能做出圖，降低風險。
- **關鍵限制**：官方沒有提供「各站每分鐘車數」的歷史資料，只有租借紀錄。所以要馬上開始自己每 10 分鐘收集即時快照，越早開始，訓練資料越多。

---

## 4. 待老師確認的決策點

見 [04_諮詢問題集.md](04_諮詢問題集.md)。
