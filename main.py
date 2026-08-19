import json
import os
import feedparser
import requests
from google import genai

# 1. 讀取環境變數
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
RSS_URL = os.getenv("RSS_URL", "https://openai.com/news/rss.xml")

if not GEMINI_API_KEY or not DISCORD_WEBHOOK_URL:
    print("缺少 GEMINI_API_KEY 或 DISCORD_WEBHOOK_URL 環境變數")
    exit(1)

# 2. 解析 RSS
feed = feedparser.parse(RSS_URL)
client = genai.Client(api_key=GEMINI_API_KEY)

# 僅取最新的 5 則新聞進行分析
for entry in feed.entries[:5]:
    title = entry.title
    link = entry.link
    summary = getattr(entry, "summary", "")

    prompt = f"""
你是一位嚴格的 AI 前沿技術分析師。請分析以下新聞：
標題：{title}
內文摘要：{summary}

判斷這是否屬於「知名科技巨頭發布的底層 AI 技術突破、新模型架構或重要技術產品」。
【嚴格規則】
- 必須剔除：商業融資、企業併購、高層人事變動、法律訴訟、一般商業合作。
- 必須保留：新模型發表、新架構突破、開源權重發布、技術論文、核心 API 重大更新。

請務必僅以 JSON 格式回應：
{{
  "is_important": true 或 false,
  "title_zh": "繁體中文精確標題",
  "tech_summary": "用 2-3 點說明技術核心重點",
  "impact": "一句話說明技術影響力"
}}
"""

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )
        text = response.text.strip()

        # 清除 Markdown codeblock 標籤
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]

        data = json.loads(text.strip())

        # 3. 若為重要技術突破，推送到 Discord
        if data.get("is_important"):
            discord_payload = {
                "embeds": [
                    {
                        "title": f"🚀 {data.get('title_zh')}",
                        "url": link,
                        "color": 3447003,
                        "fields": [
                            {
                                "name": "💡 核心技術摘要",
                                "value": data.get("tech_summary"),
                            },
                            {
                                "name": "⚡ 技術影響力",
                                "value": data.get("impact"),
                            },
                        ],
                        "footer": {
                            "text": "AI 新聞 GitHub Actions 自動過濾系統"
                        },
                    }
                ]
            }
            requests.post(DISCORD_WEBHOOK_URL, json=discord_payload)
            print(f"✅ 已推播重要技術新聞：{title}")
        else:
            print(f"⏭️ 已過濾非關鍵新聞：{title}")

    except Exception as e:
        print(f"❌ 處理新聞時發生錯誤 ({title}): {e}")
