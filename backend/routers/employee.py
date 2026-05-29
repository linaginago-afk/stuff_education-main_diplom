from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from .. import schemas
from ..config import PASSING_SCORE
from ..database import get_db
from ..deps import require_employee
from ..models import AnswerOption, Question, Test, TestAttempt, TestAttemptAnswer, User, UserTest

router = APIRouter(prefix="/api/employee", tags=["employee"])


def _ensure_assigned(db: Session, user_id: int, test_id: int):
    assignment = (
        db.query(UserTest).filter(UserTest.user_id == user_id, UserTest.test_id == test_id).first()
    )
    if not assignment:
        raise HTTPException(status_code=403, detail="Test not assigned to this user")


@router.get("/tests")
def list_assigned_tests(db: Session = Depends(get_db), user: User = Depends(require_employee)):
    assignments = (
        db.query(UserTest)
        .filter(UserTest.user_id == user.id)
        .join(Test, Test.id == UserTest.test_id)
        .with_entities(UserTest.test_id, Test.title, Test.description, UserTest.assigned_at)
        .all()
    )
    result = []
    for a in assignments:
        attempts = (
            db.query(TestAttempt)
            .filter(TestAttempt.user_id == user.id, TestAttempt.test_id == a.test_id)
            .order_by(TestAttempt.finished_at.desc())
            .all()
        )
        status = "not_started"
        last_score = None
        last_date = None
        if attempts:
            status = "completed"
            last_score = attempts[0].score_percent
            last_date = attempts[0].finished_at
        result.append(
            {
                "test_id": a.test_id,
                "title": a.title,
                "description": a.description,
                "status": status,
                "last_score": last_score,
                "last_attempt_date": last_date,
            }
        )
    return result


@router.get("/tests/{test_id}", response_model=schemas.TestPublic)
def get_test(test_id: int, db: Session = Depends(get_db), user: User = Depends(require_employee)):
    _ensure_assigned(db, user.id, test_id)
    test = db.query(Test).filter(Test.id == test_id).first()
    if not test:
        raise HTTPException(status_code=404, detail="Test not found")
    return test


@router.post("/tests/{test_id}/submit", response_model=schemas.AttemptOut)
def submit_answers(
    test_id: int,
    payload: schemas.SubmitAttemptRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_employee),
):
    _ensure_assigned(db, user.id, test_id)
    test = db.query(Test).filter(Test.id == test_id).first()
    if not test:
        raise HTTPException(status_code=404, detail="Test not found")

    answers_map: dict[int, set[int]] = {}
    for item in payload.answers:
        answers_map.setdefault(item.question_id, set()).update(item.selected_ids())

    questions: list[Question] = test.questions
    if not questions:
        raise HTTPException(status_code=400, detail="Test has no questions")

    correct_count = 0
    for q in questions:
        chosen_option_ids = answers_map.get(q.id, set())
        correct_option_ids = {opt.id for opt in q.answer_options if opt.is_correct}
        if not correct_option_ids:
            continue
        if chosen_option_ids == correct_option_ids:
            correct_count += 1

    score = round((correct_count / len(questions)) * 100, 2)
    passed = score >= PASSING_SCORE

    attempt = TestAttempt(
        user_id=user.id,
        test_id=test_id,
        started_at=datetime.utcnow(),
        finished_at=datetime.utcnow(),
        score_percent=score,
        passed=passed,
    )
    db.add(attempt)
    db.flush()

    for q in questions:
        if q.id not in answers_map:
            continue
        valid_options = (
            db.query(AnswerOption)
            .filter(AnswerOption.id.in_(answers_map[q.id]), AnswerOption.question_id == q.id)
            .all()
        )
        for valid_option in valid_options:
            db.add(
                TestAttemptAnswer(
                    attempt_id=attempt.id,
                    question_id=q.id,
                    answer_option_id=valid_option.id,
                )
            )
    db.commit()
    db.refresh(attempt)
    return attempt


@router.get("/progress", response_model=list[schemas.ProgressItem])
def my_progress(db: Session = Depends(get_db), user: User = Depends(require_employee)):
    assignments = (
        db.query(UserTest)
        .filter(UserTest.user_id == user.id)
        .join(Test, Test.id == UserTest.test_id)
        .with_entities(UserTest.test_id, Test.title)
        .all()
    )
    progress_items: list[schemas.ProgressItem] = []
    for a in assignments:
        attempts = (
            db.query(TestAttempt)
            .filter(TestAttempt.user_id == user.id, TestAttempt.test_id == a.test_id)
            .order_by(TestAttempt.finished_at.desc())
            .all()
        )
        if attempts:
            best_score = max(attempt.score_percent for attempt in attempts)
            last_date = attempts[0].finished_at
        else:
            best_score = 0.0
            last_date = None
        progress_items.append(
            schemas.ProgressItem(
                test_id=a.test_id,
                test_title=a.title,
                best_score=best_score,
                attempts=len(attempts),
                last_attempt_date=last_date,
            )
        )
    return progress_items
