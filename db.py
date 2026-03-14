import sqlite3
import json
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "learnforge.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS courses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            structure TEXT NOT NULL,
            progress TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'in_progress',
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def create_course(topic, title, description, structure):
    conn = get_db()
    progress = json.dumps({
        "current_lesson": 0,
        "lesson_scores": {},
        "final_exam_score": None,
        "completed": False
    })
    cursor = conn.execute(
        "INSERT INTO courses (topic, title, description, structure, progress, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (topic, title, description, json.dumps(structure), progress, "in_progress", datetime.now().isoformat())
    )
    course_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return course_id


def create_pending_course(topic):
    conn = get_db()
    progress = json.dumps({
        "current_lesson": 0,
        "lesson_scores": {},
        "final_exam_score": None,
        "completed": False
    })
    cursor = conn.execute(
        "INSERT INTO courses (topic, title, description, structure, progress, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (topic, "", "", "{}", progress, "generating", datetime.now().isoformat())
    )
    course_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return course_id


def finalize_course(course_id, title, description, structure):
    conn = get_db()
    conn.execute(
        "UPDATE courses SET title = ?, description = ?, structure = ?, status = ? WHERE id = ?",
        (title, description, json.dumps(structure), "in_progress", course_id)
    )
    conn.commit()
    conn.close()


def get_all_courses():
    conn = get_db()
    rows = conn.execute(
        "SELECT id, topic, title, description, status, progress, created_at FROM courses ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    courses = []
    for row in rows:
        course = dict(row)
        course["progress"] = json.loads(course["progress"])
        courses.append(course)
    return courses


def get_course(course_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM courses WHERE id = ?", (course_id,)).fetchone()
    conn.close()
    if row is None:
        return None
    course = dict(row)
    course["structure"] = json.loads(course["structure"])
    course["progress"] = json.loads(course["progress"])
    return course


def update_progress(course_id, progress):
    conn = get_db()
    conn.execute(
        "UPDATE courses SET progress = ? WHERE id = ?",
        (json.dumps(progress), course_id)
    )
    conn.commit()
    conn.close()


def delete_course(course_id):
    conn = get_db()
    conn.execute("DELETE FROM courses WHERE id = ?", (course_id,))
    conn.commit()
    conn.close()


def update_course_status(course_id, status):
    conn = get_db()
    conn.execute(
        "UPDATE courses SET status = ? WHERE id = ?",
        (status, course_id)
    )
    conn.commit()
    conn.close()
