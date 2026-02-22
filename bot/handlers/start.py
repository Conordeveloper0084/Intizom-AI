from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart

from sqlalchemy.ext.asyncio import AsyncSession

from bot.services.user_service import get_or_create_user, get_user_by_telegram_id
from bot.keyboards.main_menu import main_menu_keyboard
from bot.keyboards.reply_keys import main_reply_keyboard

router = Router()


@router.message(CommandStart())
async def start_handler(message: Message, session: AsyncSession):
    user = await get_or_create_user(
        session=session,
        telegram_id=message.from_user.id,
        full_name=message.from_user.full_name,
        username=message.from_user.username or ""
    )

    await message.answer(
        "🎯 <b>Intizom AI</b> ga xush kelibsiz!\n\n"
        "Men sizning shaxsiy intizom yordamchingizman.\n\n"
        "📌 <b>Nima qila olaman:</b>\n"
        "• Ovoz yoki matn orqali reja tuzish\n"
        "• Vaqti kelganda eslatish\n"
        "• Bajargan ishlar uchun ball berish\n"
        "• Kunlik hisobot tayyorlash\n\n"
        "💡 <b>Boshlash uchun</b> — bugun nima qilmoqchi ekanligingizni "
        "ovozli xabar yoki matn yuboring!\n\n"
        "<i>Masalan: 'Soat 6 da turaman, 9 da kitob o'qiyman'</i>",
        parse_mode="HTML",
        reply_markup=main_reply_keyboard()
    )


@router.callback_query(F.data == "home")
async def home_handler(callback: CallbackQuery, session: AsyncSession):
    user = await get_user_by_telegram_id(session, callback.from_user.id)

    await callback.message.edit_text(
        f"🏠 <b>Bosh sahifa</b>\n\n"
        f"👤 {user.full_name}\n"
        f"🏆 Ball: <b>{user.total_score}</b>\n"
        f"🔥 Streak: <b>{user.streak} kun</b>",
        parse_mode="HTML",
        reply_markup=main_menu_keyboard()
    )
    await callback.answer()