"""Students Database CRUD API - FastAPI + SQLite (+ optional Ollama /ask)."""
import json
import re
import sqlite3
import urllib.error
import urllib.request
from contextlib import asynccontextmanager, closing
from datetime import date
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, Response, status
from pydantic import BaseModel, Field, field_validator, model_validator

DB_PATH = "students.db"
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3.2:1b"

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_RE = re.compile(r"^\+?[0-9\- ]{7,15}$")


# ---------- Database ----------
def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with closing(get_conn()) as conn, conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS students (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                name            TEXT NOT NULL,
                date_of_birth   TEXT NOT NULL,
                email           TEXT UNIQUE,
                phone           TEXT,
                course          TEXT,
                address         TEXT,
                enrollment_date TEXT
            )
            """
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Students CRUD API", version="1.0.0", lifespan=lifespan)


# ---------- Schemas ----------
class StudentBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    date_of_birth: date
    email: Optional[str] = None
    phone: Optional[str] = None
    course: Optional[str] = Field(None, max_length=100)
    address: Optional[str] = Field(None, max_length=255)
    enrollment_date: Optional[date] = None

    @field_validator("email")
    @classmethod
    def check_email(cls, v):
        if v is not None and not EMAIL_RE.match(v):
            raise ValueError("invalid email format")
        return v.lower() if v else v

    @field_validator("phone")
    @classmethod
    def check_phone(cls, v):
        if v is not None and not PHONE_RE.match(v):
            raise ValueError("invalid phone number")
        return v

    @field_validator("date_of_birth")
    @classmethod
    def check_dob(cls, v):
        if v >= date.today():
            raise ValueError("date_of_birth must be in the past")
        return v


class StudentCreate(StudentBase):
    @model_validator(mode="after")
    def need_contact(self):
        if not self.email and not self.phone:
            raise ValueError("provide at least one of email or phone")
        return self


class StudentUpdate(StudentBase):
    """All fields optional (used for PATCH)."""

    name: Optional[str] = Field(None, min_length=2, max_length=100)
    date_of_birth: Optional[date] = None


class StudentOut(BaseModel):
    id: int
    name: str
    date_of_birth: date
    email: Optional[str]
    phone: Optional[str]
    course: Optional[str]
    address: Optional[str]
    enrollment_date: Optional[date]


# ---------- Helpers ----------
def row_to_dict(row: sqlite3.Row) -> dict:
    return dict(row)


def fetch_or_404(conn: sqlite3.Connection, student_id: int) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM students WHERE id = ?", (student_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Student {student_id} not found")
    return row


def to_db(data: dict) -> dict:
    return {k: (v.isoformat() if isinstance(v, date) else v) for k, v in data.items()}


# ---------- CRUD endpoints ----------
@app.post("/students", response_model=StudentOut, status_code=status.HTTP_201_CREATED)
def create_student(student: StudentCreate):
    data = to_db(student.model_dump())
    try:
        with closing(get_conn()) as conn, conn:
            cur = conn.execute(
                """INSERT INTO students
                   (name, date_of_birth, email, phone, course, address, enrollment_date)
                   VALUES (:name, :date_of_birth, :email, :phone, :course, :address, :enrollment_date)""",
                data,
            )
            return row_to_dict(fetch_or_404(conn, cur.lastrowid))
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="A student with this email already exists")


@app.get("/students", response_model=list[StudentOut])
def list_students(
    name: Optional[str] = Query(None, description="Name contains (case-insensitive)"),
    course: Optional[str] = Query(None, description="Exact course name"),
    born_after: Optional[date] = Query(None, description="DOB after this date"),
    born_before: Optional[date] = Query(None, description="DOB before this date"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    sql, params = "SELECT * FROM students WHERE 1=1", []
    if name:
        sql += " AND LOWER(name) LIKE ?"
        params.append(f"%{name.lower()}%")
    if course:
        sql += " AND course = ?"
        params.append(course)
    if born_after:
        sql += " AND date_of_birth > ?"
        params.append(born_after.isoformat())
    if born_before:
        sql += " AND date_of_birth < ?"
        params.append(born_before.isoformat())
    sql += " ORDER BY id LIMIT ? OFFSET ?"
    params += [limit, offset]
    with closing(get_conn()) as conn:
        return [row_to_dict(r) for r in conn.execute(sql, params).fetchall()]


@app.get("/students/{student_id}", response_model=StudentOut)
def get_student(student_id: int):
    with closing(get_conn()) as conn:
        return row_to_dict(fetch_or_404(conn, student_id))


@app.put("/students/{student_id}", response_model=StudentOut)
def replace_student(student_id: int, student: StudentCreate):
    return _update(student_id, to_db(student.model_dump()))


@app.patch("/students/{student_id}", response_model=StudentOut)
def patch_student(student_id: int, student: StudentUpdate):
    changes = to_db(student.model_dump(exclude_unset=True))
    if not changes:
        raise HTTPException(status_code=400, detail="No fields provided to update")
    return _update(student_id, changes)


def _update(student_id: int, changes: dict):
    cols = ", ".join(f"{k} = :{k}" for k in changes)  # keys come from our own schema
    try:
        with closing(get_conn()) as conn, conn:
            fetch_or_404(conn, student_id)
            conn.execute(f"UPDATE students SET {cols} WHERE id = :_id", {**changes, "_id": student_id})
            return row_to_dict(fetch_or_404(conn, student_id))
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="A student with this email already exists")


@app.delete("/students/{student_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_student(student_id: int):
    with closing(get_conn()) as conn, conn:
        fetch_or_404(conn, student_id)
        conn.execute("DELETE FROM students WHERE id = ?", (student_id,))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------- Optional bonus: local AI with Ollama ----------
class Question(BaseModel):
    question: str = Field(..., min_length=3, max_length=300)


@app.post("/ask")
def ask(q: Question):
    """The model never touches SQL. Backend fetches records and passes them as context."""
    with closing(get_conn()) as conn:
        rows = [row_to_dict(r) for r in conn.execute("SELECT * FROM students ORDER BY id LIMIT 200")]
        total = conn.execute("SELECT COUNT(*) FROM students").fetchone()[0]

    context = "\n".join(
        f"id={r['id']}; name={r['name']}; dob={r['date_of_birth']}; course={r['course']}" for r in rows
    )
    prompt = (
        "You answer questions about a students database. Use ONLY the data below. "
        "If the answer is not in the data, say you don't know.\n\n"
        f"Total students: {total}\nRecords:\n{context}\n\nQuestion: {q.question}\nAnswer:"
    )
    body = json.dumps({"model": OLLAMA_MODEL, "prompt": prompt, "stream": False}).encode()
    req = urllib.request.Request(OLLAMA_URL, data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            answer = json.loads(resp.read())["response"].strip()
    except (urllib.error.URLError, TimeoutError):
        raise HTTPException(status_code=503, detail="Ollama is not running. Start it with: ollama serve")
    return {"question": q.question, "answer": answer}
