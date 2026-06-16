import os
from dotenv import load_dotenv
# СНАЧАЛА ЗАГРУЖАЕМ ОКРУЖЕНИЕ ИЗ ФАЙЛА .ENV
load_dotenv()  
from typing import Annotated, List, Optional, Any


from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, selectinload
from sqlalchemy import select, LargeBinary, ForeignKey, String, Text, DateTime, Table, Column,func
from sqlalchemy.exc import DBAPIError, IntegrityError

from fastapi import Depends, FastAPI, HTTPException, Response, status, Request, UploadFile, File
from fastapi.security import HTTPBearer
from fastapi.responses import PlainTextResponse, FileResponse

from pydantic import BaseModel, Field,EmailStr, ConfigDict

from authx import AuthX, AuthXConfig, TokenPayload

import bcrypt
import asyncio
from cryptography.fernet import Fernet

from datetime import timedelta, datetime
import re

import shutil
import time
import logging
from logging.handlers import TimedRotatingFileHandler


raw_key = os.getenv("ENCRYPTION_KEY")

if not raw_key:
    raise ValueError("КРИТИЧЕСКАЯ ОШИБКА: ENCRYPTION_KEY не найден в файле .env!")

# Переводим в байты и создаем объект Fernet
fernet = Fernet(raw_key.encode())

def encrypt_data(text: str) -> str:
    """Шифрует строку в безопасный хэш"""
    if not text:
        return text
    return fernet.encrypt(text.encode()).decode()

def decrypt_data(cipher_text: str) -> str:
    """Расшифровывает хэш обратно в понятный текст"""
    if not cipher_text:
        return cipher_text
    try:
        # Для расшифровки передаем байты строки из БД
        return fernet.decrypt(cipher_text.encode()).decode()
    except Exception:
        # Если данные в базе не были зашифрованы (старые данные), возвращаем как есть
        return cipher_text
    
app = FastAPI()


config = AuthXConfig()
config.JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")  
config.JWT_TOKEN_LOCATION = ["cookies"]  
config.JWT_ACCESS_COOKIE_NAME = "access_token"  
config.JWT_COOKIE_CSRF_PROTECT = False  
config.JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)
config.JWT_COOKIE_SECURE = True  
config.JWT_COOKIE_SAMESITE = "lax"  

security = AuthX(config=config)
security.handle_errors(app)

BASE_UPLOAD_DIR = "upload"

async def get_current_user_claims(
    authx_data: Annotated[Any, Depends(security.access_token_required)]
) -> TokenPayload:
    """Извлекает данные из AuthX и собирает из них ваш TokenPayload"""
    
    uid = getattr(authx_data, "sub", None) or getattr(authx_data, "uid", None)
    claims = getattr(authx_data, "custom_claims", None)
    
    if not claims and hasattr(authx_data, "role"):
        claims = {
            "role": getattr(authx_data, "role", None),
            "group_number": getattr(authx_data, "group_number", None)
        }
        
    if not claims:
        claims = getattr(authx_data, "user_claims", {})
        
    if not claims:
        claims = {}

    return TokenPayload(
        sub=str(uid) if uid else "",
        role=claims.get("role"),
        group_number=claims.get("group_number")
    )

class RoleChecker:
    """Класс-зависимость для проверки конкретной роли пользователя"""
    def __init__(self, allowed_roles: List[str]):
        self.allowed_roles = allowed_roles

    def __call__(self, payload: Annotated[TokenPayload, Depends(get_current_user_claims)]):
    
        user_role = payload.role 
        group_number = payload.group_number
        
        if user_role not in self.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="У вас нет доступа к этому ресурсу"
            )
        return payload

allow_teachers = RoleChecker(["teacher"])
allow_students = RoleChecker(["student"])
allow_admins = RoleChecker(["admin"])
allow_all = RoleChecker(["teacher", "student","admin"])

DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")

DATABASE_URL = f"postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
engine = create_async_engine(DATABASE_URL)
new_session = async_sessionmaker(engine, expire_on_commit=False)

async def get_session():
    async with new_session() as session:
        yield session

SessionDeb = Annotated[AsyncSession, Depends(get_session)]

class Base(DeclarativeBase):
    pass

teacher_group = Table(
    "teacher_group",
    Base.metadata,
    Column("teacher_id", ForeignKey("user.id", ondelete="CASCADE"), primary_key=True),
    Column("group_number", ForeignKey("group.group_number", ondelete="CASCADE"), primary_key=True),
)

class UserModel(Base):
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False)  # "student", "teacher", "admin"
    login: Mapped[str] = mapped_column(unique=True)
    password: Mapped[bytes] = mapped_column(LargeBinary)
    
    first_name: Mapped[str]
    second_name: Mapped[str]
    middle_name: Mapped[Optional[str]]

    group_number: Mapped[Optional[str]] = mapped_column(ForeignKey("group.group_number", ondelete="SET NULL"))

    grades: Mapped[List["GradeModel"]] = relationship(back_populates="student_rel")
    
    group_rel: Mapped[Optional["GroupModel"]] = relationship(back_populates="students")
    
    managed_groups: Mapped[List["GroupModel"]] = relationship(
        secondary=teacher_group, back_populates="teachers"
    )


class GroupModel(Base):
    __tablename__ = "group"

    group_number: Mapped[str] = mapped_column(String(50), primary_key=True)

    students: Mapped[List["UserModel"]] = relationship(
        back_populates="group_rel", 
        foreign_keys="[UserModel.group_number]"
    )
    
    teachers: Mapped[List["UserModel"]] = relationship(
        secondary=teacher_group, 
        back_populates="managed_groups"
    )
    
    group_tasks: Mapped[List["GroupTaskModel"]] = relationship(
        back_populates="group_rel",
        cascade="all, delete-orphan"
    )


class TaskModel(Base):
    __tablename__ = "task"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    deadline: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    
    group_tasks: Mapped[List["GroupTaskModel"]] = relationship(
        back_populates="task_rel",
        cascade="all, delete-orphan"
    )


class GroupTaskModel(Base):
    __tablename__ = "group_task"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("task.id", ondelete="CASCADE"))
    group_number: Mapped[str] = mapped_column(ForeignKey("group.group_number", ondelete="CASCADE"))

    task_rel: Mapped["TaskModel"] = relationship(back_populates="group_tasks")
    group_rel: Mapped["GroupModel"] = relationship(back_populates="group_tasks")
    

class GradeModel(Base):
    __tablename__ = "grade"
    
    student_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("task.id", ondelete="CASCADE"), primary_key=True)
    solution_path: Mapped[str]  
    grade_value: Mapped[int | None] = mapped_column(nullable=True, default=None) 

    student_rel: Mapped["UserModel"] = relationship(back_populates="grades")
    
    
class StudentAddSchema(BaseModel):
    email: EmailStr
    login: str
    password: str
    first_name: str
    second_name: str
    middle_name: str | None = None  
   

class AdminAddSchema(BaseModel):
    email: EmailStr
    login: str
    password: str
    first_name: str
    second_name: str
    middle_name: str | None = None  
    
class AdminChangePasswordSchema(BaseModel):
    login: str 
    new_password: str 

class GroupAddSchema(BaseModel):
    group_number: str

class TaskAddShema(BaseModel):
    title: str
    description: str
    deadline: datetime | None = Field(None, description="Дата и время дедлайна")
    group_numbers: list[str] = Field(..., description="Список групп, которым назначается задача")
    
class LoginSchema(BaseModel):
    login: str
    password: str

class TeacherAddSchema(BaseModel):
    email: EmailStr
    login: str
    password: str  
    first_name: str
    second_name: str
    middle_name: str | None = None  
    group_numbers: list[str] = []

class AddGroupsToTeacherSchema(BaseModel):
    login: str
    group_numbers: list[str]

class GradeValueSchema(BaseModel):
    grade_value: int 

class UpdateStudentGroupSchema(BaseModel):
    login: str 
    group_number: str 

os.makedirs("logs", exist_ok=True)

file_handler = TimedRotatingFileHandler(
    filename="logs/app.log",
    when="midnight",      
    interval=1,           
    backupCount=7,        
    encoding="utf-8"
)

log_format = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
file_handler.setFormatter(log_format)

console_handler = logging.StreamHandler()
console_handler.setFormatter(log_format)

logger = logging.getLogger("app_logger")
logger.setLevel(logging.INFO)
logger.addHandler(file_handler)
logger.addHandler(console_handler)

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    host = request.client.host if request.client else "unknown"
    
    try:
        response = await call_next(request)
        process_time = (time.time() - start_time) * 1000
        
        logger.info(
            f"IP: {host} | {request.method} {request.url.path} | "
            f"Status: {response.status_code} | Time: {process_time:.2f}ms"
        )
        return response
        
    except Exception as e:
        process_time = (time.time() - start_time) * 1000
        logger.error(
            f"IP: {host} | {request.method} {request.url.path} | "
            f"CRITICAL ERROR: {str(e)} | Time: {process_time:.2f}ms"
        )
        raise e
    
async def get_password_hash(password: str | bytes) -> bytes:
    if isinstance(password, str):
        password = password.encode('utf-8')
        
    salt = await asyncio.to_thread(bcrypt.gensalt)
    hashed = await asyncio.to_thread(bcrypt.hashpw, password, salt)
    
    return hashed

async def verify_password(plain_password: str, hashed_password: bytes) -> bool:
    plain_bytes = plain_password.encode('utf-8') 
    return await asyncio.to_thread(bcrypt.checkpw, plain_bytes, hashed_password)

async def optional_admin_claims(session: SessionDeb) -> TokenPayload | None:
    try:
        # Пытаемся получить данные текущего пользователя
        return await get_current_user_claims(session)
    except Exception:
        # Если токена нет, он протух или невалиден — просто возвращаем None
        return None


@app.post("/setup_database")
async def setup_database():
    """
    Инициализация базы данных.
    Вызов возможен ТОЛЬКО если таблицы ещё не созданы.
    """
    
    # 1. Проверяем, существует ли таблица user
    try:
        async with AsyncSession(engine) as session:
            # Пытаемся выполнить простой запрос к таблице user
            query = select(UserModel).limit(1)
            await session.execute(query)
            
            # Если запрос успешен - таблица существует
            logger.warning("ACTION: Попытка инициализации, но таблицы уже существуют.")
            return {
                "ok": False, 
                "msg": "База данных уже инициализирована. Таблицы существуют. "
                       "Для пересоздания сначала удалите таблицы через SQL."
            }
            
    except (ProgrammingError, OperationalError) as e:
        # Таблица не существует - можно создавать
        if 'does not exist' in str(e).lower() or 'relation' in str(e).lower():
            logger.info("INFO: Таблицы не найдены. Выполняется инициализация...")
        else:
            # Другая ошибка подключения
            logger.error(f"ERROR: Ошибка подключения к БД: {str(e)}")
            return {
                "ok": False,
                "msg": f"Ошибка подключения к базе данных: {str(e)}"
            }
    
    # 2. Создаем таблицы
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            
        async with AsyncSession(engine) as session:
            raw_hash = await get_password_hash("admin")
            byte_password = raw_hash.encode("utf-8") if isinstance(raw_hash, str) else raw_hash
            
            default_admin = UserModel(
                login="admin",
                email=encrypt_data("defaultemail@gmail.com"),
                password=byte_password, 
                role="admin",
                first_name=encrypt_data("Главный"),
                second_name=encrypt_data("Администратор"),
                group_number=None
            )
            
            session.add(default_admin)
            await session.commit()
            
        logger.info("ACTION: База данных инициализирована.")
        return {"ok": True, "msg": "База данных успешно инициализирована"}
        
    except Exception as e:
        logger.error(f"ERROR: Ошибка инициализации: {str(e)}")
        return {
            "ok": False,
            "msg": f"Ошибка при инициализации: {str(e)}"
        }

@app.post("/login")
async def login(
    credentials: LoginSchema,
    response: Response,
    session: SessionDeb
):
    query = (
        select(UserModel)
        .where(UserModel.login == credentials.login)
        .options(selectinload(UserModel.managed_groups)) 
    )
    result = await session.execute(query)
    user = result.scalar_one_or_none()
    
    if not user or not await verify_password(credentials.password, user.password):
        raise HTTPException(status_code=401, detail="Некорректное имя пользователя или пароль")

    group_info = None
    if user.role == "student":
        group_info = user.group_number
    elif user.role == "teacher":
        
        group_info = [g.group_number for g in user.managed_groups]
        
    token_claims = {
        "role": user.role,
        "group_number": group_info,
        "username": user.login,
    }
    
    token = security.create_access_token(
        uid=str(user.id),
        data=token_claims
    )
    
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=False,       # Для production поменяйте на True
        samesite="lax",
        max_age=3600
    )
    
    return {
        "message": "Успешный вход",
        "uid": user.id,
        "role": user.role,
        "group_id": user.group_number,
        
    }

@app.post("/logout")
async def logout(response: Response):
    """Выход - удаляем cookie с токеном"""
    response.delete_cookie(
        key="access_token",
        httponly=True,
        secure=False,
        samesite="lax"
    )
    return {"message": "Успешный выход"}


@app.post("/groups")
async def add_group(data: GroupAddSchema, session: SessionDeb):
    
    new_group = GroupModel(
        group_number = data.group_number
    )
    session.add(new_group)
    await session.commit()
    return {"ok":True, "msg": "Добавлена новая группа"}

@app.post("/students")
async def add_student(data: StudentAddSchema, session: SessionDeb):
    # 1. Хэшируем пароль и приводим его к байтам для BYTEA-колонки
    hashed_pwd = await get_password_hash(data.password)
    if isinstance(hashed_pwd, str):
        hashed_pwd = hashed_pwd.encode("utf-8")
        
    role = "student"
    
    # 2. Формируем объект студента
    # group_number изначально ставим None (админ привяжет группу позже через /assign-group)
    new_student = UserModel(
        email=encrypt_data(data.email),
        role=role,
        login=data.login,  # Логин остается в открытом виде для быстрого поиска
        password=hashed_pwd,
        first_name=encrypt_data(data.first_name),
        second_name=encrypt_data(data.second_name),
        middle_name=encrypt_data(data.middle_name) if data.middle_name else None,
        group_number=None  
    )
    
    try:
        session.add(new_student)
        # Применяем изменения в БД
        await session.commit()
        
        # ЛОГ УСПЕШНОГО ДЕЙСТВИЯ:
        logger.info(
            f"ACTION: Успешно добавлен новый студент. "
            f"Логин: '{data.login}' | Email: '{data.email}'"
        )
        return {"ok": True, "msg": "Добавлен новый студент"}

    except IntegrityError as e:
        # Откатываем транзакцию сессии, чтобы база данных не заблокировалась
        await session.rollback()
        
        # Проверяем, произошла ли ошибка из-за уникальности (UniqueViolationError)
        # Например, если студент с таким логином уже есть в базе данных
        if "unique constraint" in str(e.orig).lower() or "duplicate key" in str(e.orig).lower():
            logger.warning(
                f"REGISTRATION FAILED: Попытка регистрации существующего логина '{data.login}'"
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Пользователь с логином '{data.login}' уже зарегистрирован в системе"
            )
        
        # Если произошла другая ошибка ограничений БД
        logger.error(f"DATABASE INTEGRITY ERROR во время регистрации студента: {str(e.orig)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ошибка нарушения целостности данных при сохранении в базу данных"
        )
        
    except Exception as e:
        # Перехват любых других непредвиденных системных ошибок
        await session.rollback()
        logger.error(f"SYSTEM ERROR во время регистрации студента '{data.login}': {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Внутренняя ошибка сервера при обработке запроса"
        )

@app.post("/teachers")
async def add_teacher(data: TeacherAddSchema, session: SessionDeb, payload: TokenPayload = Depends(allow_admins)):
    hashed_pwd = await get_password_hash(data.password)
    
    groups_db = []
    if data.group_numbers:
        
        groups_query = select(GroupModel).where(GroupModel.group_number.in_(data.group_numbers))
        groups_result = await session.execute(groups_query)
        groups_db = list(groups_result.scalars().all())  
        
        if len(groups_db) != len(data.group_numbers):
            found_numbers = {g.group_number for g in groups_db}
            missing = set(data.group_numbers) - found_numbers
            raise HTTPException(
                status_code=400, 
                detail=f"Сначала создайте эти группы в БД: {list(missing)}. Сейчас привязка невозможна."
            )
        
    new_teacher = UserModel(
        email=encrypt_data(data.email),
        role="teacher",
        login=data.login,
        password=hashed_pwd,
        first_name=encrypt_data(data.first_name),
        second_name=encrypt_data(data.second_name),
        middle_name=encrypt_data(data.middle_name),
        group_number=None,
        managed_groups=groups_db  
    )
    
    session.add(new_teacher)
    
    await session.commit()
    
    return {"ok": True, "msg": f"Добавлен учитель. Привязано групп: {len(groups_db)}"}

@app.post("/api/admins")
async def add_admin(
    data: AdminAddSchema, 
    session: SessionDeb,
    payload: TokenPayload = Depends(allow_admins)  # Строгая проверка: доступ только для админов
):
    # 1. Проверяем, не занят ли уже такой логин (ищем в открытом виде!)
    query = select(UserModel).where(UserModel.login == data.login)
    result = await session.execute(query)
    existing_user = result.scalar_one_or_none()
    
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Пользователь с логином '{data.login}' уже зарегистрирован"
        )

    # 2. Хэшируем пароль и определяем роль
    hashed_pwd = await get_password_hash(data.password)
    role = "admin"
    
    # 3. Создаем объект администратора с зашифрованными данными
    new_admin = UserModel(
        login = data.login,                      # ОСТАВЛЯЕМ В ОТКРЫТОМ ВИДЕ ДЛЯ ПОИСКА ПРИ ЛОГИНЕ!
        email = encrypt_data(data.email),         # Email можно зашифровать, если вход только по логину
        role = role,
        password = hashed_pwd,
        first_name = encrypt_data(data.first_name),
        second_name = encrypt_data(data.second_name),
        middle_name = encrypt_data(data.middle_name) if data.middle_name else None,
        group_number = None                      # У администратора нет группы
    )
    
    session.add(new_admin)
    await session.commit()
    
    # Записываем действие в наш ежедневный логгер
    logger.info(
        f"ACTION: Администратор (ID: {payload.sub}) добавил нового администратора. "
        f"Логин: '{data.login}'"
    )
    
    return {"ok": True, "msg": "Добавлен новый администратор"}

@app.post("/admins/add-groups")
async def add_groups_to_teacher(data: AddGroupsToTeacherSchema, session: SessionDeb, payload: TokenPayload = Depends(allow_admins)):
    
    teacher_query = (
        select(UserModel)
        .options(selectinload(UserModel.managed_groups))
        .where(UserModel.login == data.login, UserModel.role == "teacher")
    )
    teacher_result = await session.execute(teacher_query)
    teacher = teacher_result.scalar_one_or_none()
    
    if not teacher:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Учитель с таким логином не найден")
        
    groups_query = select(GroupModel).where(GroupModel.group_number.in_(data.group_numbers))
    groups_result = await session.execute(groups_query)
    groups_to_add = groups_result.scalars().all()
    
    found_numbers = {g.group_number for g in groups_to_add}
    missing_groups = set(data.group_numbers) - found_numbers
    if missing_groups:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail=f"Группы не найдены: {list(missing_groups)}"
        )
        
    current_group_numbers = {g.group_number for g in teacher.managed_groups}
    for group in groups_to_add:
        if group.group_number not in current_group_numbers:
            teacher.managed_groups.append(group)
            
    await session.commit()
    return {"ok": True, "msg": f"Учителю {data.login} успешно добавлены новые группы"}

@app.post("/admins/remove-groups")
async def remove_groups_from_teacher(data: AddGroupsToTeacherSchema, session: SessionDeb, payload: TokenPayload = Depends(allow_admins)):
    # 1. Находим учителя по логину с его группами
    teacher_query = (
        select(UserModel)
        .options(selectinload(UserModel.managed_groups))
        .where(UserModel.login == data.login, UserModel.role == "teacher")
    )
    teacher_result = await session.execute(teacher_query)
    teacher = teacher_result.scalar_one_or_none()
    
    if not teacher:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Учитель с таким логином не найден")
        
    removed_count = 0
    for group in list(teacher.managed_groups):
        if group.group_number in data.group_numbers:
            teacher.managed_groups.remove(group)
            removed_count += 1
            
    if removed_count == 0:
        return {"ok": True, "msg": "У учителя не было привязок к указанным группам, ничего не удалено"}
        
    await session.commit()
    return {"ok": True, "msg": f"У учителя {data.login} успешно удалено групп: {removed_count}"}


@app.get("/api/profile")
async def get_profile(
    session: SessionDeb,
    payload: TokenPayload = Depends(allow_all)
):
    """Возвращает информацию о текущем пользователе с расшифрованными персональными данными"""
    user_id = payload.sub  
    role = payload.role
    token_group = payload.group_number # Группа, зашитая в токен

    # 1. Запрашиваем пользователя из базы данных
    query = select(UserModel).where(UserModel.id == int(user_id))
    result = await session.execute(query)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Пользователь не найден в системе"
        )

    # 2. Формируем ответ с расшифровкой защищенных полей
    profile_data = {
        "user_id": user.id,      
        "role": role,
        "group_number": token_group, # Передаем группу из токена (или user.group_number)
        "login": user.login,         # Логин хранится в открытом виде
        "email": decrypt_data(user.email),
        "first_name": decrypt_data(user.first_name),
        "second_name": decrypt_data(user.second_name),
        "middle_name": decrypt_data(user.middle_name) if user.middle_name else None
    }

    # Логируем запрос профиля
    logger.info(f"ACTION: [{role.upper()} ID: {user_id}] открыл свой профиль")

    return {
        "ok": True,
        "profile": profile_data
    }


@app.post("/api/task")
async def add_task(
    data: TaskAddShema, 
    session: SessionDeb, 
    payload: TokenPayload = Depends(allow_teachers)
):
    if not data.group_numbers:
        return {"ok": False, "msg": "Необходимо указать хотя бы одну группу"}

    naive_deadline = data.deadline
    if naive_deadline and naive_deadline.tzinfo is not None:
        naive_deadline = naive_deadline.replace(tzinfo=None)

    # УБРАЛИ РЕШЕТКИ ЗДЕСЬ:
    new_task = TaskModel(
        title=data.title,
        description=data.description,
        deadline=naive_deadline 
    )
    session.add(new_task)
    
    await session.flush() 

    for group_num in data.group_numbers:
        group_task_binding = GroupTaskModel(
            task_id=new_task.id,  
            group_number=group_num
        )
        session.add(group_task_binding)
    
    await session.commit()
    
    logger.info(
        f"ACTION: Учитель (ID: {payload.sub}) успешно добавил новую задачу "
        f"'{data.title}' для групп: {data.group_numbers}"
    )
    
    return {"ok": True, "msg": f"Задача успешно добавлена для групп: {', '.join(data.group_numbers)}"}

@app.post("/api/solution/{task_id}")
async def upload_solution(
    task_id: int,
    session: SessionDeb,
    files: Annotated[list[UploadFile], File(description="Выделите несколько файлов")],
    payload: TokenPayload = Depends(allow_students)
):
    student_id = int(payload.sub)
    group_number = payload.group_number

    if not group_number:
        raise HTTPException(status_code=400, detail="У студента не указана группа в токене")

    ALLOWED_EXTENSIONS = {".py", ".json"}
    FILENAME_REGEX = re.compile(r"^[a-zA-Z0-9_]+$")
    
    for file in files:
        name_without_ext, ext = os.path.splitext(file.filename)
        
        if ext.lower() not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Недопустимый формат файла: {file.filename}. Разрешены только .py и .json"
            )
            
        if not FILENAME_REGEX.match(name_without_ext):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Недопустимое имя файла: '{file.filename}'. "
                    f"Разрешены только латинские буквы, цифры и символ '_'"
                )
            )

    student_dir = os.path.join(BASE_UPLOAD_DIR, str(group_number), str(student_id), f"task_{task_id}")
    os.makedirs(student_dir, exist_ok=True)

    main_py_path = None

    for file in files:
        file_path = os.path.join(student_dir, file.filename)
        
        contents = await file.read()
        with open(file_path, "wb") as f:
            f.write(contents)
        
        if file.filename == "main.py":
            main_py_path = file_path

    final_solution_path = main_py_path if main_py_path else student_dir

    grade_entry = await session.get(GradeModel, (student_id, task_id))
    
    if grade_entry:
        grade_entry.solution_path = final_solution_path
    else:
        grade_entry = GradeModel(
            student_id=student_id,
            task_id=task_id,
            solution_path=final_solution_path,
            grade_value=None
        )
        session.add(grade_entry)

    await session.commit()

    # ПРАВИЛЬНЫЙ И ИНФОРМАТИВНЫЙ ЛОГ:
    filenames_list = [f.filename for f in files]
    logger.info(
        f"ACTION: [STUDENT ID: {student_id} | Группа: {group_number}] "
        f"загрузил решение для задачи (ID: {task_id}). "
        f"Файлов: {len(files)} {filenames_list} | Путь в БД: '{final_solution_path}'"
    )

    return {"ok": True, "msg": "Решение успешно загружено", "path": final_solution_path}

@app.get("/api/solution/files-list")
async def list_solution_files(
    group_number: str,
    student_id: int,
    task_id: int,
    payload: TokenPayload = Depends(allow_teachers)  
):
    target_dir = os.path.join(BASE_UPLOAD_DIR, group_number, str(student_id), f"task_{task_id}")
    
    if not os.path.exists(target_dir):
        raise HTTPException(status_code=404, detail="Папка с решением не найдена на сервере")
    
    files = []
    for root, _, filenames in os.walk(target_dir):
        for filename in filenames:
            rel_path = os.path.relpath(os.path.join(root, filename), target_dir)
            files.append(rel_path)
            
    logger.info(
        f"ACTION: [TEACHER ID: {payload.sub}] успешно запросил список файлов решения. "
        f"Студент (ID: {student_id}) | Группа: '{group_number}' | Задача (ID: {task_id}) | Найдено файлов: {len(files)}"
    )
    return {"group": group_number, "student_id": student_id, "task_id": task_id, "files": files}

@app.get("/api/solution/read-file")
async def read_solution_file(
    group_number: str,
    student_id: int,
    task_id: int,
    file_relative_path: str,  
    as_text: bool = True,     
    payload: TokenPayload = Depends(allow_all)
):
    # Защита от Directory Traversal
    safe_path = os.path.normpath(file_relative_path).lstrip(chr(47)).lstrip(chr(92))
    file_path = os.path.join(BASE_UPLOAD_DIR, group_number, str(student_id), f"task_{task_id}", safe_path)

    if not os.path.exists(file_path) or os.path.isdir(file_path):
        raise HTTPException(status_code=404, detail="Файл не найден")

    # Текстовый режим (вывод кода на экран)
    if as_text:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            
            # Логируем успешное чтение текста
            logger.info(
                f"ACTION: [{payload.role.upper()} ID: {payload.sub}] прочитал код файла "
                f"'{safe_path}' студента (ID: {student_id}) по задаче (ID: {task_id})"
            )
            return PlainTextResponse(content)
        except UnicodeDecodeError:
            pass

    # Режим скачивания (бинарный файл или архив)
    logger.info(
        f"ACTION: [{payload.role.upper()} ID: {payload.sub}] скачал файл "
        f"'{safe_path}' студента (ID: {student_id}) по задаче (ID: {task_id})"
    )
    return FileResponse(path=file_path, filename=os.path.basename(file_path))

@app.post("/api/solution/{task_id}/student/{student_id}/grade")
async def set_grade_automatic(
    task_id: int,
    student_id: int,
    data: GradeValueSchema,
    session: SessionDeb,
    payload: TokenPayload = Depends(allow_teachers)
):
    
    grade_entry = await session.get(GradeModel, (student_id, task_id))
    
    if not grade_entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Студент еще не загрузил решение. Нечего оценивать."
        )
        
    grade_entry.grade_value = data.grade_value
    await session.commit()
    
    logger.info(
        f"ACTION: Учитель (ID: {payload.sub}) выставил оценку {data.grade_value} "
        f"студенту (ID: {student_id}) за задание (ID: {task_id})"
    )

    return {
        "ok": True, 
        "msg": f"Оценка {data.grade_value} успешно сохранена",
        "task_id": task_id,
        "student_id": student_id
    }

@app.get("/api/my-tasks")
async def get_student_tasks(
    session: SessionDeb,
    payload: TokenPayload = Depends(allow_students)
):
    # 1. Извлекаем номер группы студента из токена
    student_group = payload.group_number

    if not student_group:
        raise HTTPException(
            status_code=400, 
            detail="В вашем токене авторизации отсутствует номер группы."
        )

    # 2. Строим запрос: выбираем задачи, которые связаны с группой студента
    query = (
        select(TaskModel)
        .join(GroupTaskModel, TaskModel.id == GroupTaskModel.task_id)
        .where(GroupTaskModel.group_number == student_group)
        .order_by(TaskModel.deadline.asc())
    )

    result = await session.execute(query)
    tasks = result.scalars().all()

    # 3. Формируем ответ БЕЗ ОБРАЩЕНИЯ К task.files
    formatted_tasks = []
    for task in tasks:
        # Ищем оценку студента за эту задачу
        grade_query = select(GradeModel).where(
            GradeModel.student_id == int(payload.sub),
            GradeModel.task_id == task.id
        )
        grade_result = await session.execute(grade_query)
        grade = grade_result.scalar_one_or_none()
        
        formatted_tasks.append({
            "id": task.id,
            "title": task.title,
            "description": task.description,
            "deadline": task.deadline,
            "grade": grade.grade_value if grade else None
        })

    # Логируем успешное получение списка задач студентом
    logger.info(
        f"ACTION: [STUDENT ID: {payload.sub}] запросил список задач для группы '{student_group}'. "
        f"Найдено задач: {len(formatted_tasks)}"
    )

    return {
        "ok": True,
        "group_number": student_group,
        "tasks": formatted_tasks
    }

@app.get("/api/tasks/{task_id}")
async def get_task_detail(
    task_id: int,
    session: SessionDeb,
    payload: TokenPayload = Depends(allow_all)
):
    # 1. Загружаем задачу из БД (УБИРАЕМ .files, так как его нет!)
    query = select(TaskModel).where(TaskModel.id == task_id)
    result = await session.execute(query)
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Задание с ID {task_id} не найдено в системе"
        )

    # 2. ЗАЩИТА ДЛЯ СТУДЕНТОВ: проверяем, назначено ли это задание их группе
    if payload.role == "student":
        student_group = payload.group_number
        
        # Ищем, привязана ли эта задача к группе студента в таблице group_task
        binding_query = (
            select(GroupTaskModel)
            .where(GroupTaskModel.task_id == task_id)
            .where(GroupTaskModel.group_number == student_group)
        )
        binding_res = await session.execute(binding_query)
        if not binding_res.scalar_one_or_none():
            logger.warning(
                f"SECURITY BREACH: [STUDENT ID: {payload.sub}] пытался открыть "
                f"чужую задачу (ID: {task_id}), не принадлежащую группе '{student_group}'"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="У вас нет доступа к этому заданию. Оно не назначено вашей группе."
            )

    # 3. Получаем информацию о группах, которым назначена задача (опционально)
    groups_query = (
        select(GroupTaskModel.group_number)
        .where(GroupTaskModel.task_id == task_id)
    )
    groups_result = await session.execute(groups_query)
    assigned_groups = [g for g in groups_result.scalars().all()]

    # 4. Формируем JSON-ответ (УБИРАЕМ files, так как их нет!)
    response_data = {
        "id": task.id,
        "title": task.title,
        "description": task.description,
        "deadline": task.deadline,
        "assigned_groups": assigned_groups  # Добавляем информацию о группах
    }

    # Логируем успешное открытие карточки
    logger.info(
        f"ACTION: [{payload.role.upper()} ID: {payload.sub}] открыл карточку "
        f"задания (ID: {task_id}) '{task.title}'"
    )

    return {"ok": True, "task": response_data}

@app.post("/api/admin/assign-group")
async def assign_group_to_student(
    data: UpdateStudentGroupSchema,
    session: SessionDeb,
    payload: TokenPayload = Depends(allow_admins)  # Строгая проверка: доступ только для админов
):
    # 1. Ищем пользователя в БД по его открытому логину
    query = select(UserModel).where(UserModel.login == data.login)
    result = await session.execute(query)
    user = result.scalar_one_or_none()

    # 2. Если пользователь не найден — отдаем 404
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Пользователь с логином '{data.login}' не найден в системе"
        )

    # 3. Защитная проверка: менять группу можно ТОЛЬКО студентам
    if user.role != "student":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Пользователь '{data.login}' имеет роль '{user.role}'. Группу можно назначать только студентам."
        )

    # Запоминаем старую группу для детального лога
    old_group = user.group_number or "БЕЗ ГРУППЫ"

    # 4. Обновляем номер группы
    user.group_number = data.group_number
    await session.commit()

    # Записываем действие администратора в наш ежедневный профессиональный логгер
    logger.info(
        f"ACTION: [ADMIN ID: {payload.sub}] изменил группу студенту '{data.login}' (ID: {user.id}). "
        f"Старая группа: '{old_group}' -> Новая группа: '{data.group_number}'"
    )

    return {
        "ok": True, 
        "msg": f"Студенту '{data.login}' успешно присвоена группа '{data.group_number}'"
    }

@app.post("/api/admin/change-password")
async def admin_change_user_password(
    data: AdminChangePasswordSchema,
    session: SessionDeb,
    payload: TokenPayload = Depends(allow_admins)  # Строгая проверка: доступ только для админов
):
    # 1. Ищем пользователя в БД по его открытому логину
    query = select(UserModel).where(UserModel.login == data.login)
    result = await session.execute(query)
    user = result.scalar_one_or_none()

    # 2. Если пользователь не найден — возвращаем 404 ошибку
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Пользователь с логином '{data.login}' не найден в системе"
        )

    # 3. Хэшируем новый пароль
    raw_hash = await get_password_hash(data.new_password)
    
    # ПРИВЕДЕНИЕ ТИПОВ ДЛЯ BYTEA: Если на выходе функции строка, переводим её в байты
    byte_password = raw_hash.encode("utf-8") if isinstance(raw_hash, str) else raw_hash

    # 4. Обновляем пароль пользователя
    user.password = byte_password
    await session.commit()

    # Записываем действие администратора в наш ежедневный профессиональный логгер
    logger.info(
        f"ACTION: [ADMIN ID: {payload.sub}] принудительно изменил пароль "
        f"пользователю '{data.login}' ({user.role.upper()} ID: {user.id})"
    )

    return {
        "ok": True, 
        "msg": f"Пароль для пользователя '{data.login}' успешно обновлен"
    }




@app.get("/api/tasks")
async def get_tasks(session: SessionDeb, payload: TokenPayload = Depends(get_current_user_claims)):
    # Запрос всех заданий из базы
    query = select(TaskModel) # Убедитесь, что у вас есть модель TaskModel
    result = await session.execute(query)
    tasks = result.scalars().all()
    
    return [
        {
            "id": t.id, 
            "title": t.title, 
            "description": t.description, 
            "grade": None # Здесь можно добавить логику получения оценки из таблицы решений
        } 
        for t in tasks
    ]

# ========== ДОБАВИТЬ ЭТИ ЭНДПОИНТЫ В db.py ==========

@app.get("/api/groups")
async def get_all_groups(
    session: SessionDeb,
    payload: TokenPayload = Depends(allow_teachers)
):
    """Возвращает все существующие группы из БД"""
    query = select(GroupModel).order_by(GroupModel.group_number)
    result = await session.execute(query)
    groups = result.scalars().all()
    
    return {
        "ok": True,
        "groups": [{"group_number": g.group_number} for g in groups]
    }


@app.get("/api/teacher/groups")
async def get_teacher_groups(
    session: SessionDeb,
    payload: TokenPayload = Depends(allow_teachers)
):
    """Возвращает группы, к которым привязан текущий учитель"""
    teacher_id = int(payload.sub)
    
    query = (
        select(UserModel)
        .where(UserModel.id == teacher_id)
        .options(selectinload(UserModel.managed_groups))
    )
    result = await session.execute(query)
    teacher = result.scalar_one_or_none()
    
    if not teacher:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Учитель не найден"
        )
    
    groups = [{"group_number": g.group_number} for g in teacher.managed_groups]
    
    return {
        "ok": True,
        "groups": groups
    }


@app.get("/api/teacher/tasks")
async def get_teacher_tasks(
    session: SessionDeb,
    payload: TokenPayload = Depends(allow_teachers)
):
    """Возвращает все задания, доступные учителю (по его группам)"""
    teacher_id = int(payload.sub)
    
    # Получаем группы учителя
    teacher_query = (
        select(UserModel)
        .where(UserModel.id == teacher_id)
        .options(selectinload(UserModel.managed_groups))
    )
    teacher_result = await session.execute(teacher_query)
    teacher = teacher_result.scalar_one_or_none()
    
    if not teacher:
        raise HTTPException(status_code=404, detail="Учитель не найден")
    
    teacher_groups = [g.group_number for g in teacher.managed_groups]
    
    if not teacher_groups:
        return {"ok": True, "tasks": []}
    
    # Получаем задания для этих групп
    query = (
        select(TaskModel)
        .join(GroupTaskModel, TaskModel.id == GroupTaskModel.task_id)
        .where(GroupTaskModel.group_number.in_(teacher_groups))
        .distinct()
        .order_by(TaskModel.deadline.asc().nulls_last(), TaskModel.id.desc())
    )
    
    result = await session.execute(query)
    tasks = result.scalars().all()
    
    # Формируем ответ
    formatted_tasks = []
    for task in tasks:
        # Получаем группы для этого задания
        groups_query = select(GroupTaskModel.group_number).where(GroupTaskModel.task_id == task.id)
        groups_result = await session.execute(groups_query)
        task_groups = groups_result.scalars().all()
        
        formatted_tasks.append({
            "id": task.id,
            "title": task.title,
            "description": task.description,
            "deadline": task.deadline,
            "group_numbers": task_groups
        })
    
    logger.info(f"ACTION: Учитель (ID: {teacher_id}) запросил список заданий. Найдено: {len(formatted_tasks)}")
    
    return {"ok": True, "tasks": formatted_tasks}

@app.get("/api/task/{task_id}/solutions")
async def get_task_solutions(
    task_id: int,
    session: SessionDeb,
    payload: TokenPayload = Depends(allow_teachers)
):
    """Возвращает список решений студентов для конкретного задания"""
    
    # Проверяем, имеет ли учитель доступ к этому заданию
    teacher_id = int(payload.sub)
    
    # Получаем группы учителя
    teacher_query = (
        select(UserModel)
        .where(UserModel.id == teacher_id)
        .options(selectinload(UserModel.managed_groups))
    )
    teacher_result = await session.execute(teacher_query)
    teacher = teacher_result.scalar_one_or_none()
    
    if not teacher:
        raise HTTPException(status_code=404, detail="Учитель не найден")
    
    teacher_groups = [g.group_number for g in teacher.managed_groups]
    
    # Проверяем, что задание относится к группам учителя
    task_groups_query = select(GroupTaskModel.group_number).where(GroupTaskModel.task_id == task_id)
    task_groups_result = await session.execute(task_groups_query)
    task_groups = task_groups_result.scalars().all()
    
    if not any(g in teacher_groups for g in task_groups):
        raise HTTPException(status_code=403, detail="У вас нет доступа к этому заданию")
    
    # Получаем все решения для этого задания
    query = (
        select(GradeModel, UserModel)
        .join(UserModel, GradeModel.student_id == UserModel.id)
        .where(GradeModel.task_id == task_id)
        .order_by(GradeModel.grade_value.asc().nulls_first())
    )
    
    result = await session.execute(query)
    rows = result.all()
    
    solutions = []
    for grade, student in rows:
        solutions.append({
            "student_id": student.id,
            "student_name": f"{decrypt_data(student.second_name)} {decrypt_data(student.first_name)}",
            "group_number": student.group_number,
            "grade_value": grade.grade_value,
            "submitted_at": "Дата не сохранена"  # Можно добавить поле created_at в GradeModel
        })
    
    logger.info(f"ACTION: Учитель (ID: {teacher_id}) запросил решения для задачи {task_id}. Найдено: {len(solutions)}")
    
    return {"ok": True, "solutions": solutions}

@app.get("/api/user/{user_id}")
async def get_user_info(
    user_id: int,
    session: SessionDeb,
    payload: TokenPayload = Depends(allow_teachers)
):
    """Возвращает информацию о пользователе (для учителей)"""
    query = select(UserModel).where(UserModel.id == user_id)
    result = await session.execute(query)
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    return {
        "ok": True,
        "user": {
            "id": user.id,
            "login": user.login,
            "first_name": decrypt_data(user.first_name),
            "second_name": decrypt_data(user.second_name),
            "middle_name": decrypt_data(user.middle_name) if user.middle_name else None,
            "group_number": user.group_number,
            "role": user.role
        }
    }

@app.get("/api/solution/{task_id}/student/{student_id}/grade")
async def get_student_grade(
    task_id: int,
    student_id: int,
    session: SessionDeb,
    payload: TokenPayload = Depends(allow_teachers)
):
    """Получает оценку студента за задание"""
    grade_entry = await session.get(GradeModel, (student_id, task_id))
    
    if not grade_entry:
        return {"grade_value": None}
    
    return {"grade_value": grade_entry.grade_value}

@app.delete("/api/admin/user") 
async def delete_user_by_login(
    login: str, # Принимаем логин как Query-параметр прямо из URL
    session: SessionDeb,
    payload: TokenPayload = Depends(allow_admins)
):
    # 1. Ищем пользователя в БД
    from sqlalchemy import select
    query = select(UserModel).where(UserModel.login == login)
    result = await session.execute(query)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Пользователь с логином '{login}' не найден в системе"
        )

    # 2. Защита от удаления самого себя
    if str(user.id) == payload.sub:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Вы не можете удалить свой собственный аккаунт администратора!"
        )

    # Запоминаем данные для логов и удаления файлов
    user_id = user.id
    user_role = user.role
    group_number = user.group_number

    # 3. Удаляем пользователя из базы данных (Каскад очистит таблицы оценок)
    await session.delete(user)
    await session.commit()

    # 4. УДАЛЕНИЕ ФАЙЛОВ С ДИСКА (только если это был студент)
    if user_role == "student" and group_number:
        # Строим путь к персональной папке студента: upload/{group_number}/{student_id}
        student_dir = os.path.join(BASE_UPLOAD_DIR, str(group_number), str(user_id))
        
        # Проверяем, существует ли папка физически на диске
        if os.path.exists(student_dir):
            try:
                # Безвозвратно удаляем папку вместе со всеми подпапками задач и файлами внутри
                shutil.rmtree(student_dir)
                logger.info(f"FILES OBLITERATED: Папка с решениями студента '{login}' успешно удалена с диска: {student_dir}")
            except Exception as e:
                # Если папка занята процессом или заблокирована, пишем ошибку в лог, но клиенту отдаем 200 (так как из БД юзер уже удален)
                logger.error(f"FILE SYSTEM ERROR: Не удалось удалить папку {student_dir}. Ошибка: {str(e)}")

    # Записываем действие администратора в наш ежедневный логгер
    logger.info(
        f"ACTION: [ADMIN ID: {payload.sub}] безвозвратно удалил пользователя '{login}' "
        f"({user_role.upper()} ID: {user_id})"
    )

    return {
        "ok": True,
        "msg": f"Пользователь '{login}' успешно удален из БД, его файлы и оценки стерты"
    }

@app.get("/api/check-role/admin")
async def check_admin_role(
    payload: TokenPayload = Depends(get_current_user_claims)
):
    """Проверка что пользователь админ (для Nginx auth_request)"""
    if payload.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return {"ok": True, "role": "admin"}
