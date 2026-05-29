import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = os.getenv(
    "DATABASE_URL", "mysql+pymysql://teremok_user:StrongPass123@localhost:3306/teremok"
)

# Настройки подключения
connect_args = {}

# Если используется SQLite
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}
else:
    # Для MySQL (Aiven) добавляем настройки SSL
    connect_args = {
        "ssl": {
            "check_hostname": False,
            "use_openssl_context": False
        }
    }

engine = create_engine(
    DATABASE_URL, 
    echo=False, 
    future=True, 
    connect_args=connect_args,
    pool_pre_ping=True,  # Проверяет соединение перед использованием
    pool_recycle=3600     # Пересоздаёт соединение каждый час
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()