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

        system_prompt = """Sen professional reja tahlilchi va tarjimonsiz.

ASOSIY VAZIFA: Foydalanuvchi nima demoqchi bo'lsa - aniq tushunib, o'zbek tilida reja chiqarish.

QOIDALAR:
1. title FAQAT O'ZBEK TILIDA lotin harflarida
2. Har bir so'zni diqqat bilan tahlil qil
3. Sonlar va miqdorlar muhim — ularni saqla
4. Faqat JSON formatda javob ber"""

        user_prompt = f"""HOZIRGI VAQT VA SANA:
Tashkent vaqti: {current_time}
Bugungi sana: {current_date}
Ertaga: {tomorrow_date}

FOYDALANUVCHI MATNI:
"{text}"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

TAHLIL QOIDALARI:

1. SONLAR VA MIQDORLAR:
   Agar son aytilgan bo'lsa — title ga qo'sh!
   
   MISOLLAR:
   ✅ "10 ta turnik" → "Turnikda 10 ta tortish"
   ✅ "5 km yugurish" → "5 km yugurish"
   ✅ "3 sahifa kitob" → "3 sahifa kitob o'qish"
   ✅ "20 minutlik meditatsiya" → "20 daqiqa meditatsiya"
   ❌ "turnik" → "Turnik mashqi" (son yo'q bo'lsa umumiy)

2. VAQT HISOBLASH:
   Aniq soat:
   - "17:00 da" → "17:00"
   - "soat 9 da" → "09:00"
   - "14:30 da" → "14:30"
   
   Nisbiy vaqt (hozirgi vaqt: {current_time}):
   - "10 minutdan keyin" → "{(now + timedelta(minutes=10)).strftime("%H:%M")}"
   - "yarim soatdan so'ng" → "{(now + timedelta(minutes=30)).strftime("%H:%M")}"
   - "1 soatdan keyin" → "{(now + timedelta(hours=1)).strftime("%H:%M")}"
   - "2 soatdan so'ng" → "{(now + timedelta(hours=2)).strftime("%H:%M")}"
   
   Vaqt yo'q:
   - "kechqurun" → null
   - "ertadan" → null

3. BUGUN vs ERTAGA:
   - "ertaga", "sabah", "tomorrow" → for_tomorrow: true
   - Boshqa holatlarda → for_tomorrow: false

4. MAVZU ANIQLASH:
   SPORT va MASHQ:
   - "turnik", "турник", "pull-up" → "Turnikda tortish"
   - "yugurish", "koşmak", "running" → "Yugurish"
   - "sport", "mashq" → "Sport mashg'uloti"
   - "fitnes", "gym" → "Fitnes mashg'uloti"
   
   O'QUV:
   - "dars", "dars tayyorlash" → "Darsga tayyorgarlik"
   - "AI fanidan", "matematikadan" → "[Fan nomi] darsi"
   - "imtihon", "exam" → "Imtihonga tayyorgarlik"
   
   KUNDALIK ISH:
   - "uyg'onish", "turish" → "Uyg'onish"
   - "nonushta", "breakfast" → "Nonushta"
   - "uxlash", "sleep" → "Uxlash"

5. TARJIMA (agar boshqa tilda bo'lsa):
   Turkcha → O'zbekcha:
   - "kalkacağım" → "Uyg'onish"
   - "spor yapacağım" → "Sport qilish"
   - "kitap okuyacağım" → "Kitob o'qish"
   
   Ruscha → O'zbekcha:
   - "проснуться" → "Uyg'onish"
   - "заниматься спортом" → "Sport qilish"
   - "читать книгу" → "Kitob o'qish"
   
   Inglizcha → O'zbekcha:
   - "wake up" → "Uyg'onish"
   - "workout" → "Sport mashg'uloti"
   - "read a book" → "Kitob o'qish"

6. SCORE BERISH:
   - Oddiy (suv ichish, yurish): 3
   - O'rtacha (kitob, sport, dars): 5
   - Qiyin (proyekt, katta ish): 8
   - Juda qiyin (erta turish, sovuq dush): 6

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

JAVOB FORMATI (faqat JSON):
{{
  "plans": [
    {{
      "title": "O'ZBEK TILIDA aniq sarlavha (miqdor bilan agar bor bo'lsa)",
      "description": null,
      "scheduled_time": "HH:MM yoki null",
      "score_value": 5,
      "for_tomorrow": false
    }}
  ]
}}

ESLATMA: 
- title doim o'zbek tilida lotin harflarida
- Sonlar va miqdorlar saqlansin
- Aniq va tushunarli bo'lsin
- Agar bir nechta reja bo'lsa — hammasini ajrat

FAQAT JSON QAYTAR, BOSHQA HECH NARSA YOZMA!"""

        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.05,  # Pastroq — aniqroq javob
        )

        content = response.choices[0].message.content.strip()
        logger.info(f"✅ GPT: {content[:300]}")

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
        
        # Kirill harflar → O'zbek
        for plan in plans:
            title = plan.get("title", "")
            # Kirill tekshirish
            if any(ord(c) >= 0x0400 and ord(c) <= 0x04FF for c in title):
                logger.warning(f"⚠️ Kirill topildi: '{title}' - tarjima qilamiz")
                tr_resp = await client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": "Sen tarjimon. FAQAT o'zbek tilida lotin harflarida javob ber."},
                        {"role": "user", "content": f"Bu matnni o'zbek tiliga (lotin harflarida) tarjima qil. Faqat tarjimani yoz, boshqa hech narsa: '{title}'"}
                    ],
                    temperature=0.05,
                )
                uzbek_title = tr_resp.choices[0].message.content.strip()
                # Kirill qaytgan bo'lsa — fallback
                if any(ord(c) >= 0x0400 and ord(c) <= 0x04FF for c in uzbek_title):
                    uzbek_title = "Reja"
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