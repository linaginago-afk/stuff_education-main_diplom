from collections import defaultdict
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy import func
from sqlalchemy.orm import Session
from .. import schemas
from ..config import PASSING_SCORE
from ..database import get_db
from ..deps import require_admin
from ..models import AnswerOption, Question, Test, TestAttempt, TestAttemptAnswer, User

router = APIRouter(prefix="/api/admin", tags=["admin-reports"])


def _parse_user_ids(user_id: int | None, user_ids: list[str] | None) -> list[int]:
    selected_ids: list[int] = []
    if user_id:
        selected_ids.append(user_id)
    for raw_value in user_ids or []:
        for value in raw_value.split(","):
            value = value.strip()
            if value:
                try:
                    selected_ids.append(int(value))
                except ValueError as exc:
                    raise HTTPException(status_code=400, detail="Некорректный идентификатор сотрудника") from exc
    return sorted(set(selected_ids))


def _collect_results(db: Session, test_id: int | None, user_ids: list[int] | None):
    query = (
        db.query(
            TestAttempt.user_id,
            User.full_name,
            TestAttempt.test_id,
            Test.title,
            func.max(TestAttempt.score_percent).label("best_score"),
            func.count(TestAttempt.id).label("attempts"),
        )
        .join(User, User.id == TestAttempt.user_id)
        .join(Test, Test.id == TestAttempt.test_id)
        .group_by(TestAttempt.user_id, TestAttempt.test_id, User.full_name, Test.title)
    )
    if test_id:
        query = query.filter(TestAttempt.test_id == test_id)
    if user_ids:
        query = query.filter(TestAttempt.user_id.in_(user_ids))
    return query.all()


@router.get("/results", response_model=list[schemas.ResultSummary])
def results(
    test_id: int | None = None,
    user_id: int | None = None,
    user_ids: list[str] | None = Query(default=None),
    status: str | None = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    rows = _collect_results(db, test_id, _parse_user_ids(user_id, user_ids))
    data = [
        schemas.ResultSummary(
            user_id=row.user_id,
            user_name=row.full_name,
            test_id=row.test_id,
            test_title=row.title,
            best_score=row.best_score,
            attempts=row.attempts,
            passed=row.best_score >= PASSING_SCORE,
        )
        for row in rows
    ]
    if status == "passed":
        data = [d for d in data if d.passed]
    elif status == "failed":
        data = [d for d in data if not d.passed]
    return data[offset : offset + limit]


@router.get("/results/export")
def export_results(
    test_id: int | None = None,
    user_id: int | None = None,
    user_ids: list[str] | None = Query(default=None),
    status: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    rows = _collect_results(db, test_id, _parse_user_ids(user_id, user_ids))
    data = []
    for row in rows:
        passed = row.best_score >= PASSING_SCORE
        if status == "passed" and not passed:
            continue
        if status == "failed" and passed:
            continue
        data.append(
            {
                "user_id": row.user_id,
                "user_name": row.full_name,
                "test_id": row.test_id,
                "test_title": row.title,
                "best_score": row.best_score,
                "attempts": row.attempts,
                "passed": "passed" if passed else "failed",
            }
        )
    import csv
    import io

    buffer = io.StringIO()
    writer = csv.DictWriter(
        buffer, fieldnames=["user_id", "user_name", "test_id", "test_title", "best_score", "attempts", "passed"]
    )
    writer.writeheader()
    writer.writerows(data)
    # Excel дружелюбный UTF-8: кодируем как utf-8-sig (с BOM)
    csv_bytes = buffer.getvalue().encode("utf-8-sig")
    return PlainTextResponse(
        content=csv_bytes,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=results.csv"},
    )


@router.get("/users/{user_id}/attempts", response_model=list[schemas.DetailedAttempt])
def user_attempts(user_id: int, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    attempts = (
        db.query(TestAttempt)
        .filter(TestAttempt.user_id == user_id)
        .order_by(TestAttempt.finished_at.desc())
        .all()
    )
    return attempts


@router.get("/users/{user_id}/attempts/details", response_model=list[schemas.AttemptDetailed])
def user_attempt_details(
    user_id: int,
    test_id: int | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    attempts_query = db.query(TestAttempt).filter(TestAttempt.user_id == user_id)
    if test_id:
        attempts_query = attempts_query.filter(TestAttempt.test_id == test_id)
    attempts = attempts_query.order_by(TestAttempt.finished_at.desc()).all()
    if not attempts:
        return []

    attempt_ids = [a.id for a in attempts]
    test_ids = {a.test_id for a in attempts}
    questions = (
        db.query(Question)
        .filter(Question.test_id.in_(test_ids))
        .order_by(Question.id)
        .all()
    )
    questions_by_test: dict[int, list[Question]] = defaultdict(list)
    for question in questions:
        questions_by_test[question.test_id].append(question)

    answers_rows = (
        db.query(
            TestAttemptAnswer.attempt_id,
            TestAttemptAnswer.question_id,
            TestAttemptAnswer.answer_option_id,
            AnswerOption.text.label("selected_option_text"),
        )
        .join(AnswerOption, AnswerOption.id == TestAttemptAnswer.answer_option_id)
        .filter(TestAttemptAnswer.attempt_id.in_(attempt_ids))
        .all()
    )

    question_ids = {question.id for question in questions}
    correct_options = (
        db.query(AnswerOption)
        .filter(AnswerOption.question_id.in_(question_ids), AnswerOption.is_correct == True)
        .order_by(AnswerOption.id)
        .all()
    )
    correct_map: dict[int, dict[int, str]] = defaultdict(dict)
    for option in correct_options:
        correct_map[option.question_id][option.id] = option.text

    selected_map: dict[tuple[int, int], dict[int, str]] = defaultdict(dict)
    for row in answers_rows:
        selected_map[(row.attempt_id, row.question_id)][row.answer_option_id] = row.selected_option_text

    answers_by_attempt: dict[int, list[schemas.AttemptAnswerDetailed]] = {a.id: [] for a in attempts}
    for attempt in attempts:
        for question in questions_by_test.get(attempt.test_id, []):
            selected_options = selected_map.get((attempt.id, question.id), {})
            correct_options_for_question = correct_map.get(question.id, {})
            selected_ids = sorted(selected_options)
            correct_ids = sorted(correct_options_for_question)
            answers_by_attempt[attempt.id].append(
                schemas.AttemptAnswerDetailed(
                    question_id=question.id,
                    question_text=question.text,
                    selected_option_ids=selected_ids,
                    selected_option_text=", ".join(selected_options[option_id] for option_id in selected_ids)
                    or "ответ не выбран",
                    correct_option_ids=correct_ids,
                    correct_option_text=", ".join(
                        correct_options_for_question[option_id] for option_id in correct_ids
                    ),
                    is_correct=set(selected_ids) == set(correct_ids),
                )
            )

    result: list[schemas.AttemptDetailed] = []
    for attempt in attempts:
        result.append(
            schemas.AttemptDetailed(
                id=attempt.id,
                test_id=attempt.test_id,
                score_percent=attempt.score_percent,
                passed=attempt.passed,
                finished_at=attempt.finished_at,
                answers=answers_by_attempt.get(attempt.id, []),
            )
        )
    return result
