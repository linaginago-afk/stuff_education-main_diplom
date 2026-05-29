import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from .database import Base, engine, SessionLocal
from .models import User
from .security import get_password_hash
from .routers import auth, users, tests, assignments, employee, reports

Base.metadata.create_all(bind=engine)

app = FastAPI(title="АИС ПУОП Теремок", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _ensure_admin_user():
    username = os.getenv("INIT_ADMIN_USERNAME", "admin")
    password = os.getenv("INIT_ADMIN_PASSWORD", "admin")
    full_name = os.getenv("INIT_ADMIN_FULLNAME", "Администратор")
    with SessionLocal() as db:
        exists = db.query(User).filter(User.username == username).first()
        if not exists:
            admin = User(
                full_name=full_name,
                username=username,
                password_hash=get_password_hash(password),
                role="admin",
                department=None,
            )
            db.add(admin)
            db.commit()


_ensure_admin_user()

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(tests.router)
app.include_router(assignments.router)
app.include_router(employee.router)
app.include_router(reports.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}


frontend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))
app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")
