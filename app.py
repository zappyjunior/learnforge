import threading
from flask import Flask, render_template, request, redirect, url_for, jsonify
from db import init_db, create_course, create_pending_course, finalize_course, get_course, get_all_courses, update_progress, update_course_status, delete_course
from ai import generate_course, grade_short_answer, chat_with_tutor

app = Flask(__name__)


@app.route("/")
def index():
    courses = get_all_courses()
    return render_template("index.html", courses=courses)


def _generate_course_background(course_id, topic, difficulty="intermediate"):
    try:
        print(f"[BG] Starting generation for course {course_id}: {topic} ({difficulty})", flush=True)
        course_data = generate_course(topic, difficulty)
        finalize_course(
            course_id,
            title=course_data["title"],
            description=course_data.get("description", ""),
            structure=course_data
        )
        print(f"[BG] Course {course_id} ready: {course_data['title']}", flush=True)
    except Exception as e:
        print(f"[BG] Course {course_id} FAILED: {e}", flush=True)
        update_course_status(course_id, "error")


@app.route("/generate", methods=["POST"])
def generate():
    data = request.get_json()
    topic = (data.get("topic") or "").strip() if data else ""
    difficulty = (data.get("difficulty") or "intermediate").strip() if data else "intermediate"
    if not topic:
        return jsonify({"error": "Topic is required"}), 400

    course_id = create_pending_course(topic)
    thread = threading.Thread(
        target=_generate_course_background,
        args=(course_id, topic, difficulty)
    )
    thread.daemon = True
    thread.start()
    return jsonify({"course_id": course_id})


@app.route("/course/<int:course_id>/delete", methods=["POST"])
def delete_course_route(course_id):
    course = get_course(course_id)
    if course is None:
        return jsonify({"error": "Not found"}), 404
    delete_course(course_id)
    return jsonify({"ok": True})


@app.route("/course/<int:course_id>/status")
def course_status(course_id):
    course = get_course(course_id)
    if course is None:
        return jsonify({"status": "error"}), 404
    if course["status"] == "generating":
        return jsonify({"status": "generating"})
    elif course["status"] == "error":
        return jsonify({"status": "error"})
    else:
        return jsonify({"status": "ready", "title": course.get("title", "")})


@app.route("/course/<int:course_id>")
def course(course_id):
    course = get_course(course_id)
    if course is None:
        return redirect(url_for("index"))
    if course["status"] == "generating":
        return redirect(url_for("index"))
    return render_template("course.html", course=course)


@app.route("/course/<int:course_id>/lesson/<int:lesson_index>")
def lesson(course_id, lesson_index):
    course = get_course(course_id)
    if course is None:
        return redirect(url_for("index"))

    lessons = course["structure"]["lessons"]
    if lesson_index < 0 or lesson_index >= len(lessons):
        return redirect(url_for("course", course_id=course_id))

    return render_template("course.html", course=course, active_lesson=lesson_index)


@app.route("/course/<int:course_id>/chat", methods=["POST"])
def course_chat(course_id):
    course = get_course(course_id)
    if course is None:
        return jsonify({"error": "Course not found"}), 404

    data = request.get_json()
    lesson_index = data.get("lesson_index")
    message = (data.get("message") or "").strip()
    history = data.get("history", [])

    if not message:
        return jsonify({"error": "Message is required"}), 400

    lessons = course["structure"].get("lessons", [])
    if lesson_index is None or lesson_index < 0 or lesson_index >= len(lessons):
        return jsonify({"error": "Invalid lesson index"}), 400

    lesson = lessons[lesson_index]
    messages = history + [{"role": "user", "content": message}]

    try:
        reply = chat_with_tutor(
            course_topic=course["topic"],
            lesson_title=lesson["title"],
            lesson_content=lesson["content"],
            messages=messages
        )
        return jsonify({"reply": reply})
    except Exception as e:
        return jsonify({"error": "Failed to get response"}), 500


@app.route("/course/<int:course_id>/submit_quiz", methods=["POST"])
def submit_quiz(course_id):
    course = get_course(course_id)
    if course is None:
        return jsonify({"error": "Course not found"}), 404

    data = request.get_json()
    lesson_index = data.get("lesson_index")
    answers = data.get("answers", {})

    lessons = course["structure"]["lessons"]
    if lesson_index is None or lesson_index < 0 or lesson_index >= len(lessons):
        return jsonify({"error": "Invalid lesson index"}), 400

    quiz = lessons[lesson_index]["quiz"]
    results = []
    correct_count = 0

    for i, question in enumerate(quiz):
        user_answer = answers.get(str(i), "")
        if question["type"] == "multiple_choice":
            is_correct = user_answer == question["correct_answer"]
            results.append({
                "question": question["question"],
                "type": "multiple_choice",
                "user_answer": user_answer,
                "correct_answer": question["correct_answer"],
                "correct": is_correct,
                "explanation": question["explanation"],
                "feedback": "Correct!" if is_correct else f"Incorrect. {question['explanation']}"
            })
            if is_correct:
                correct_count += 1
        else:
            grading = grade_short_answer(question["question"], question["expected_answer"], user_answer)
            is_correct = grading["score"] == 1
            results.append({
                "question": question["question"],
                "type": "short_answer",
                "user_answer": user_answer,
                "correct_answer": question["expected_answer"],
                "correct": is_correct,
                "explanation": question["explanation"],
                "feedback": grading["feedback"]
            })
            if is_correct:
                correct_count += 1

    total = len(quiz)
    score = correct_count / total if total > 0 else 0
    passed = score >= 0.75

    progress = course["progress"]
    progress["lesson_scores"][str(lesson_index)] = {
        "score": score,
        "correct": correct_count,
        "total": total,
        "passed": passed
    }

    if passed and lesson_index >= progress.get("current_lesson", 0):
        progress["current_lesson"] = lesson_index + 1

    update_progress(course_id, progress)

    return jsonify({
        "results": results,
        "score": score,
        "correct": correct_count,
        "total": total,
        "passed": passed,
        "next_lesson": lesson_index + 1 if passed else None
    })


@app.route("/course/<int:course_id>/final_exam")
def final_exam(course_id):
    course = get_course(course_id)
    if course is None:
        return redirect(url_for("index"))
    return render_template("course.html", course=course, show_final_exam=True)


@app.route("/course/<int:course_id>/submit_final", methods=["POST"])
def submit_final(course_id):
    course = get_course(course_id)
    if course is None:
        return jsonify({"error": "Course not found"}), 404

    data = request.get_json()
    answers = data.get("answers", {})
    exam = course["structure"]["final_exam"]

    results = []
    correct_count = 0

    for i, question in enumerate(exam):
        user_answer = answers.get(str(i), "")
        if question["type"] == "multiple_choice":
            is_correct = user_answer == question["correct_answer"]
            results.append({
                "question": question["question"],
                "type": "multiple_choice",
                "user_answer": user_answer,
                "correct_answer": question["correct_answer"],
                "correct": is_correct,
                "explanation": question["explanation"],
                "feedback": "Correct!" if is_correct else f"Incorrect. {question['explanation']}"
            })
            if is_correct:
                correct_count += 1
        else:
            grading = grade_short_answer(question["question"], question.get("expected_answer", ""), user_answer)
            is_correct = grading["score"] == 1
            results.append({
                "question": question["question"],
                "type": "short_answer",
                "user_answer": user_answer,
                "correct_answer": question.get("expected_answer", ""),
                "correct": is_correct,
                "explanation": question["explanation"],
                "feedback": grading["feedback"]
            })
            if is_correct:
                correct_count += 1

    total = len(exam)
    score = correct_count / total if total > 0 else 0
    passed = score >= 0.80

    progress = course["progress"]
    progress["final_exam_score"] = {
        "score": score,
        "correct": correct_count,
        "total": total,
        "passed": passed
    }
    progress["completed"] = passed
    update_progress(course_id, progress)

    if passed:
        update_course_status(course_id, "completed")

    return jsonify({
        "results": results,
        "score": score,
        "correct": correct_count,
        "total": total,
        "passed": passed
    })


@app.route("/course/<int:course_id>/results")
def results(course_id):
    course = get_course(course_id)
    if course is None:
        return redirect(url_for("index"))
    return render_template("results.html", course=course)


init_db()

if __name__ == "__main__":
    app.run(debug=True, port=5000)
