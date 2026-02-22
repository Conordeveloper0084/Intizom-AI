from aiogram import Router, F
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.services.user_service import get_user_by_telegram_id
from bot.services.plan_service import get_plan_by_id, move_plan_to_tomorrow
from bot.services.score_service import process_plan_result
from bot.keyboards.plan_keys import back_to_home_keyboard

router = Router()


@router.callback_query(F.data.startswith("done_"))
async def done_handler(callback: CallbackQuery, session: AsyncSession):
    plan_id = int(callback.data.split("_")[1])

    user = await get_user_by_telegram_id(session, callback.from_user.id)
    plan = await get_plan_by_id(session, plan_id)

    if not plan:
        await callback.answer("Reja topilmadi!", show_alert=True)
        return

    score = await process_plan_result(session, user, plan, is_done=True)

    await callback.message.edit_text(
        f"🎉 <b>Barakallo!</b>\n\n"
        f"✅ <b>{plan.title}</b> bajarildi!\n\n"
        f"⭐ +{score} ball qo'shildi\n"
        f"🏆 Umumiy ball: <b>{user.total_score}</b>\n"
        f"🔥 Streak: <b>{user.streak} kun</b>",
        parse_mode="HTML",
        reply_markup=back_to_home_keyboard()
    )
    await callback.answer("✅ +ball qo'shildi!")


@router.callback_query(F.data.startswith("failed_"))
async def failed_handler(callback: CallbackQuery, session: AsyncSession):
    plan_id = int(callback.data.split("_")[1])

    user = await get_user_by_telegram_id(session, callback.from_user.id)
    plan = await get_plan_by_id(session, plan_id)

    if not plan:
        await callback.answer("Reja topilmadi!", show_alert=True)
        return

    score = await process_plan_result(session, user, plan, is_done=False)

    await callback.message.edit_text(
        f"😔 <b>{plan.title}</b> bajarilmadi.\n\n"
        f"❌ {score} ball ayirildi\n"
        f"🏆 Umumiy ball: <b>{user.total_score}</b>\n\n"
        f"💪 Ertaga yana urinib ko'ring!",
        parse_mode="HTML",
        reply_markup=back_to_home_keyboard()
    )
    await callback.answer("Keyingi safar bajarasiz! 💪")


@router.callback_query(F.data.startswith("tomorrow_"))
async def tomorrow_handler(callback: CallbackQuery, session: AsyncSession):
    """Rejani ertaga ko'chirish"""
    plan_id = int(callback.data.split("_")[1])

    plan = await get_plan_by_id(session, plan_id)

    if not plan:
        await callback.answer("Reja topilmadi!", show_alert=True)
        return

    # Keyingi kunga ko'chirish
    new_plan = await move_plan_to_tomorrow(session, plan)

    await callback.message.edit_text(
        f"📅 <b>{plan.title}</b> ertaga ko'chirildi!\n\n"
        f"📌 Ertaga: {new_plan.plan_date.strftime('%d.%m.%Y')}\n"
        f"{f'🕐 {new_plan.scheduled_time}' if new_plan.scheduled_time else '🕐 Vaqtsiz'}\n\n"
        f"Ertaga eslataman! 💪",
        parse_mode="HTML",
        reply_markup=back_to_home_keyboard()
    )
    await callback.answer("Ertaga ko'chirildi! 📅")