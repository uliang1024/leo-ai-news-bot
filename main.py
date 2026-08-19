import json
import os
import feedparser
import requests
from google import genai

# 1. 環境變數驗證
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

if not GEMINI_API_KEY or not DISCORD_WEBHOOK_URL:
    print("❌ 錯誤：缺少 GEMINI_API_KEY 或 DISCORD_WEBHOOK_URL")
    exit(1)

# 2. 直接從 JSON 檔載入來源清單
with open("sources.json", "r", encoding="utf-8") as f:
    RSS_SOURCES = json.load(f)

client = genai.Client(api_key=GEMINI_API_KEY)

# 3. 輪詢與 AI 評估
for source in RSS_SOURCES:
    print(f"\n📡 正在抓取來源: {source['name']}...")
    try:
        feed = feedparser.parse(source["url"])
        entries = feed.entries[:3]  # 每個來源只挑最新的 3 則

        for entry in entries:
            title = entry.title
            link = entry.link
            summary = getattr(entry, "summary", getattr(entry, "description", ""))

            prompt = f"""
你是一位資深全棧工程師兼 AI 應用架構師。請審視以下資訊：
來源平台：{source['name']}
標題：{title}
內文摘要：{summary[:600]}

【使用者背景與興趣】
使用者是一位前後端軟體工程師，目前使用 Angular、做 Web 前後端開發，個人專案在做 AI 派工 Agent，日常使用 Gemini 與 Claude Pro。

【請判斷這是否符合以下條件（符合任一即 is_important = true）】
1. AI 巨頭（OpenAI, Claude, Gemini, DeepSeek）發布新模型、新 API 特性、Codex/Copilot 類程式開發工具。
2. AI Agent、派工自動化、RAG、LLM 工作流實作或 GitHub 熱門開發者工具突破。
3. Angular 或 Web 前後端關鍵技術的大版本更新/重要特性。
4. 能直接提升軟體開發效率、自動化個人日常/工作流程的特色技術。

【嚴格過濾（is_important = false）】
- 純學術/非軟體領域論文（氣象、生醫、臨床）。
- 商業融資、高層人事變動、政策法規、純公關宣傳稿。

請務必僅以 JSON 格式回應（禁止包含任何 Markdown 標記）：
{{
  "is_important": true 或 false,
  "title_zh": "繁體中文精確標題",
  "tech_summary": "用 2-3 點說明這對開發者或 AI 專案有何實用價值",
  "category": "標籤（如：AI 模型 / Agent 自動化 / 前端技術 / 開發工具）"
}}
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

                data = json.loads(text.strip())

                if data.get("is_important"):
                    discord_payload = {
                        "embeds": [
                            {
                                "title": f"🚀 [{data.get('category', '技術動態')}] {data.get('title_zh')}",
                                "url": link,
                                "color": 3447003,
                                "fields": [
                                    {
                                        "name": "💡 核心開發價值",
                                        "value": data.get("tech_summary", "無"),
                                    },
                                    {
                                        "name": "🔗 來源",
                                        "value": f"[{source['name']}]({link})",
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
                        print(f"✅ 已推播開發者精選新聞：{title}")
                    else:
                        print(f"⚠️ Discord 推播失敗 ({res.status_code}): {res.text}")
                else:
                    print(f"⏭️ 已過濾不相關新聞：{title}")

            except Exception as e:
                print(f"⚠️ 分析新聞失敗 ({title}): {e}")

    except Exception as e:
        print(f"❌ 抓取 RSS 失敗 ({source['name']}): {e}")
