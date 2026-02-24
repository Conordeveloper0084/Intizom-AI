import json
import os
import tempfile
import logging
from datetime import datetime, timedelta
from openai import AsyncOpenAI
from bot.config import OPENAI_API_KEY, TIMEZONE

logger = logging.getLogger(__name__)

client = AsyncOpenAI(api_key=OPENAI_API_KEY)


async def transcribe_voice(file_bytes: bytes) -> str:
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
            tmp.write(file_bytes)
            tmp_path = tmp.name

        with open(tmp_path, "rb") as audio_file:
            transcript = await client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
            )

        result = transcript.text.strip()
        logger.info(f"✅ Whisper natija: '{result}'")
        return result

    except Exception as e:
        logger.error(f"❌ Whisper xatosi: {type(e).__name__}: {str(e)}")
        raise e

    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)


async def extract_plans_from_text(text: str) -> list[dict]:
    try:
        # O'zbekiston vaqti
        now = datetime.now(TIMEZONE)
        current_time = now.strftime("%H:%M")
        current_date = now.strftime("%d.%m.%Y")
        
        tomorrow = now + timedelta(days=1)
        tomorrow_date = tomorrow.strftime("%d.%m.%Y")

        logger.info(f"📝 GPT ga yuborilmoqda: '{text}' | Tashkent: {current_time}")

        system_prompt = """Sen reja yordamchisisiz. Faqat o'zbek tilida javob ber."""

        user_prompt = f"""Hozir: {current_time} (Tashkent)
Bugun: {current_date}
Ertaga: {tomorrow_date}

Matndan rejalarni topib O'ZBEK TILIDA JSON qaytar.

VAQT:
- "17:00 da" → "17:00"
- "10 minutdan keyin" → "{(now + timedelta(minutes=10)).strftime("%H:%M")}"
- "yarim soatdan so'ng" → "{(now + timedelta(minutes=30)).strftime("%H:%M")}"
- Vaqt yo'q → null

BUGUN/ERTAGA:
- "ertaga", "sabah" → for_tomorrow: true
- Boshqa → for_tomorrow: false

JSON:
{{
  "plans": [
    {{
      "title": "O'zbek tilida (Erta turish)",
      "description": null,
      "scheduled_time": "HH:MM yoki null",
      "score_value": 5,
      "for_tomorrow": false
    }}
  ]
}}

Matn: "{text}"
"""

        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.1,
        )

        content = response.choices[0].message.content.strip()
        logger.info(f"✅ GPT: {content[:200]}")

        if "```" in content:
            parts = content.split("```")
            if len(parts) >= 2:
                content = parts[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.strip()

        start = content.find("{")
        end = content.rfind("}") + 1
        if start != -1 and end > start:
            content = content[start:end]

        data = json.loads(content)
        plans = data.get("plans", [])
        
        # Kirill → O'zbek
        for plan in plans:
            title = plan.get("title", "")
            if any(ord(c) >= 0x0400 and ord(c) <= 0x04FF for c in title):
                tr_resp = await client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": "Tarjimon. O'zbek tilida yoz."},
                        {"role": "user", "content": f"O'zbekchaga: {title}"}
                    ],
                    temperature=0.1,
                )
                plan["title"] = tr_resp.choices[0].message.content.strip()

        logger.info(f"✅ Final: {plans}")
        return plans

    except Exception as e:
        logger.error(f"❌ GPT xato: {e}")
        return []