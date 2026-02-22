import json
import os
import tempfile
import logging
from datetime import datetime, timedelta
from openai import AsyncOpenAI
from bot.config import OPENAI_API_KEY

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
        now = datetime.now()
        current_time = now.strftime("%H:%M")

        logger.info(f"📝 GPT ga yuborilmoqda: '{text}'")

        system_prompt = """Sen tarjima va reja yordamchisisiz.

QOIDALAR:
1. Matn QAYSI TILDA bo'lmasin (o'zbek, turk, qozoq, rus, ingliz) - sen DOIM o'zbek tilida javob berasan
2. Agar matn o'zbek tilida emas bo'lsa - MA'NOSINI tushunib o'zbek tilida reja yoz
3. JSON ichidagi "title" va "description" FAQAT O'ZBEK TILIDA bo'lishi SHART
4. Faqat JSON qaytar, boshqa hech narsa yozma"""

        user_prompt = f"""Hozirgi vaqt: {current_time}

Quyidagi matndan kunlik rejalarni topib, O'ZBEK TILIDA JSON qaytar.

MUHIM: 
- Matn turk, qozoq, rus yoki boshqa tilda bo'lsa ham - title FAQAT O'ZBEK TILIDA
- Masalan: "уйқудан турамын" → title: "Uyg'onish" yoki "Erta turish"
- Masalan: "spor yapacağım" → title: "Sport qilish"
- Masalan: "read a book" → title: "Kitob o'qish"

Vaqt hisoblash:
- Aniq vaqt: "9 da" → "09:00"
- "10 minutdan keyin" → "{(now + timedelta(minutes=10)).strftime("%H:%M")}"
- "30 minutdan so'ng" → "{(now + timedelta(minutes=30)).strftime("%H:%M")}"
- Vaqt yo'q → null

JSON format:
{{
  "plans": [
    {{
      "title": "O'ZBEK TILIDA sarlavha (masalan: Erta turish, Sport qilish, Kitob o'qish)",
      "description": null,
      "scheduled_time": "HH:MM yoki null",
      "score_value": 5
    }}
  ]
}}

Matn: "{text}"

ESLATMA: Title mutlaqo o'zbek tilida bo'lishi kerak!"""

        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.1,
        )

        content = response.choices[0].message.content.strip()
        logger.info(f"✅ GPT javobi: '{content[:300]}'")

        # JSON tozalash
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
        
        # Har bir plan title'ini tekshirish - agar kirill harflarda bo'lsa qayta so'rash
        for plan in plans:
            title = plan.get("title", "")
            # Agar kirill harflari bor bo'lsa - bu o'zbek emas
            if any(ord(c) >= 0x0400 and ord(c) <= 0x04FF for c in title):
                logger.warning(f"⚠️ Title kirill harflarida: '{title}' - qayta tahlil qilamiz")
                # GPT ga yana bir marta so'raymiz - faqat tarjima uchun
                translate_response = await client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": "Sen tarjimonsan. Faqat o'zbek tilida javob ber."},
                        {"role": "user", "content": f"Bu matnni o'zbek tiliga tarjima qil (faqat tarjimani yoz, boshqa hech narsa): '{title}'"}
                    ],
                    temperature=0.1,
                )
                uzbek_title = translate_response.choices[0].message.content.strip()
                plan["title"] = uzbek_title
                logger.info(f"✅ Tarjima: '{title}' → '{uzbek_title}'")

        logger.info(f"✅ Final rejalar: {plans}")
        return plans

    except json.JSONDecodeError as e:
        logger.error(f"❌ JSON parse xatosi: {e}")
        return []
    except Exception as e:
        logger.error(f"❌ GPT xatosi: {type(e).__name__}: {str(e)}")
        raise e


async def extract_time_only(text: str) -> str | None:
    """
    Matndan FAQAT vaqtni chiqaradi.
    Userga vaqt so'raganda ishlatiladi.
    """
    try:
        now = datetime.now()
        current_time = now.strftime("%H:%M")

        logger.info(f"🕐 Vaqt tahlili: '{text}'")

        prompt = f"""Hozirgi vaqt: {current_time}

Foydalanuvchi vaqt aytdi. Faqat vaqtni HH:MM formatda chiqar.

MISOLLAR:
"soat 15 da" → 15:00
"soat 10:43" → 10:43
"15:00" → 15:00
"10 da" → 10:00
"30 minutdan keyin" → {(now + timedelta(minutes=30)).strftime("%H:%M")}
"1 soatdan so'ng" → {(now + timedelta(hours=1)).strftime("%H:%M")}
"yarim soatdan keyin" → {(now + timedelta(minutes=30)).strftime("%H:%M")}

FAQAT HH:MM formatda javob ber (masalan: 15:00), boshqa hech narsa yozma.

Matn: "{text}"
"""

        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Sen vaqt aniqlash assistantisan. Faqat HH:MM formatda javob ber."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
        )

        result = response.choices[0].message.content.strip()
        logger.info(f"✅ Vaqt natija: '{result}'")

        # HH:MM formatni tekshirish
        if ":" in result and len(result) == 5:
            return result
        
        return None

    except Exception as e:
        logger.error(f"❌ Vaqt tahlil xatosi: {e}")
        return None