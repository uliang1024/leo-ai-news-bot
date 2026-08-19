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

# 2. 定義硬核 AI 技術新聞 RSS 來源清單
RSS_SOURCES = [
    {"name": "OpenAI Blog", "url": "https://openai.com/news/rss.xml"},
    {"name": "Google Research", "url": "https://blog.research.google/feeds/posts/default"},
    {"name": "Hugging Face Blog", "url": "https://huggingface.co/blog/feed.xml"},
    {"name": "arXiv AI 論文", "url": "https://rss.arxiv.org/rss/cs.AI"},
]

client = genai.Client(api_key=GEMINI_API_KEY)

# 3. 輪詢各大 RSS 來源
for source in RSS_SOURCES:
    print(f"\n📡 正在抓取來源: {source['name']}...")
    try:
        feed = feedparser.parse(source["url"])
        entries = feed.entries[:3]  # 每個來源只挑最新的 3 則進行 AI 語意分析

        for entry in entries:
            title = entry.title
            link = entry.link
            summary = getattr(entry, "summary", getattr(entry, "description", ""))

            prompt = f"""
你是一位嚴格的 AI 前沿技術分析師。請分析以下新聞：
來源平台：{source['name']}
標題：{title}
內容摘要：{summary[:500]}

請判斷這是否屬於「知名科技巨頭或頂級機構發布的底層 AI 技術突破、新模型架構、開源權重、核心演算法或重要論文/API」。
【過濾規則】
- 必須剔除（is_important = false）：純商業廣告、融資、高層變動、政策法規、一般公關與未附帶技術細節的宣傳稿。
- 必須保留（is_important = true）：全新大模型/小模型發布、模型架構突破、開源模型權重、核心 API 或開發者工具重大升級。

請務必僅以 JSON 格式回應（禁止包含任何 Markdown 標記）：
{{
  "is_important": true 或 false,
  "title_zh": "繁體中文精確標題",
  "tech_summary": "用 2-3 點說明技術核心重點與亮點",
  "impact": "一句話說明對 AI 領域或開發者的技術影響"
}}
"""

            try:
                response = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=prompt,
                )
                text = response.text.strip()

                # 清除 Markdown codeblock 標籤
                if "```" in text:
                    text = text.split("```")[1]
                    if text.startswith("json"):
                        text = text[4:]

                data = json.loads(text.strip())

                if data.get("is_important"):
                    discord_payload = {
                        "embeds": [
                            {
                                "title": f"🚀 [{source['name']}] {data.get('title_zh')}",
                                "url": link,
                                "color": 3447003,
                                "fields": [
                                    {
                                        "name": "💡 核心技術摘要",
                                        "value": data.get("tech_summary", "無"),
                                    },
                                    {
                                        "name": "⚡ 技術影響力",
                                        "value": data.get("impact", "無"),
                                    },
                                ],
                                "footer": {
                                    "text": "AI 新聞 GitHub Actions 自動過濾系統"
                                },
                            }
                        ]
                    }
                    res = requests.post(DISCORD_WEBHOOK_URL, json=discord_payload)
                    if res.status_code == 204:
                        print(f"✅ 已成功推播至 Discord：{title}")
                    else:
                        print(f"⚠️ Discord 推播失敗 ({res.status_code}): {res.text}")
                else:
                    print(f"⏭️ 已過濾非關鍵新聞：{title}")

            except Exception as e:
                print(f"⚠️ 分析新聞失敗 ({title}): {e}")

    except Exception as e:
        print(f"❌ 抓取 RSS 失敗 ({source['name']}): {e}")
