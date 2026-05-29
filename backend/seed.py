import argparse
import random
from datetime import datetime, timedelta, UTC

from .config import PASSING_SCORE
from .database import Base, SessionLocal, engine
from .models import AnswerOption, Question, Test, TestAttempt, TestAttemptAnswer, User, UserTest
from .security import get_password_hash


ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin"
DEFAULT_EMPLOYEE_PASSWORD = "test1234"
SEED_EMAIL_PREFIX = "seed.employee"
SEED_EMAIL_DOMAIN = "example.com"
SEED_TEST_PREFIX = "Seed Test"

DEPARTMENTS = ("Operations", "Safety", "HR", "Kitchen", "Logistics")
TEST_TITLES = (
    "Seed Test: Safety Basics",
    "Seed Test: Fire Safety",
    "Seed Test: Customer Service",
    "Seed Test: Food Storage",
    "Seed Test: Workplace Rules",
    "Seed Test: Equipment Use",
)


def _get_or_create_admin(db) -> User:
    admin = db.query(User).filter(User.username == ADMIN_USERNAME).first()
    if admin:
        return admin

    admin = User(
        full_name="Administrator",
        username=ADMIN_USERNAME,
        password_hash=get_password_hash(ADMIN_PASSWORD),
        role="admin",
        department=None,
    )
    db.add(admin)
    db.flush()
    return admin


def _seed_email(index: int) -> str:
    return f"{SEED_EMAIL_PREFIX}{index:03d}@{SEED_EMAIL_DOMAIN}"


def _create_seed_users(db, count: int, password: str) -> list[User]:
    users: list[User] = []
    password_hash = get_password_hash(password)
    for index in range(1, count + 1):
        email = _seed_email(index)
        user = db.query(User).filter(User.username == email).first()
        if not user:
            user = User(
                full_name=f"Seed Employee {index:03d}",
                username=email,
                password_hash=password_hash,
                role="employee",
                department=DEPARTMENTS[(index - 1) % len(DEPARTMENTS)],
            )
            db.add(user)
            db.flush()
        users.append(user)
    return users


def _create_seed_tests(db, admin: User, tests_count: int, questions_per_test: int) -> list[Test]:
    tests: list[Test] = []
    for test_index in range(1, tests_count + 1):
        title = TEST_TITLES[(test_index - 1) % len(TEST_TITLES)]
        if test_index > len(TEST_TITLES):
            title = f"{SEED_TEST_PREFIX}: Extra {test_index}"

        test = db.query(Test).filter(Test.title == title).first()
        if not test:
            test = Test(
                title=title,
                description="Generated demo test data.",
                created_by=admin.id,
            )
            db.add(test)
            db.flush()

        while len(test.questions) < questions_per_test:
            question_number = len(test.questions) + 1
            question = Question(
                test_id=test.id,
                text=f"Question {question_number} for {title}",
            )
            db.add(question)
            db.flush()

            is_multi_answer = question_number % 3 == 0
            options = (
                ("Correct option A", True),
                ("Correct option B", is_multi_answer),
                ("Distractor option C", False),
                ("Distractor option D", False),
            )
            for text, is_correct in options:
                db.add(AnswerOption(question_id=question.id, text=text, is_correct=is_correct))
            db.flush()
            db.refresh(test)

        tests.append(test)
    return tests


def _ensure_assignments(db, users: list[User], tests: list[Test]) -> int:
    created = 0
    for user in users:
        for test in tests:
            exists = (
                db.query(UserTest)
                .filter(UserTest.user_id == user.id, UserTest.test_id == test.id)
                .first()
            )
            if not exists:
                db.add(UserTest(user_id=user.id, test_id=test.id))
                created += 1
    return created


def _select_answer_ids(question: Question, should_be_correct: bool, rng: random.Random) -> list[int]:
    correct_ids = [option.id for option in question.answer_options if option.is_correct]
    wrong_ids = [option.id for option in question.answer_options if not option.is_correct]
    if should_be_correct:
        return correct_ids
    if wrong_ids and rng.random() < 0.5:
        return [wrong_ids[0]]
    if correct_ids and wrong_ids:
        return [*correct_ids, wrong_ids[0]]
    return []


def _create_attempts(db, users: list[User], tests: list[Test], rng: random.Random) -> int:
    created = 0
    now = datetime.now(UTC).replace(tzinfo=None)
    for user_index, user in enumerate(users):
        for test_index, test in enumerate(tests):
            exists = (
                db.query(TestAttempt)
                .filter(TestAttempt.user_id == user.id, TestAttempt.test_id == test.id)
                .first()
            )
            if exists:
                continue

            questions = list(test.questions)
            if not questions:
                continue

            correct_count = 0
            selected_by_question: list[tuple[Question, list[int]]] = []
            for question_index, question in enumerate(questions):
                should_be_correct = (user_index + test_index + question_index) % 4 != 0
                selected_ids = _select_answer_ids(question, should_be_correct, rng)
                correct_ids = {option.id for option in question.answer_options if option.is_correct}
                if set(selected_ids) == correct_ids:
                    correct_count += 1
                selected_by_question.append((question, selected_ids))

            score = round((correct_count / len(questions)) * 100, 2)
            finished_at = now - timedelta(days=(user_index % 30), hours=test_index)
            attempt = TestAttempt(
                user_id=user.id,
                test_id=test.id,
                started_at=finished_at - timedelta(minutes=12),
                finished_at=finished_at,
                score_percent=score,
                passed=score >= PASSING_SCORE,
            )
            db.add(attempt)
            db.flush()

            for question, selected_ids in selected_by_question:
                for option_id in selected_ids:
                    db.add(
                        TestAttemptAnswer(
                            attempt_id=attempt.id,
                            question_id=question.id,
                            answer_option_id=option_id,
                        )
                    )
            created += 1
    return created


def _reset_seed_data(db) -> None:
    seed_users = db.query(User).filter(User.username.like(f"{SEED_EMAIL_PREFIX}%@{SEED_EMAIL_DOMAIN}")).all()
    seed_tests = db.query(Test).filter(Test.title.like(f"{SEED_TEST_PREFIX}%")).all()
    seed_user_ids = [user.id for user in seed_users]
    seed_test_ids = [test.id for test in seed_tests]

    attempt_query = db.query(TestAttempt)
    if seed_user_ids and seed_test_ids:
        attempt_query = attempt_query.filter(
            (TestAttempt.user_id.in_(seed_user_ids)) | (TestAttempt.test_id.in_(seed_test_ids))
        )
    elif seed_user_ids:
        attempt_query = attempt_query.filter(TestAttempt.user_id.in_(seed_user_ids))
    elif seed_test_ids:
        attempt_query = attempt_query.filter(TestAttempt.test_id.in_(seed_test_ids))
    else:
        return

    attempt_ids = [attempt.id for attempt in attempt_query.all()]
    if attempt_ids:
        db.query(TestAttemptAnswer).filter(TestAttemptAnswer.attempt_id.in_(attempt_ids)).delete(
            synchronize_session=False
        )
        db.query(TestAttempt).filter(TestAttempt.id.in_(attempt_ids)).delete(synchronize_session=False)

    if seed_user_ids:
        db.query(UserTest).filter(UserTest.user_id.in_(seed_user_ids)).delete(synchronize_session=False)

    if seed_test_ids:
        db.query(UserTest).filter(UserTest.test_id.in_(seed_test_ids)).delete(synchronize_session=False)
        question_ids = [question.id for question in db.query(Question).filter(Question.test_id.in_(seed_test_ids)).all()]
        if question_ids:
            db.query(AnswerOption).filter(AnswerOption.question_id.in_(question_ids)).delete(synchronize_session=False)
            db.query(Question).filter(Question.id.in_(question_ids)).delete(synchronize_session=False)
        db.query(Test).filter(Test.id.in_(seed_test_ids)).delete(synchronize_session=False)

    if seed_user_ids:
        db.query(User).filter(User.id.in_(seed_user_ids)).delete(synchronize_session=False)

    db.commit()


def seed_database(
    employees: int,
    tests: int,
    questions_per_test: int,
    password: str,
    reset_seed: bool,
    random_seed: int,
) -> dict[str, int]:
    if employees < 1:
        raise ValueError("employees must be at least 1")
    if tests < 1:
        raise ValueError("tests must be at least 1")
    if questions_per_test < 1:
        raise ValueError("questions-per-test must be at least 1")
    if len(password) < 4:
        raise ValueError("password must contain at least 4 characters")

    Base.metadata.create_all(bind=engine)
    rng = random.Random(random_seed)

    with SessionLocal() as db:
        if reset_seed:
            _reset_seed_data(db)

        admin = _get_or_create_admin(db)
        users = _create_seed_users(db, employees, password)
        seed_tests = _create_seed_tests(db, admin, tests, questions_per_test)
        assignments_created = _ensure_assignments(db, users, seed_tests)
        attempts_created = _create_attempts(db, users, seed_tests, rng)
        db.commit()

        return {
            "employees": len(users),
            "tests": len(seed_tests),
            "assignments_created": assignments_created,
            "attempts_created": attempts_created,
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the application database with demo data.")
    parser.add_argument("--employees", type=int, default=50, help="Number of demo employees to create.")
    parser.add_argument("--tests", type=int, default=5, help="Number of demo tests to create.")
    parser.add_argument("--questions-per-test", type=int, default=6, help="Number of questions in each demo test.")
    parser.add_argument("--password", default=DEFAULT_EMPLOYEE_PASSWORD, help="Password for demo employee accounts.")
    parser.add_argument("--reset-seed", action="store_true", help="Delete previous seed data before creating new data.")
    parser.add_argument("--random-seed", type=int, default=42, help="Random seed for deterministic generated attempts.")
    args = parser.parse_args()

    result = seed_database(
        employees=args.employees,
        tests=args.tests,
        questions_per_test=args.questions_per_test,
        password=args.password,
        reset_seed=args.reset_seed,
        random_seed=args.random_seed,
    )

    print("Seed data is ready.")
    print(f"Employees available: {result['employees']}")
    print(f"Tests available: {result['tests']}")
    print(f"Assignments created this run: {result['assignments_created']}")
    print(f"Attempts created this run: {result['attempts_created']}")
    print(f"Demo employee login: {_seed_email(1)}")
    print(f"Demo employee password: {args.password}")


if __name__ == "__main__":
    main()
