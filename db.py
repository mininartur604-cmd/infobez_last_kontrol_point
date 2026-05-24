from typing import Annotated, List, Optional

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import select, LargeBinary, ForeignKey

from fastapi import Depends, FastAPI, HTTPException, Response

from pydantic import BaseModel, Field,EmailStr, ConfigDict

from authx import AuthX, AuthXConfig

from secret_file import secret_JWT_key, db_link

import bcrypt
import asyncio

config = AuthXConfig()
config.JWT_SECRET_KEY = secret_JWT_key
config.JWT_ACCESS_COOKIE_NAME = "my_access_token"
config.JWT_TOKEN_LOCATION = ["cookies"]

security = AuthX(config=config)

engine = create_async_engine(db_link)
new_session = async_sessionmaker(engine, expire_on_commit=False)

async def get_session():
    async with new_session() as session:
        yield session

SessionDeb = Annotated[AsyncSession, Depends(get_session)]

class Base(DeclarativeBase):
    pass

class GroupModel(Base):
    __tablename__ = "group"

    group_number: Mapped[str] = mapped_column(primary_key=True)

    students: Mapped[List["StudentModel"]] = relationship(back_populates="group_rel")
    group_tasks: Mapped[List["GroupTaskModel"]] = relationship(back_populates="group_rel")


class TaskModel(Base):
    __tablename__ = "task" 

    id: Mapped[int] = mapped_column(primary_key=True)
    description: Mapped[str]
    path: Mapped[str]
    
    group_tasks: Mapped[List["GroupTaskModel"]] = relationship(back_populates="task_rel")
    grades: Mapped[List["GradeModel"]] = relationship(back_populates="task_rel")


class GroupTaskModel(Base):
    __tablename__ = "group_task"

    id: Mapped[int] = mapped_column(primary_key=True)
    
    task_id: Mapped[int] = mapped_column(ForeignKey("task.id", ondelete="CASCADE"))
    group_number: Mapped[str] = mapped_column(ForeignKey("group.group_number", ondelete="CASCADE"))

    task_rel: Mapped["TaskModel"] = relationship(back_populates="group_tasks")
    group_rel: Mapped["GroupModel"] = relationship(back_populates="group_tasks")


class StudentModel(Base):
    __tablename__ = "student"

    id: Mapped[int] = mapped_column(primary_key=True)
    first_name: Mapped[str]
    second_name: Mapped[str]
    middle_name: Mapped[str]
    login: Mapped[str]
    password: Mapped[bytes] = mapped_column(LargeBinary)
    
    group_number: Mapped[str] = mapped_column(ForeignKey("group.group_number"))

    group_rel: Mapped["GroupModel"] = relationship(back_populates="students") 
    grades: Mapped[List["GradeModel"]] = relationship(back_populates="student_rel")


class TeacherModel(Base):
    __tablename__ = "teacher"

    id: Mapped[int] = mapped_column(primary_key=True)
    first_name: Mapped[str]
    second_name: Mapped[str]
    middle_name: Mapped[str]
    login: Mapped[str]
    password: Mapped[bytes] = mapped_column(LargeBinary)

class GradeModel(Base):
    __tablename__ = "grade"
    
    student_id: Mapped[int] = mapped_column(ForeignKey("student.id", ondelete="CASCADE"), primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("task.id", ondelete="CASCADE"), primary_key=True)
    solution_path: Mapped[str]
    grade_value: Mapped[int] 

    student_rel: Mapped["StudentModel"] = relationship(back_populates="grades")
    task_rel: Mapped["TaskModel"] = relationship(back_populates="grades")

app = FastAPI()

class StudentAddSchema(BaseModel):
    first_name: str
    second_name: str
    middle_name: str
    login: str
    password: bytes
    group_number: str

class GroupAddSchema(BaseModel):
    group_number: str
    
class LoginSchema(BaseModel):
    login: str
    password: str


async def get_password_hash(password: str | bytes) -> bytes:
    # Конвертируем строку в байты, если передана строка
    if isinstance(password, str):
        password = password.encode('utf-8')
        
    # Генерируем соль и хешируем в отдельном потоке, чтобы не блокировать event loop
    salt = await asyncio.to_thread(bcrypt.gensalt)
    hashed = await asyncio.to_thread(bcrypt.hashpw, password, salt)
    
    return hashed

async def verify_password(plain_password: str, hashed_password: bytes) -> bool:
    plain_bytes = plain_password.encode('utf-8') 
    return await asyncio.to_thread(bcrypt.checkpw, plain_bytes, hashed_password)

@app.post("/setup_database")
async def setup_database():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    return {"ok":True, "msg": "База данных создана"}

@app.post("/login")
async def login(
    credentials: LoginSchema,
    response: Response,
    session: SessionDeb
):
    # 1. Ищем пользователя в БД по имени
    query = select(StudentModel).where(StudentModel.login == credentials.login)
    result = await session.execute(query)
    user = result.scalar_one_or_none()
    
    # 2. Проверяем существование пользователя и валидность пароля
    if not user or not await verify_password(credentials.password, user.password):
        raise HTTPException(status_code=401, detail="Некорректное имя пользователя или пароль")
        
    # 3. Создаем токен (в uid передаем реальный ID из базы данных)
    token = security.create_access_token(uid=str(user.id))
    response.set_cookie(config.JWT_ACCESS_COOKIE_NAME, token)
    return {"access_token": token}


@app.post("/groups")
async def add_group(data: GroupAddSchema, session: SessionDeb):
    
    new_group = GroupModel(
        group_number = data.group_number
    )
    session.add(new_group)
    await session.commit()
    return {"ok":True, "msg": "Добавлен новый ученик"}

@app.post("/students")
async def add_student(data: StudentAddSchema, session: SessionDeb):
    hashed_pwd = await get_password_hash(data.password)
    new_student = StudentModel(
        first_name = data.first_name,
        second_name = data.second_name,
        middle_name = data.middle_name,
        login =  data.login,
        password =  hashed_pwd,
        group_number= data.group_number
    )
    session.add(new_student)
    await session.commit()
    return {"ok":True, "msg": "Добавлена новая группа"}

@app.get("/students")
async def get_students(session: SessionDeb):
    query = select(StudentModel)
    result = await session.execute(query)
    return result.scalars().all()