"""Tick 8 study engine: queue assembly, subcategory init, tick recording, SRS, progress."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.flashcard import Flashcard
from app.models.sub_category import SubCategory
from app.models.tick_result import TickResult, TickResultKind
from app.models.user import User
from app.models.user_card_progress import UserCardProgress, ProgressStatus
from app.models.user_study_settings import UserStudySettings
from app.services import interval_provider
from app.services.srs_engine import (
    get_initial_srs_interval_and_ease,
    performance_score_from_tick_values,
    process_srs_review,
    tick_value,
)

# Defaults when no UserStudySettings row exists (create on first get)
DEFAULT_DAILY_NEW_CARD_LIMIT = 20
DEFAULT_SESSION_CAP = 50
DEFAULT_PHASE_REGRESSION_ENABLED = True


def _today_utc() -> date:
    return datetime.now(timezone.utc).date()


def _get_or_create_study_settings(db: Session, user_id: int) -> UserStudySettings:
    row = db.scalar(select(UserStudySettings).where(UserStudySettings.user_id == user_id))
    if row is not None:
        return row
    row = UserStudySettings(
        user_id=user_id,
        daily_new_card_limit=DEFAULT_DAILY_NEW_CARD_LIMIT,
        session_cap=DEFAULT_SESSION_CAP,
        phase_regression_enabled=DEFAULT_PHASE_REGRESSION_ENABLED,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_user_study_settings(db: Session, user_id: int) -> dict[str, Any]:
    s = _get_or_create_study_settings(db, user_id)
    return {
        "daily_new_card_limit": s.daily_new_card_limit,
        "session_cap": s.session_cap,
        "phase_regression_enabled": s.phase_regression_enabled,
        "skip_off_schedule_progress_prompt": getattr(
            s, "skip_off_schedule_progress_prompt", False
        ),
    }


def update_user_study_settings(
    db: Session,
    user_id: int,
    *,
    daily_new_card_limit: int | None = None,
    session_cap: int | None = None,
    phase_regression_enabled: bool | None = None,
    skip_off_schedule_progress_prompt: bool | None = None,
) -> dict[str, Any]:
    s = _get_or_create_study_settings(db, user_id)
    if daily_new_card_limit is not None:
        s.daily_new_card_limit = max(5, min(50, daily_new_card_limit))
    if session_cap is not None:
        s.session_cap = max(20, min(200, session_cap))
    if phase_regression_enabled is not None:
        s.phase_regression_enabled = phase_regression_enabled
    if skip_off_schedule_progress_prompt is not None:
        s.skip_off_schedule_progress_prompt = skip_off_schedule_progress_prompt
    db.commit()
    db.refresh(s)
    return get_user_study_settings(db, user_id)


def ensure_subcategory_initialized(db: Session, sub_category_id: int, user_id: int) -> None:
    """Create pending UserCardProgress for every flashcard in subcategory that has none."""
    sub = db.get(SubCategory, sub_category_id)
    if sub is None or sub.owner_id != user_id or sub.deleted_at is not None:
        return
    cards = db.scalars(
        select(Flashcard).where(
            Flashcard.sub_category_id == sub_category_id,
            Flashcard.deleted_at.is_(None),
        )
    ).all()
    now = datetime.now(timezone.utc)
    for card in cards:
        existing = db.scalar(
            select(UserCardProgress).where(
                UserCardProgress.user_id == user_id,
                UserCardProgress.flashcard_id == card.id,
            )
        )
        if existing is None:
            db.add(
                UserCardProgress(
                    user_id=user_id,
                    flashcard_id=card.id,
                    status=ProgressStatus.PENDING,
                    queued_at=now,
                )
            )
        elif existing.deleted_at is not None:
            # Restored card: progress was soft-deleted; restore it to avoid duplicate key
            existing.deleted_at = None
    db.commit()


def _ensure_all_subcategories_initialized(db: Session, user_id: int) -> None:
    """Create pending progress for any card in user's subcategories that lacks progress."""
    sub_ids = db.scalars(
        select(SubCategory.id).where(
            SubCategory.owner_id == user_id,
            SubCategory.deleted_at.is_(None),
        )
    ).all()
    for sub_id in sub_ids:
        ensure_subcategory_initialized(db, sub_id, user_id)


def _promote_pending_to_phase1_today(db: Session, user_id: int, limit: int) -> None:
    """Promote up to `limit` pending cards (by queued_at) to phase1 with next_review_date=today."""
    if limit <= 0:
        return
    today = _today_utc()
    # How many did we already introduce today?
    already = db.scalar(
        select(func.count(UserCardProgress.id)).where(
            UserCardProgress.user_id == user_id,
            UserCardProgress.deleted_at.is_(None),
            func.date(UserCardProgress.introduced_at) == today,
        )
    ) or 0
    to_promote = max(0, limit - already)
    if to_promote == 0:
        return
    now = datetime.now(timezone.utc)
    pending = db.scalars(
        select(UserCardProgress)
        .where(
            UserCardProgress.user_id == user_id,
            UserCardProgress.status == ProgressStatus.PENDING,
            UserCardProgress.deleted_at.is_(None),
        )
        .order_by(UserCardProgress.queued_at.asc())
        .limit(to_promote)
    ).all()
    for p in pending:
        p.status = ProgressStatus.PHASE1
        p.next_review_date = today
        p.schedule_anchor_date = today
        p.introduced_at = now
    db.commit()


def _apply_rule2_reschedule_simple(db: Session, user_id: int, today: date) -> None:
    """Rule 2: If two or more consecutive scheduled review dates passed without review,
    set schedule_anchor_date to last_reviewed_date and recalc next_review_date.
    """
    intervals = interval_provider.get_tick8_intervals()
    progress_list = db.scalars(
        select(UserCardProgress).where(
            UserCardProgress.user_id == user_id,
            UserCardProgress.deleted_at.is_(None),
            UserCardProgress.status.in_([ProgressStatus.PHASE1, ProgressStatus.PHASE2]),
            UserCardProgress.next_review_date.isnot(None),
            UserCardProgress.schedule_anchor_date.isnot(None),
        )
    ).all()

    for p in progress_list:
        anchor = p.schedule_anchor_date
        if anchor is None or p.last_reviewed_at is None:
            continue
        last_reviewed_date = p.last_reviewed_at.date()
        if p.status == ProgressStatus.PHASE1:
            n = p.phase1_ticks_done + 1  # next tick to do (1..8)
            if n > 8:
                continue
            # Scheduled date for tick n = anchor + intervals[0]+..+intervals[n-1]
            days_to_next = sum(intervals[i] for i in range(n))
            scheduled_next = anchor + timedelta(days=days_to_next)
            if n >= 2:
                days_to_prev = sum(intervals[i] for i in range(n - 1))
                scheduled_prev = anchor + timedelta(days=days_to_prev)
            else:
                scheduled_prev = anchor
            if today <= scheduled_prev:
                continue
            if today <= scheduled_next:
                continue
            if p.phase1_ticks_done < n - 2:
                continue
            # Actually: "last_reviewed_tick <= N-2" means we did tick (n-2) or earlier, so we missed (n-1) and n
            if p.phase1_ticks_done >= n - 1:
                continue
            # Revert anchor to last review date and recalc
            p.schedule_anchor_date = last_reviewed_date
            # Next tick to do is (phase1_ticks_done + 1) = n; from last_reviewed_date add interval for tick n
            days_next = intervals[n - 1]  # interval after tick (n-1) to get to tick n
            p.next_review_date = last_reviewed_date + timedelta(days=days_next)
        else:
            # Phase 2
            phase2_start = p.phase1_completed_at.date() if p.phase1_completed_at else anchor
            n = p.phase2_ticks_done + 1  # 1..8
            if n > 8:
                continue
            days_to_next = sum(intervals[i] for i in range(n))
            scheduled_next = phase2_start + timedelta(days=days_to_next)
            if n >= 2:
                days_to_prev = sum(intervals[i] for i in range(n - 1))
                scheduled_prev = phase2_start + timedelta(days=days_to_prev)
            else:
                scheduled_prev = phase2_start
            if today <= scheduled_prev or today <= scheduled_next:
                continue
            if p.phase2_ticks_done >= n - 1:
                continue
            p.schedule_anchor_date = last_reviewed_date
            phase2_start = last_reviewed_date
            days_next = intervals[n - 1]
            p.next_review_date = phase2_start + timedelta(days=days_next)
    db.commit()


def _build_due_list(
    db: Session, user_id: int, today: date
) -> list[tuple[UserCardProgress, int, bool, int, int]]:
    """Returns list of (progress, phase, is_overdue, catch_up_index, catch_up_total)."""
    settings = _get_or_create_study_settings(db, user_id)
    # Priority 1: Phase 2 overdue; 2: Phase 1 overdue; 3: Phase 2 due; 4: Phase 1 due; 5: SRS; 6: new
    due: list[tuple[UserCardProgress, int, bool, int, int]] = []
    # Phase 2 overdue
    q = (
        select(UserCardProgress)
        .where(
            UserCardProgress.user_id == user_id,
            UserCardProgress.deleted_at.is_(None),
            UserCardProgress.status == ProgressStatus.PHASE2,
            UserCardProgress.next_review_date < today,
        )
        .order_by(UserCardProgress.next_review_date.asc())
    )
    for p in db.scalars(q).all():
        due.append((p, 2, True, 0, 0))
    # Phase 1 overdue
    q = (
        select(UserCardProgress)
        .where(
            UserCardProgress.user_id == user_id,
            UserCardProgress.deleted_at.is_(None),
            UserCardProgress.status == ProgressStatus.PHASE1,
            UserCardProgress.next_review_date < today,
        )
        .order_by(UserCardProgress.next_review_date.asc())
    )
    for p in db.scalars(q).all():
        due.append((p, 1, True, 0, 0))
    # Phase 2 due today
    q = (
        select(UserCardProgress)
        .where(
            UserCardProgress.user_id == user_id,
            UserCardProgress.deleted_at.is_(None),
            UserCardProgress.status == ProgressStatus.PHASE2,
            UserCardProgress.next_review_date == today,
        )
        .order_by(UserCardProgress.next_review_date.asc())
    )
    for p in db.scalars(q).all():
        due.append((p, 2, False, 0, 0))
    # Phase 1 due today
    q = (
        select(UserCardProgress)
        .where(
            UserCardProgress.user_id == user_id,
            UserCardProgress.deleted_at.is_(None),
            UserCardProgress.status == ProgressStatus.PHASE1,
            UserCardProgress.next_review_date == today,
        )
        .order_by(UserCardProgress.next_review_date.asc())
    )
    for p in db.scalars(q).all():
        due.append((p, 1, False, 0, 0))
    # SRS due
    q = (
        select(UserCardProgress)
        .where(
            UserCardProgress.user_id == user_id,
            UserCardProgress.deleted_at.is_(None),
            UserCardProgress.status.in_([ProgressStatus.GRADUATED, ProgressStatus.LONG_TERM_MASTERED]),
            UserCardProgress.next_review_date.isnot(None),
            UserCardProgress.next_review_date <= today,
        )
        .order_by(UserCardProgress.next_review_date.asc())
    )
    for p in db.scalars(q).all():
        due.append((p, 0, False, 0, 0))  # phase 0 = SRS
    # New: pending promoted this run are already phase1 with next_review_date=today; we already have them in "Phase 1 due today". So "new introductions" = those we just promoted. So we don't add pending again here — they get promoted first, then appear in Phase 1 due today. So we only need to add pending that we're about to promote. So the flow is: promote up to limit; then build due list. So "new introductions" in the queue are the phase1 cards with next_review_date=today that have current_tick=0 (Tick 1). They're already in the "Phase 1 due today" and "Phase 2 due" etc. So we're good. But we need to add PENDING that get promoted: _promote_pending_to_phase1_today runs first, so after that we have more phase1 with next_review_date=today. So the due list is built after promotion. Good.
    return due


def get_todays_queue_with_cards(db: Session, user_id: int) -> list[dict[str, Any]]:
    """Today's queue with card content (front, back) and marks for each item. For home page display."""
    data = get_todays_queue(db, user_id)
    out: list[dict[str, Any]] = []
    for item in data["queue"]:
        progress_id = item["progress_id"]
        flashcard_id = item["flashcard_id"]
        p = db.get(UserCardProgress, progress_id)
        if p is None or p.user_id != user_id or p.deleted_at is not None:
            continue
        card = db.get(Flashcard, flashcard_id)
        if card is None or card.owner_id != user_id or card.deleted_at is not None:
            continue
        results = db.scalars(
            select(TickResult)
            .where(
                TickResult.user_card_progress_id == progress_id,
                TickResult.is_regression_tick.is_(False),
            )
            .order_by(TickResult.tick_number.asc())
        ).all()
        # Map 'difficult' to 'forgot' for frontend
        marks = [
            "forgot" if r.result.value == "difficult" else r.result.value
            for r in results
        ][:16]
        out.append({
            "progress_id": progress_id,
            "flashcard_id": flashcard_id,
            "front": {
                "type": card.front_type.value,
                "text": card.front_text,
                "image_url": card.front_image_url,
            },
            "back": {
                "type": card.back_type.value,
                "text": card.back_text,
                "image_url": card.back_image_url,
            },
            "marks": marks,
        })
    return out


def get_todays_queue(db: Session, user_id: int) -> dict[str, Any]:
    """Assemble today's study queue: run init, promote, Rule 2, then priority-ordered list with cap."""
    today = _today_utc()
    _ensure_all_subcategories_initialized(db, user_id)
    settings = _get_or_create_study_settings(db, user_id)
    _promote_pending_to_phase1_today(db, user_id, settings.daily_new_card_limit)
    _apply_rule2_reschedule_simple(db, user_id, today)

    due = _build_due_list(db, user_id, today)
    # Expand catch-up: when same progress appears multiple times (multiple overdue ticks), we need to add one entry per tick. For now we add each progress once; the story says "when Rule 2 results in multiple ticks due, the card is shown once per tick" and "re-inserted at end of queue for Tick N+1". So we need to count how many ticks are due for each progress when it's Phase 1/2 and overdue. So we should expand (progress, phase, is_overdue, 0, 0) into multiple entries when that card has multiple ticks due (catch-up). Rule 2 recalc sets next_review_date to the first due tick; after user does that tick we'll recalc and the card might appear again the same day. So actually we build the queue as a list of "slots": each slot is one appearance of a card. For catch-up we need to know "this card has 3 ticks due" and add 3 slots. So we need to compute for each progress how many ticks are due today. That's more complex (we'd need to simulate or store "ticks due count"). Per story: "When Rule 2 results in multiple ticks of the same card being due simultaneously... The card is shown once per tick... After recording a response for Tick N, the card is re-inserted at the end of the current session queue for Tick N+1." So we don't pre-expand: we show one slot per card, and when they answer we re-insert for the next tick. So the queue is list of (progress_id, ...) and when we record a tick we might add the same progress again at the end if there's another tick due. So we need to know "how many ticks are due for this progress today". If we don't pre-expand, the frontend would need to know "review 2 of 3" — so we need to return for each queue item: progress_id, flashcard_id, phase, tick_in_phase, is_overdue, catch_up_total (how many ticks due for this card today). So we need to compute catch_up_total for each progress. That requires: for this progress, from schedule_anchor_date and phase, compute all tick dates up to today and count how many are <= today. Let me simplify: return one entry per (progress, tick_due_index). So we expand here: for each progress in due list, compute number of ticks due today; emit that many entries (each with catch_up_n, catch_up_total). So _build_due_list should return list of (progress, phase, is_overdue, catch_up_n, catch_up_total). And we need to compute catch_up_total. For Phase 1: from schedule_anchor_date, tick 1 due at anchor+0, tick 2 at anchor+interval[1], ... Count how many are <= today. For Phase 2: from phase1_completed_at, same. So I'll add a helper that returns (num_ticks_due_today, list of tick numbers) for a progress. Then we expand the due list.
    # Simplified: don't expand catch-up in queue; return one entry per progress. When recording tick we'll recalc and the API can return "next card" which might be the same progress again. So the frontend "session" holds the queue and when user answers we pop and optionally push same card again (backend tells "same card, next tick" in the response). So we return queue items with progress_id, flashcard_id, phase, tick_in_phase, is_overdue, catch_up_total. catch_up_total we can compute: for this progress how many ticks have next_review_date <= today? Actually after Rule 2 we set next_review_date to the first due tick. So we only have one next_review_date. To know "3 ticks due" we need to recalc from anchor. So in _build_due_list we could compute for each progress the number of ticks due and then duplicate entries. Let me compute catch_up_total in a helper and expand.
    expanded: list[dict[str, Any]] = []
    for (p, phase, is_overdue, _, _) in due:
        if phase == 0:
            # SRS: one appearance
            expanded.append({
                "progress_id": p.id,
                "flashcard_id": p.flashcard_id,
                "phase": 0,
                "tick_in_phase": 0,
                "is_overdue": is_overdue,
                "catch_up_n": 0,
                "catch_up_total": 0,
            })
            continue
        n_due = _count_ticks_due_today_fixed(p, today)
        for i in range(n_due):
            expanded.append({
                "progress_id": p.id,
                "flashcard_id": p.flashcard_id,
                "phase": phase,
                "tick_in_phase": (p.phase1_ticks_done if phase == 1 else p.phase2_ticks_done) + i + 1,
                "is_overdue": is_overdue,
                "catch_up_n": i + 1,
                "catch_up_total": n_due,
            })
    # Apply session cap: take first session_cap
    cap = settings.session_cap
    total_due = len(expanded)
    queue = expanded[:cap]
    return {
        "queue": queue,
        "total_due": total_due,
        "capped": total_due > cap,
        "session_cap": cap,
        "daily_new_card_limit": settings.daily_new_card_limit,
    }


def get_upcoming_reviews(db: Session, user_id: int, days: int = 5) -> list[dict[str, Any]]:
    """Next `days` calendar days with count of cards due each day."""
    today = _today_utc()
    out: list[dict[str, Any]] = []
    for d in range(1, days + 1):
        day = today + timedelta(days=d)
        count = db.scalar(
            select(func.count(UserCardProgress.id)).where(
                UserCardProgress.user_id == user_id,
                UserCardProgress.deleted_at.is_(None),
                UserCardProgress.next_review_date.isnot(None),
                UserCardProgress.next_review_date == day,
            )
        ) or 0
        out.append({"date": day.isoformat(), "count": count})
    return out


def get_study_card(
    db: Session,
    user_id: int,
    progress_id: int,
    tick_in_phase: int = 1,
    catch_up_n: int = 0,
    catch_up_total: int = 0,
) -> dict[str, Any]:
    """Return the card side to display for a queue item. Phase 1 -> front, Phase 2 -> back."""
    p = db.get(UserCardProgress, progress_id)
    if p is None or p.user_id != user_id or p.deleted_at is not None:
        raise ValueError("Progress not found")
    card = db.get(Flashcard, p.flashcard_id)
    if card is None or card.owner_id != user_id or card.deleted_at is not None:
        raise ValueError("Flashcard not found")
    if p.status == ProgressStatus.PHASE1:
        side = "front"
        content = {
            "type": card.front_type.value,
            "text": card.front_text,
            "image_url": card.front_image_url,
        }
        content_hidden = {
            "type": card.back_type.value,
            "text": card.back_text,
            "image_url": card.back_image_url,
        }
        hidden_side_label = "Back"
    elif p.status == ProgressStatus.PHASE2:
        side = "back"
        content = {
            "type": card.back_type.value,
            "text": card.back_text,
            "image_url": card.back_image_url,
        }
        content_hidden = {
            "type": card.front_type.value,
            "text": card.front_text,
            "image_url": card.front_image_url,
        }
        hidden_side_label = "Front"
    else:
        side = "front"
        content = {
            "type": card.front_type.value,
            "text": card.front_text,
            "image_url": card.front_image_url,
        }
        content_hidden = {
            "type": card.back_type.value,
            "text": card.back_text,
            "image_url": card.back_image_url,
        }
        hidden_side_label = "Back"
    return {
        "progress_id": p.id,
        "flashcard_id": p.flashcard_id,
        "phase": 1 if p.status == ProgressStatus.PHASE1 else (2 if p.status == ProgressStatus.PHASE2 else 0),
        "tick_in_phase": tick_in_phase,
        "catch_up_n": catch_up_n,
        "catch_up_total": catch_up_total,
        "side": side,
        "content": content,
        "content_hidden": content_hidden,
        "hidden_side_label": hidden_side_label,
    }


def get_earliest_next_review_date(db: Session, user_id: int) -> date | None:
    """Earliest next_review_date in the future, or None if none."""
    today = _today_utc()
    r = db.scalar(
        select(func.min(UserCardProgress.next_review_date)).where(
            UserCardProgress.user_id == user_id,
            UserCardProgress.deleted_at.is_(None),
            UserCardProgress.next_review_date > today,
        )
    )
    return r


def get_subcategory_progress(db: Session, sub_category_id: int, user_id: int) -> dict[str, Any]:
    """Counts by status and optional phase breakdown for subcategory."""
    ensure_subcategory_initialized(db, sub_category_id, user_id)
    sub = db.get(SubCategory, sub_category_id)
    if sub is None or sub.owner_id != user_id or sub.deleted_at is not None:
        return {
            "total": 0,
            "pending": 0,
            "phase1": 0,
            "phase2": 0,
            "graduated": 0,
            "long_term_mastered": 0,
            "mastery_percent": 0.0,
        }
    # All flashcards in subcategory
    card_ids = db.scalars(
        select(Flashcard.id).where(
            Flashcard.sub_category_id == sub_category_id,
            Flashcard.deleted_at.is_(None),
        )
    ).all()
    total = len(card_ids)
    if total == 0:
        return {
            "total": 0,
            "pending": 0,
            "phase1": 0,
            "phase2": 0,
            "graduated": 0,
            "long_term_mastered": 0,
            "mastery_percent": 0.0,
        }
    # Count progress by status for this user and these cards
    q = (
        select(UserCardProgress.status, func.count(UserCardProgress.id))
        .where(
            UserCardProgress.user_id == user_id,
            UserCardProgress.flashcard_id.in_(card_ids),
            UserCardProgress.deleted_at.is_(None),
        )
        .group_by(UserCardProgress.status)
    )
    counts = {str(s): c for s, c in db.execute(q).all()}
    pending = counts.get(ProgressStatus.PENDING.value, 0)
    phase1 = counts.get(ProgressStatus.PHASE1.value, 0)
    phase2 = counts.get(ProgressStatus.PHASE2.value, 0)
    graduated = counts.get(ProgressStatus.GRADUATED.value, 0)
    long_term_mastered = counts.get(ProgressStatus.LONG_TERM_MASTERED.value, 0)
    mastered = graduated + long_term_mastered
    mastery_percent = round(100.0 * mastered / total, 1) if total else 0.0
    return {
        "total": total,
        "pending": pending,
        "phase1": phase1,
        "phase2": phase2,
        "graduated": graduated,
        "long_term_mastered": long_term_mastered,
        "mastery_percent": mastery_percent,
    }


def get_subcategory_card_progress(
    db: Session, sub_category_id: int, user_id: int
) -> list[dict[str, Any]]:
    """Per-card tick results for the 16-dot progress strip: list of { flashcard_id, marks }."""
    ensure_subcategory_initialized(db, sub_category_id, user_id)
    card_ids = db.scalars(
        select(Flashcard.id).where(
            Flashcard.sub_category_id == sub_category_id,
            Flashcard.deleted_at.is_(None),
        )
    ).all()
    if not card_ids:
        return []
    out: list[dict[str, Any]] = []
    for cid in card_ids:
        progress = db.scalar(
            select(UserCardProgress).where(
                UserCardProgress.user_id == user_id,
                UserCardProgress.flashcard_id == cid,
                UserCardProgress.deleted_at.is_(None),
            )
        )
        marks: list[str] = []
        progress_id = 0
        if progress is not None:
            progress_id = progress.id
            results = db.scalars(
                select(TickResult)
                .where(
                    TickResult.user_card_progress_id == progress.id,
                    TickResult.is_regression_tick.is_(False),
                )
                .order_by(TickResult.tick_number.asc())
            ).all()
            # Map 'difficult' to 'forgot' so frontend only sees remembered/forgot
            marks = [
                "forgot" if r.result.value == "difficult" else r.result.value
                for r in results
            ][:16]
        out.append({"flashcard_id": cid, "progress_id": progress_id, "marks": marks})
    return out


def record_tick(
    db: Session,
    user_id: int,
    user_card_progress_id: int,
    result: TickResultKind,
    response_time_ms: int | None = None,
) -> dict[str, Any]:
    """Record one tick response; update progress and optionally phase/SRS. Returns updated progress + next state."""
    p = db.get(UserCardProgress, user_card_progress_id)
    if p is None or p.user_id != user_id or p.deleted_at is not None:
        raise ValueError("Progress not found")
    today = _today_utc()
    now = datetime.now(timezone.utc)
    phase = 1 if p.status == ProgressStatus.PHASE1 else (2 if p.status == ProgressStatus.PHASE2 else 0)
    tick_number = p.current_tick + 1

    if p.status == ProgressStatus.PHASE1:
        phase1_tick = p.phase1_ticks_done + 1
        # Create TickResult
        tr = TickResult(
            user_card_progress_id=p.id,
            tick_number=tick_number,
            phase=1,
            reviewed_on_date=today,
            result=result,
            response_time_ms=response_time_ms,
            is_regression_tick=False,
        )
        db.add(tr)
        p.current_tick = tick_number
        p.phase1_ticks_done = phase1_tick
        p.last_reviewed_at = now
        p.schedule_anchor_date = today
        if result == TickResultKind.FORGOT:
            p.consecutive_forgot_count += 1
        else:
            p.consecutive_forgot_count = 0
        if phase1_tick < 8:
            interval_days = interval_provider.get_tick8_interval_days(phase1_tick + 1)
            p.next_review_date = today + timedelta(days=interval_days)
        else:
            # Tick 8 complete -> Phase 2
            p.status = ProgressStatus.PHASE2
            p.phase1_completed_at = now
            p.phase2_ticks_done = 0
            p.next_review_date = today  # Tick 9 = same day
        db.commit()
        db.refresh(p)
        return _record_tick_response_fix(db, p, phase, phase1_tick, result)
    elif p.status == ProgressStatus.PHASE2:
        phase2_tick = p.phase2_ticks_done + 1
        tr = TickResult(
            user_card_progress_id=p.id,
            tick_number=tick_number,
            phase=2,
            reviewed_on_date=today,
            result=result,
            response_time_ms=response_time_ms,
            is_regression_tick=False,
        )
        db.add(tr)
        p.current_tick = tick_number
        p.phase2_ticks_done = phase2_tick
        p.last_reviewed_at = now
        p.schedule_anchor_date = today
        if result == TickResultKind.FORGOT:
            p.consecutive_forgot_count += 1
        else:
            p.consecutive_forgot_count = 0
        if phase2_tick < 8:
            interval_days = interval_provider.get_tick8_interval_days(phase2_tick + 1)
            p.next_review_date = today + timedelta(days=interval_days)
        else:
            # Graduate
            p.status = ProgressStatus.GRADUATED
            p.graduated_at = now
            db.flush()
            results_16 = db.scalars(
                select(TickResult).where(
                    TickResult.user_card_progress_id == p.id,
                    TickResult.is_regression_tick.is_(False),
                ).order_by(TickResult.tick_number.asc())
            ).all()
            values = [tick_value(r.result) for r in results_16][:16]
            if len(values) == 16:
                score = performance_score_from_tick_values(values)
                interval_days, ease = get_initial_srs_interval_and_ease(score)
                p.srs_interval_days = interval_days
                p.srs_ease_factor = ease
                p.srs_repetitions = 0
                p.next_review_date = today + timedelta(days=interval_days)
            else:
                p.next_review_date = today + timedelta(days=1)
                p.srs_ease_factor = 1.3
                p.srs_interval_days = 1
        db.commit()
        db.refresh(p)
        return _record_tick_response_fix(db, p, 2, phase2_tick, result)
    else:
        # SRS review (graduated or long_term_mastered)
        interval = p.srs_interval_days or 1
        ease = p.srs_ease_factor or 1.3
        rep = p.srs_repetitions or 0
        next_interval, new_ease, new_rep = process_srs_review(result, interval, ease, rep)
        p.srs_interval_days = next_interval
        p.srs_ease_factor = new_ease
        p.srs_repetitions = new_rep
        p.next_review_date = today + timedelta(days=next_interval)
        p.last_reviewed_at = now
        if next_interval >= 90:
            p.status = ProgressStatus.LONG_TERM_MASTERED
        db.commit()
        db.refresh(p)
        return _record_tick_response_fix(db, p, 0, 0, result)


def _record_tick_response_fix(db: Session, p: UserCardProgress, phase: int, tick_in_phase: int, result: TickResultKind) -> dict[str, Any]:
    out: dict[str, Any] = {
        "progress_id": p.id,
        "phase": phase,
        "tick_in_phase": tick_in_phase,
        "result": result.value,
        "phase2_regression_offer": False,
    }
    if p.status == ProgressStatus.PHASE2 and p.consecutive_forgot_count == 3:
        s = _get_or_create_study_settings(db, p.user_id)
        if s.phase_regression_enabled and not p.phase2_regression_dismissed:
            out["phase2_regression_offer"] = True
    return out


def _count_ticks_due_today_fixed(p: UserCardProgress, today: date) -> int:
    """Number of ticks due on or before today for this progress (Phase 1 or 2)."""
    intervals = interval_provider.get_tick8_intervals()
    if p.status == ProgressStatus.PHASE1:
        anchor = p.schedule_anchor_date or today
        count = 0
        cum = 0
        for j in range(1, 9):
            if j <= p.phase1_ticks_done:
                cum += intervals[j - 1]
                continue
            cum += intervals[j - 1]
            if anchor + timedelta(days=cum) <= today:
                count += 1
            else:
                break
        return count if count >= 1 else 1
    if p.status == ProgressStatus.PHASE2:
        anchor = (p.phase1_completed_at.date() if p.phase1_completed_at else p.schedule_anchor_date) or today
        count = 0
        cum = 0
        for j in range(1, 9):
            if j <= p.phase2_ticks_done:
                cum += intervals[j - 1]
                continue
            cum += intervals[j - 1]
            if anchor + timedelta(days=cum) <= today:
                count += 1
            else:
                break
        return count if count >= 1 else 1
    return 1


def set_progress_ticks(
    db: Session,
    user_id: int,
    progress_id: int,
    marks: list[str],
) -> None:
    """Replace tick results for this progress with the given list (max 16). Updates progress state accordingly."""
    p = db.get(UserCardProgress, progress_id)
    if p is None or p.user_id != user_id or p.deleted_at is not None:
        raise ValueError("Progress not found")
    if len(marks) > 16:
        raise ValueError("At most 16 marks allowed")
    today = _today_utc()
    now = datetime.now(timezone.utc)
    # Only accept 'remembered' and 'forgot' (difficult removed from UI)
    kind_map = {
        TickResultKind.REMEMBERED.value: TickResultKind.REMEMBERED,
        TickResultKind.FORGOT.value: TickResultKind.FORGOT,
    }
    parsed: list[TickResultKind] = []
    for m in marks:
        if m not in kind_map:
            raise ValueError(f"Invalid mark: {m}. Use 'remembered' or 'forgot'.")
        parsed.append(kind_map[m])

    # Delete existing non-regression tick results
    existing = db.scalars(
        select(TickResult).where(
            TickResult.user_card_progress_id == progress_id,
            TickResult.is_regression_tick.is_(False),
        )
    ).all()
    for tr in existing:
        db.delete(tr)

    # Insert new tick results
    for i, result in enumerate(parsed):
        phase = 1 if i < 8 else 2
        db.add(
            TickResult(
                user_card_progress_id=progress_id,
                tick_number=i + 1,
                phase=phase,
                reviewed_on_date=today,
                result=result,
                response_time_ms=None,
                is_regression_tick=False,
            )
        )

    n = len(parsed)
    p.current_tick = n
    p.phase1_ticks_done = min(8, n)
    p.phase2_ticks_done = max(0, n - 8)
    p.last_reviewed_at = now
    p.schedule_anchor_date = today
    if p.phase1_ticks_done >= 8:
        p.phase1_completed_at = now
    if n < 8:
        p.status = ProgressStatus.PHASE1
        p.phase1_completed_at = None
        if n == 0:
            p.next_review_date = today
        else:
            interval_days = interval_provider.get_tick8_interval_days(n + 1)
            p.next_review_date = today + timedelta(days=interval_days)
    elif n < 16:
        p.status = ProgressStatus.PHASE2
        if p.phase1_completed_at is None:
            p.phase1_completed_at = now
        interval_days = interval_provider.get_tick8_interval_days(n - 7)
        p.next_review_date = today + timedelta(days=interval_days)
    else:
        p.status = ProgressStatus.GRADUATED
        p.graduated_at = now
        db.flush()
        results_16 = db.scalars(
            select(TickResult).where(
                TickResult.user_card_progress_id == p.id,
                TickResult.is_regression_tick.is_(False),
            ).order_by(TickResult.tick_number.asc())
        ).all()
        values = [tick_value(r.result) for r in results_16][:16]
        if len(values) == 16:
            score = performance_score_from_tick_values(values)
            interval_days, ease = get_initial_srs_interval_and_ease(score)
            p.srs_interval_days = interval_days
            p.srs_ease_factor = ease
            p.srs_repetitions = 0
            p.next_review_date = today + timedelta(days=interval_days)
        else:
            p.next_review_date = today + timedelta(days=1)
    db.commit()
