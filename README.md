# Students Database CRUD API

Python backend for managing student records using **FastAPI** and **SQLite**.
Includes an optional **Ollama** endpoint (`POST /ask`) for natural-language questions.

## Prerequisites
- Python 3.10+
- (Optional, for `/ask`) [Ollama](https://ollama.com) with `ollama pull llama3.2:1b`

## Installation
```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Run
```bash
python seed.py                   # optional: add dummy data
uvicorn main:app --reload
```
Open interactive docs: http://127.0.0.1:8000/docs

## Endpoints
| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/students` | Create a student |
| GET | `/students` | List / filter (`name`, `course`, `born_after`, `born_before`, `limit`, `offset`) |
| GET | `/students/{id}` | View a student |
| PUT | `/students/{id}` | Replace all details |
| PATCH | `/students/{id}` | Update some fields |
| DELETE | `/students/{id}` | Delete a student |
| POST | `/ask` | (Bonus) Ask AI about the data |

## Test with curl
```bash
# Create
curl -X POST http://127.0.0.1:8000/students -H "Content-Type: application/json" \
  -d '{"name":"Test User","date_of_birth":"2004-05-10","email":"test@example.com","course":"Python"}'

# List / filter
curl "http://127.0.0.1:8000/students?course=Python&born_after=2004-01-01"

# View one
curl http://127.0.0.1:8000/students/1

# Update (partial)
curl -X PATCH http://127.0.0.1:8000/students/1 -H "Content-Type: application/json" \
  -d '{"course":"Data Science"}'

# Delete
curl -X DELETE http://127.0.0.1:8000/students/1

# Bonus: AI question (Ollama must be running)
curl -X POST http://127.0.0.1:8000/ask -H "Content-Type: application/json" \
  -d '{"question":"How many students are there?"}'
```

## Validation and errors
- `422` invalid input (bad email/phone, future DOB, missing name, no email *and* no phone)
- `404` student not found
- `409` duplicate email

## Design notes
- Parameterized SQL everywhere (no SQL injection).
- `/ask`: the backend fetches records and gives them to the model as context. The model never runs SQL.
- Only dummy data is used. `students.db` is git-ignored.
