from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from .. import schemas
from ..database import get_db
from ..deps import require_admin
from ..models import AnswerOption, Question, Test, User

router = APIRouter(prefix="/api/admin/tests", tags=["admin-tests"])


def _ensure_correct_option(options: list[schemas.AnswerOptionCreate]):
    if not any(opt.is_correct for opt in options):
        raise HTTPException(status_code=400, detail="At least one answer must be correct")


@router.get("", response_model=list[schemas.TestOut])
def list_tests(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    return db.query(Test).order_by(Test.id).all()


@router.post("", response_model=schemas.TestOut)
def create_test(payload: schemas.TestCreate, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    new_test = Test(title=payload.title, description=payload.description, created_by=admin.id)
    db.add(new_test)
    db.flush()
    if payload.questions:
        for q in payload.questions:
            _ensure_correct_option(q.answer_options)
            question = Question(test_id=new_test.id, text=q.text)
            db.add(question)
            db.flush()
            for opt in q.answer_options:
                db.add(AnswerOption(question_id=question.id, text=opt.text, is_correct=opt.is_correct))
    db.commit()
    db.refresh(new_test)
    return new_test


@router.get("/{test_id}", response_model=schemas.TestOut)
def get_test(test_id: int, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    test = db.query(Test).filter(Test.id == test_id).first()
    if not test:
        raise HTTPException(status_code=404, detail="Test not found")
    return test


@router.put("/{test_id}", response_model=schemas.TestOut)
def update_test(
    test_id: int, payload: schemas.TestUpdate, db: Session = Depends(get_db), _: User = Depends(require_admin)
):
    test = db.query(Test).filter(Test.id == test_id).first()
    if not test:
        raise HTTPException(status_code=404, detail="Test not found")
    if payload.title is not None:
        test.title = payload.title
    if payload.description is not None:
        test.description = payload.description
    db.commit()
    db.refresh(test)
    return test


@router.delete("/{test_id}")
def delete_test(test_id: int, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    test = db.query(Test).filter(Test.id == test_id).first()
    if not test:
        raise HTTPException(status_code=404, detail="Test not found")
    db.delete(test)
    db.commit()
    return {"detail": "Deleted"}


@router.post("/{test_id}/questions", response_model=schemas.QuestionOut)
def add_question(
    test_id: int,
    payload: schemas.QuestionCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    test = db.query(Test).filter(Test.id == test_id).first()
    if not test:
        raise HTTPException(status_code=404, detail="Test not found")
    _ensure_correct_option(payload.answer_options)
    question = Question(test_id=test_id, text=payload.text)
    db.add(question)
    db.flush()
    for opt in payload.answer_options:
        db.add(AnswerOption(question_id=question.id, text=opt.text, is_correct=opt.is_correct))
    db.commit()
    db.refresh(question)
    return question


@router.put("/{test_id}/questions/{question_id}", response_model=schemas.QuestionOut)
def update_question(
    test_id: int,
    question_id: int,
    payload: schemas.QuestionCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    question = db.query(Question).filter(Question.id == question_id, Question.test_id == test_id).first()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    _ensure_correct_option(payload.answer_options)
    question.text = payload.text
    # replace options
    db.query(AnswerOption).filter(AnswerOption.question_id == question_id).delete()
    db.flush()
    for opt in payload.answer_options:
        db.add(AnswerOption(question_id=question.id, text=opt.text, is_correct=opt.is_correct))
    db.commit()
    db.refresh(question)
    return question


@router.delete("/{test_id}/questions/{question_id}")
def delete_question(
    test_id: int, question_id: int, db: Session = Depends(get_db), _: User = Depends(require_admin)
):
    question = db.query(Question).filter(Question.id == question_id, Question.test_id == test_id).first()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    db.delete(question)
    db.commit()
    return {"detail": "Deleted"}
