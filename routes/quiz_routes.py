"""Quiz Blueprint for Study Quest; relies on Admin 2's shared models/database."""
from __future__ import annotations

import secrets

from flask import Blueprint, flash, jsonify, redirect, render_template, request, session, url_for

from models.database import get_db
from models.profile_model import add_exp
from models.quiz_model import (
    list_subjects,
    list_topics,
    random_questions,
    save_attempt,
    user_history,
)

quiz_bp = Blueprint("quiz", __name__, url_prefix="/quiz")

_QUIZ_SESSION_KEY = "admin4_active_quiz"
_ALLOWED_ANSWERS = {"A", "B", "C", "D"}
_MAX_QUESTIONS = 10


@quiz_bp.before_request
def require_login():
    """Enforce the existing app session contract without replacing its decorators."""
    if session.get("user_id") is None:
        flash("Em hãy đăng nhập để làm Quiz nhé.", "warning")
        return redirect(url_for("login", next=request.path))
    return None


def _fetch_questions(question_ids):
    """Fetch only the server-stored question IDs via the shared DB connection."""
    if not isinstance(question_ids, list) or not question_ids:
        return []
    ids = []
    for value in question_ids[:_MAX_QUESTIONS]:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            continue
        if parsed > 0 and parsed not in ids:
            ids.append(parsed)
    if not ids:
        return []
    placeholders = ",".join("?" for _ in ids)
    return get_db().execute(
        f"SELECT id, subject, topic, question_text, option_a, option_b, option_c, option_d, "
        f"correct_answer, explanation FROM questions WHERE id IN ({placeholders})",
        ids,
    ).fetchall()


def _public_question(row):
    """Question shape for the play page; deliberately excludes answer/explanation."""
    return {
        "id": row["id"],
        "question_text": row["question_text"],
        "option_a": row["option_a"],
        "option_b": row["option_b"],
        "option_c": row["option_c"],
        "option_d": row["option_d"],
    }


@quiz_bp.get("")
def index():
    subjects = list_subjects()
    selected_subject = request.args.get("subject", "").strip()
    if selected_subject not in subjects:
        selected_subject = ""
    selected_topic = request.args.get("topic", "").strip()
    if selected_topic and (
        not selected_subject or selected_topic not in list_topics(selected_subject)
    ):
        selected_topic = ""
    return render_template(
        "quiz/index.html",
        subjects=subjects,
        selected_subject=selected_subject,
        selected_topic=selected_topic,
    )


@quiz_bp.get("/topics")
def topics_for_subject():
    subject = request.args.get("subject", "").strip()
    if not subject or subject not in list_subjects():
        return jsonify({"topics": []})
    return jsonify({"topics": list_topics(subject)})


@quiz_bp.post("/start")
def start():
    subject = request.form.get("subject", "").strip()
    topic = request.form.get("topic", "").strip()
    if subject not in list_subjects():
        flash("Em hãy chọn môn học hợp lệ.", "warning")
        return redirect(url_for("quiz.index"))
    available_topics = list_topics(subject)
    if topic and topic not in available_topics:
        flash("Chủ đề không thuộc môn học đã chọn.", "warning")
        return redirect(url_for("quiz.index"))
    try:
        quantity = int(request.form.get("quantity", "5"))
    except (TypeError, ValueError):
        quantity = 5
    quantity = min(max(quantity, 1), _MAX_QUESTIONS)

    # Admin 2's model caps quantity at 10; server state stores the selected IDs.
    rows = random_questions(subject, topic or None, quantity)
    if not rows:
        flash("Chưa có câu hỏi phù hợp với lựa chọn này.", "warning")
        return redirect(url_for("quiz.index"))
    question_ids = [int(row["id"]) for row in rows]
    session[_QUIZ_SESSION_KEY] = {
        "ids": question_ids,
        "subject": subject,
        "topic": topic,
        "token": secrets.token_urlsafe(24),
    }
    return redirect(url_for("quiz.play"))


@quiz_bp.get("/play")
def play():
    state = session.get(_QUIZ_SESSION_KEY)
    if not isinstance(state, dict) or not state.get("ids"):
        flash("Hãy chọn môn học và bắt đầu một Quiz trước nhé.", "warning")
        return redirect(url_for("quiz.index"))
    rows = _fetch_questions(state.get("ids"))
    if not rows:
        session.pop(_QUIZ_SESSION_KEY, None)
        flash("Không tìm thấy câu hỏi của lượt Quiz này. Em hãy thử lại.", "warning")
        return redirect(url_for("quiz.index"))
    by_id = {int(row["id"]): row for row in rows}
    ordered = [by_id[qid] for qid in state["ids"] if qid in by_id]
    return render_template(
        "quiz/play.html",
        questions=[_public_question(row) for row in ordered],
        subject=state.get("subject", ""),
        topic=state.get("topic", ""),
        submit_token=state.get("token", ""),
    )


@quiz_bp.post("/submit")
def submit():
    state = session.get(_QUIZ_SESSION_KEY)
    if not isinstance(state, dict) or not state.get("ids"):
        flash("Lượt Quiz không còn hiệu lực. Em hãy bắt đầu lại nhé.", "warning")
        return redirect(url_for("quiz.index"))
    submitted_token = request.form.get("submit_token", "")
    if not secrets.compare_digest(str(state.get("token", "")), submitted_token):
        flash("Lượt Quiz không hợp lệ. Em hãy bắt đầu lại nhé.", "warning")
        return redirect(url_for("quiz.index"))

    rows = _fetch_questions(state.get("ids"))
    by_id = {int(row["id"]): row for row in rows}
    ordered = [by_id[qid] for qid in state["ids"] if qid in by_id]
    if not ordered:
        session.pop(_QUIZ_SESSION_KEY, None)
        flash("Không thể chấm lượt Quiz này. Em hãy thử lại.", "warning")
        return redirect(url_for("quiz.index"))

    # The client submits only chosen letters. Correct answers come exclusively from DB.
    results = []
    correct = 0
    for row in ordered:
        qid = int(row["id"])
        selected = request.form.get(f"answer_{qid}", "").strip().upper()
        if selected not in _ALLOWED_ANSWERS:
            selected = ""
        answer = str(row["correct_answer"]).upper()
        is_correct = selected == answer
        correct += int(is_correct)
        results.append({
            "id": qid,
            "question_text": row["question_text"],
            "option_a": row["option_a"],
            "option_b": row["option_b"],
            "option_c": row["option_c"],
            "option_d": row["option_d"],
            "selected_answer": selected,
            "correct_answer": answer,
            "is_correct": is_correct,
            "explanation": row["explanation"] or "",
        })

    total = len(ordered)
    score = round(correct * 10 / total, 1) if total else 0.0
    exp_earned = correct * 10 + (20 if total and correct / total >= 0.8 else 0)
    user_id = session.get("user_id")
    subject = str(state.get("subject", ""))
    topic = str(state.get("topic", ""))
    attempt_id = save_attempt(user_id, subject, topic, total, correct, score, exp_earned)
    if exp_earned:
        add_exp(user_id, exp_earned)
    session.pop(_QUIZ_SESSION_KEY, None)

    return render_template(
        "quiz/result.html",
        subject=subject,
        topic=topic,
        total=total,
        correct=correct,
        score=score,
        exp_earned=exp_earned,
        results=results,
        attempt_id=attempt_id,
    )


@quiz_bp.get("/history")
def history():
    # Always scope history by the authenticated session user; never accept user_id from URL/form.
    attempts = user_history(session.get("user_id"), limit=50)
    return render_template("quiz/history.html", attempts=attempts)


@quiz_bp.get("/cancel")
def cancel():
    session.pop(_QUIZ_SESSION_KEY, None)
    return redirect(url_for("quiz.index"))
