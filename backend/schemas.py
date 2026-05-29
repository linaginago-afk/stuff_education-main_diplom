from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    username: Optional[str] = None


class LoginRequest(BaseModel):
    username: str
    password: str


class UserBase(BaseModel):
    full_name: str
    username: str
    role: str
    department: Optional[str] = None


class UserCreate(UserBase):
    password: str = Field(..., min_length=4)


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    password: Optional[str] = Field(None, min_length=4)
    role: Optional[str] = None
    department: Optional[str] = None


class UserOut(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime


class UserImportError(BaseModel):
    row: int
    email: Optional[str] = None
    error: str


class UserImportResult(BaseModel):
    created: int
    skipped: int
    errors: List[UserImportError] = Field(default_factory=list)


class AnswerOptionBase(BaseModel):
    text: str
    is_correct: bool = False


class AnswerOptionCreate(AnswerOptionBase):
    pass


class AnswerOptionOut(AnswerOptionBase):
    model_config = ConfigDict(from_attributes=True)

    id: int


class AnswerOptionPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    text: str


class QuestionBase(BaseModel):
    text: str


class QuestionCreate(QuestionBase):
    answer_options: List[AnswerOptionCreate]


class QuestionOut(QuestionBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    allows_multiple_answers: bool = False
    answer_options: List[AnswerOptionOut]


class QuestionPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    text: str
    allows_multiple_answers: bool = False
    answer_options: List[AnswerOptionPublic]


class TestBase(BaseModel):
    title: str
    description: Optional[str] = None


class TestCreate(TestBase):
    questions: Optional[List[QuestionCreate]] = None


class TestUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None


class TestOut(TestBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_by: int
    created_at: datetime
    questions: List[QuestionOut] = Field(default_factory=list)


class TestPublic(TestBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    questions: List[QuestionPublic]


class AssignmentRequest(BaseModel):
    user_ids: List[int]


class SubmitAnswer(BaseModel):
    question_id: int
    answer_option_ids: List[int] = Field(default_factory=list)
    answer_option_id: Optional[int] = None

    def selected_ids(self) -> set[int]:
        selected = set(self.answer_option_ids)
        if self.answer_option_id is not None:
            selected.add(self.answer_option_id)
        return selected


class SubmitAttemptRequest(BaseModel):
    answers: List[SubmitAnswer]


class AttemptAnswerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    question_id: int
    answer_option_id: int


class AttemptOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    test_id: int
    started_at: datetime
    finished_at: datetime
    score_percent: float
    passed: bool
    answers: List[AttemptAnswerOut]


class AttemptAnswerDetailed(BaseModel):
    question_id: int
    question_text: str
    selected_option_ids: List[int]
    selected_option_text: str
    correct_option_ids: List[int]
    correct_option_text: str
    is_correct: bool


class AttemptDetailed(BaseModel):
    id: int
    test_id: int
    score_percent: float
    passed: bool
    finished_at: datetime
    answers: List[AttemptAnswerDetailed]


class ProgressItem(BaseModel):
    test_id: int
    test_title: str
    best_score: float
    attempts: int
    last_attempt_date: Optional[datetime] = None


class ResultSummary(BaseModel):
    user_id: int
    user_name: str
    test_id: int
    test_title: str
    best_score: float
    attempts: int
    passed: bool


class DetailedAttempt(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    test_id: int
    score_percent: float
    passed: bool
    finished_at: datetime
