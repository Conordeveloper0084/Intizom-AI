from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from bot.models.score_log import ScoreLog
from bot.models.plan import Plan, PlanStatus
from bot.models.user import User
from datetime import date


async def add_score_log(session: AsyncSession, user: User, plan: Plan, score_change: int, reason: str):
    log = ScoreLog(
        user_id=user.id,
        plan_id=plan.id,
        score_change=score_change,
        reason=reason
    )
    session.add(log)
    user.total_score += score_change
    await session.commit()


async def process_plan_result(session: AsyncSession, user: User, plan: Plan, is_done: bool) -> int:
    if plan.status != PlanStatus.pending:
        return 0  # Ikki marta bosilmasin

    if is_done:
        score_change = plan.score_value
        reason = f"✅ '{plan.title}' bajarildi"
        plan.status = PlanStatus.done
    else:
        score_change = -3
        reason = f"❌ '{plan.title}' bajarilmadi"
        plan.status = PlanStatus.failed

    await session.commit()
    await add_score_log(session, user, plan, score_change, reason)
    return score_change


async def get_today_score(session: AsyncSession, user: User) -> int:
    result = await session.execute(
        select(func.sum(ScoreLog.score_change)).where(
            and_(
                ScoreLog.user_id == user.id,
                func.date(ScoreLog.created_at) == date.today()
            )
        )
    )
    return result.scalar() or 0