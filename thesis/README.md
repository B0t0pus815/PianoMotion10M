# 論文檔案說明

本 `thesis/` 目錄包含畢業論文「AI 鋼琴學習」全部文字材料。

## 章節結構

| 檔案 | 章節 | 行數 | 角色 |
|---|---|---|---|
| `ch1_introduction.md` | 第一章 緒論 | 54 | 動機、RQ、貢獻、結構 |
| `ch2_related_work.md` | 第二章 文獻回顧 | 90 | 指法決策 / 動作生成 / 教學系統 |
| `ch3_system_architecture.md` | 第三章 系統架構 | 190 | Dual-Track + Stage A/B/C |
| `ch4_evaluation.md` | 第四章 評估方法與結果 | 225 | corpus audit + finger distribution |
| `ch5_implementation.md` | 第五章 系統實作 | 210 | 工程細節 + 復現性 |
| `ch6_user_experience.md` | 第六章 使用者互動設計 | 176 | UI 元件 + 互動流程 |
| `ch7_conclusion.md` | 第七章 結論與未來工作 | 87 | findings + limitations + future |

**總計：~1032 行 markdown，預估 PDF 30-40 頁。**

## Defense 套件

| 檔案 | 用途 |
|---|---|
| `defense_slides.md` | Marp 格式 slides (15-20 頁) |
| `defense_qa.md` | 預期 Q&A + 建議答覆 |
| `references.bib` | BibTeX 文獻檔 (12 條 entries) |

## 工作流程

### 1. 編輯（你做）

直接編輯各 `.md` 檔案。每章獨立，互引用透過 footnote 與 `第 N 章` 文字 reference。

### 2. 轉檔 PDF/Word/LaTeX

#### 單章
```bash
pandoc ch4_evaluation.md \
    --bibliography=references.bib \
    --citeproc \
    -o ch4_evaluation.docx
```

#### 全本合併成單一檔
```bash
pandoc ch1_introduction.md ch2_related_work.md ch3_system_architecture.md \
       ch4_evaluation.md ch5_implementation.md ch6_user_experience.md \
       ch7_conclusion.md \
    --bibliography=references.bib \
    --citeproc \
    --toc --toc-depth=2 \
    -o thesis_full.pdf
```

#### 轉 LaTeX (適合大幅編輯)
```bash
pandoc ch*.md --bibliography=references.bib \
    --citeproc -t latex -o thesis_full.tex
```

#### Defense slides
```bash
# Marp CLI
marp defense_slides.md -o defense_slides.pdf
marp defense_slides.md -o defense_slides.html  # 互動式
marp defense_slides.md -o defense_slides.pptx  # PowerPoint
```

### 3. 引用 (Citation)

各章中目前使用 `[^key]` markdown footnote 語法。轉換成 BibTeX 風格時用 `[@key]`:

```markdown
<!-- footnote 風格 (目前) -->
Ramoneda 2022 [^ramoneda22] 提出...
[^ramoneda22]: Ramoneda, P. et al. (2022)...

<!-- BibTeX 風格 (pandoc + .bib) -->
Ramoneda 2022 [@ramoneda2022] 提出...
```

`references.bib` 已包含對應 key (`parncutt1997`, `nakamura2014`, `ramoneda2022`, `liu2024pianomotion` 等)。

## 章節依賴關係

```
ch1 (motivation, RQ)
  ├─→ ch2 (positions against literature)
  │     │
  │     ▼
  └─→ ch3 (architecture: solves RQ1)
        │
        ▼
       ch4 (eval: solves RQ2)
        │
        ├─→ ch5 (impl detail of ch3/ch4)
        ├─→ ch6 (impl detail of RQ3, UX)
        └─→ ch7 (synthesis)
```

可獨立改 ch5/6/7 不影響 ch1-4。ch4 數字若改要連動更新 ch1 1.3 主要貢獻 + ch7 7.1 findings。

## 寫作慣例

- **語體**：繁體中文 + 英文技術名詞（不翻譯 ArLSTM / pianoplayer / fingering 等）
- **table**：用 markdown table，pandoc 會自動轉合適格式
- **方程式**：LaTeX inline `$...$` 與 block `$$...$$`，pandoc 直通
- **檔案路徑**：用 inline code backtick 包起來 `like_this.py`
- **commit hash**：7 字元短 hash + 描述，如 `commit f7ebf8a`

## 已知 TODO

- ch2.3.3 At Your Fingertips 完整 citation 待確認
- ch6 sheet music 元件目前是 placeholder，Stage D 完成後章節需更新
- ch7 7.4.1 未來工作的 hardware mode 完成後可補實驗數據

## 校對 checklist (defense 前)

- [ ] 每章 abstract / lead paragraph 是否獨立可讀
- [ ] 章節間 cross-reference 是否正確（「如第 4 章 4.5 節」）
- [ ] 數字一致性：ch1 1.3、ch4 4.4.3、ch7 7.1 都引用 corpus n=183 的 ArLSTM 0.792
- [ ] BibTeX entry 是否所有 footnote 都有對應
- [ ] 是否有 placeholder 文字（如「TODO」、「待補」）漏改
- [ ] 中文字句通順（請非作者讀一遍找 typo）
