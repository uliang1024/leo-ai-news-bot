import json
import os
import time
import feedparser
import requests
from google import genai

# 1. 環境變數驗證
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

if not GEMINI_API_KEY or not DISCORD_WEBHOOK_URL:
    print("❌ 錯誤：缺少 GEMINI_API_KEY 或 DISCORD_WEBHOOK_URL")
    exit(1)

# 2. 讀取歷史紀錄 (避免重複發送)
HISTORY_FILE = "history.json"
history = []
if os.path.exists(HISTORY_FILE):
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            history = json.load(f)
    except Exception:
        history = []

# 3. 讀取 RSS 來源清單
with open("sources.json", "r", encoding="utf-8") as f:
    RSS_SOURCES = json.load(f)

# 4. 收集未分析的新文章
candidates = []
for source in RSS_SOURCES:
    print(f"📡 正在抓取來源: {source['name']}...")
    try:
        feed = feedparser.parse(source["url"])
        for entry in feed.entries[:3]:
            link = entry.link
            if link in history:
                print(f"⏭️ 已存在歷史紀錄，自動跳過：{entry.title}")
                continue

            summary = getattr(entry, "summary", getattr(entry, "description", ""))
            candidates.append({
                "source": source["name"],
                "title": entry.title,
                "link": link,
                "summary": summary[:400]
            })
    except Exception as e:
        print(f"❌ 抓取 RSS 失敗 ({source['name']}): {e}")

if not candidates:
    print("\n✨ 沒有發現任何未處理的新文章。")
    exit(0)

print(f"\n🧠 成功收集 {len(candidates)} 篇新文章，打包進行一次性 AI 評估...")

# 5. 一次性打包呼叫 Gemini API (徹底避免 429 錯誤)
client = genai.Client(api_key=GEMINI_API_KEY)

prompt = f"""
你是一位資深全棧工程師兼 AI 應用架構師。請審視以下 {len(candidates)} 篇文章清單：

{json.dumps(candidates, ensure_ascii=False, indent=2)}

【使用者背景與需求】
使用者是前後端工程師（Angular、Web 開發），個人專案開發 AI 派工 Agent，使用 Gemini/Claude Pro。
請判斷哪些文章符合以下條件（is_important = true）：
1. AI 巨頭（OpenAI, Claude, Gemini, DeepSeek）發布新模型、新 API 特性、Codex/Copilot 類開發工具。
2. AI Agent、派工自動化、RAG、LLM 工作流實作或 GitHub 熱門開發者工具突破。
3. Angular 或 Web 前後端關鍵技術的大版本更新/重要特性。
4. 能直接提升軟體開發效率、自動化個人日常/工作流程的特色技術。

【過濾（is_important = false）】
- 純學術/非軟體領域論文（氣象、生醫、臨床）。
- 商業融資、高層人事變動、政策法規、純公關宣傳稿。

請務必僅回傳一個 JSON 陣列（List），格式如下（禁止包含 Markdown 註解）：
[
  {{
    "link": "對應文章的 link",
    "is_important": true 或 false,
    "title_zh": "繁體中文精確標題",
    "tech_summary": "用 2-3 點說明這對開發者或 AI 專案有何實用價值",
    "category": "標籤（如：AI 模型 / Agent 自動化 / 前端技術 / 開發工具）"
  }}
]
"""

try:
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
    )
    text = response.text.strip()

    if "```" in text:
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]

    results = json.loads(text.strip())

    new_history_added = False
    for item in results:
        link = item.get("link")
        
        # 紀錄已評估過，無論是否重要都寫入紀錄
        if link and link not in history:
            history.append(link)
            new_history_added = True

        if item.get("is_important"):
            discord_payload = {
                "embeds": [
                    {
                        "title": f"🚀 [{item.get('category', '技術動態')}] {item.get('title_zh')}",
                        "url": link,
                        "color": 3447003,
                        "fields": [
                            {
                                "name": "💡 核心開發價值",
                                "value": item.get("tech_summary", "無"),
                            },
                            {
                                "name": "🔗 來源連結",
                                "value": f"[點此閱讀原文]({link})",
                            }
                        ],
                        "footer": {
                            "text": "開發者 AI & 技術新聞篩選系統"
                        },
                    }
                ]
            }
            res = requests.post(DISCORD_WEBHOOK_URL, json=discord_payload)
            if res.status_code == 204:
                print(f"✅ 已成功推播：{item.get('title_zh')}")
            else:
                print(f"⚠️ Discord 推播失敗 ({res.status_code}): {res.text}")
            time.sleep(1)

    # 6. 保存歷史紀錄 (保留最新 200 筆)
    if new_history_added:
        history = history[-200:]
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
            print("💾 已更新 history.json 去重紀錄。")

except Exception as e:
    print(f"❌ AI 分析失敗: {e}")
