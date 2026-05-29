from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from .. import schemas
from ..database import get_db
from ..deps import require_admin
from ..models import Test, User, UserTest

router = APIRouter(prefix="/api/admin/tests", tags=["admin-assignments"])


@router.post("/{test_id}/assign")
def assign_test(
    test_id: int,
    payload: schemas.AssignmentRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    test = db.query(Test).filter(Test.id == test_id).first()
    if not test:
        raise HTTPException(status_code=404, detail="Test not found")

    users = db.query(User).filter(User.id.in_(payload.user_ids)).all()
    if len(users) != len(payload.user_ids):
        raise HTTPException(status_code=400, detail="Some users not found")

    for user_id in payload.user_ids:
        exists = (
            db.query(UserTest)
            .filter(UserTest.user_id == user_id, UserTest.test_id == test_id)
            .first()
        )
        if not exists:
            db.add(UserTest(user_id=user_id, test_id=test_id))
    db.commit()
    return {"detail": "Assignments saved"}


@router.get("/{test_id}/assignees")
def list_assignees(test_id: int, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    test = db.query(Test).filter(Test.id == test_id).first()
    if not test:
        raise HTTPException(status_code=404, detail="Test not found")
    assignments = (
        db.query(UserTest)
        .filter(UserTest.test_id == test_id)
        .join(User, User.id == UserTest.user_id)
        .with_entities(UserTest.user_id, User.full_name, User.username, User.department)
        .all()
    )
    return [
        {
            "user_id": a.user_id,
            "full_name": a.full_name,
            "username": a.username,
            "department": a.department,
        }
        for a in assignments
    ]
