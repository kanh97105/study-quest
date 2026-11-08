"""Smart Exam Planner routes for Study Quest.

This module deliberately delegates persistence and plan generation to Admin 2's
exam model. It does not open SQLite connections or define database tables.
"""
from datetime import date, datetime
from functools import wraps

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from models.database import get_db
from models.exam_model import (
    create_exam,
    add_topics,
    get_user_exams,
    get_exam,
    get_topics,
    get_plan,
    calculate_progress,
)
from models.profile_model import add_exp, unlock_achievement


exam_bp = Blueprint("exam", __name__, url_prefix="/planner")


# ---------------------------------------------------------------------------
# Small, read-only helpers. They normalize dict/row/object model results
# without replacing any Admin 2 backend behavior.
# ---------------------------------------------------------------------------
def _value(record, *keys, default=None):
    if record is None:
        return default
    for key in keys:
        if isinstance(record, dict) and key in record:
            return record[key]
        try:
            value = record[key]
            if value is not None:
                return value
        except (KeyError, IndexError, TypeError):
            pass
        value = getattr(record, key, None)
        if value is not None:
            return value
    return default


def _user_id():
    user = session.get("user")
    nested_id = user.get("id") if isinstance(user, dict) else None
    return session.get("user_id") or nested_id


def _logged_in(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if _user_id() is None:
            flash("Vui lòng đăng nhập để sử dụng Smart Exam Planner.", "error")
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapped


def _owned_exam(exam_id):
    """Return the exam only when it belongs to the current user."""
    try:
        exam_id = int(exam_id)
    except (TypeError, ValueError):
        return None

    exam = get_exam(exam_id, _user_id())
    if not exam:
        return None

    owner = _value(exam, "user_id", "owner_id", "created_by")
    if owner is not None and str(owner) != str(_user_id()):
        return None

    return exam


def _parse_form():
    subject = request.form.get("subject", "").strip()
    exam_date = request.form.get("exam_date", "").strip()
    topics_raw = request.form.get("topics", "")

    try:
        current_score = float(request.form.get("current_score", ""))
        target_score = float(request.form.get("target_score", ""))
        daily_minutes = int(request.form.get("daily_minutes", ""))
    except (TypeError, ValueError):
        raise ValueError("Điểm số phải là số và thời gian học phải là số nguyên.")

    try:
        parsed_exam_date = datetime.strptime(exam_date, "%Y-%m-%d").date()
    except ValueError:
        raise ValueError("Ngày thi không hợp lệ.")

    if not subject or len(subject) > 160:
        raise ValueError("Vui lòng nhập môn thi hợp lệ.")
    if parsed_exam_date < date.today():
        raise ValueError("Ngày thi phải từ hôm nay trở đi.")
    if not (0 <= current_score <= 10 and 0 <= target_score <= 10):
        raise ValueError("Điểm hiện tại và điểm mục tiêu phải từ 0 đến 10.")
    if not (10 <= daily_minutes <= 1440):
        raise ValueError("Thời gian học mỗi ngày phải từ 10 đến 1440 phút.")

    topics = [topic.strip() for topic in topics_raw.splitlines() if topic.strip()]
    topics = list(dict.fromkeys(topics))
    if not topics or len(topics) > 100:
        raise ValueError("Hãy nhập từ 1 đến 100 chủ đề, mỗi dòng một chủ đề.")
    if any(len(topic) > 200 for topic in topics):
        raise ValueError("Tên chủ đề không được dài quá 200 ký tự.")

    return subject, exam_date, current_score, target_score, daily_minutes, topics


def _progress(exam_id):
    # Never accept a progress value from the browser.
    value = calculate_progress(exam_id, _user_id())
    if isinstance(value, dict):
        value = value.get("percent", value.get("progress", 0))
    try:
        return max(0, min(100, round(float(value))))
    except (TypeError, ValueError):
        return 0


@exam_bp.route("", methods=["GET"])
@_logged_in
def planner_index():
    """List only the current user's exams."""
    exams = get_user_exams(_user_id()) or []
    cards = [{"exam": exam, "progress": _progress(_value(exam, "id", "exam_id"))} for exam in exams]
    return render_template("exam/index.html", exams=cards)


@exam_bp.route("/new", methods=["GET", "POST"])
@_logged_in
def planner_new():
    if request.method == "GET":
        return render_template("exam/new.html", today=date.today().isoformat())

    try:
        subject, exam_date, current_score, target_score, daily_minutes, topics = _parse_form()
        exam_id = create_exam(
            _user_id(), subject, exam_date, current_score, target_score, daily_minutes
        )
        exam_id = _value(exam_id, "id", "exam_id", default=exam_id)
        # Admin 2 owns plan generation; add_topics must be called after exam creation.
        add_topics(exam_id, topics)
        # Admin 2 currently exposes plan generation from app.py, not exam_model.py.
        # Import lazily to avoid an app/blueprint circular import at startup.
        from app import generate_plan

        generate_plan(exam_id, exam_date, daily_minutes, topics)
    except (ValueError, TypeError) as exc:
        flash(str(exc), "error")
        return render_template("exam/new.html", today=date.today().isoformat()), 400

    flash("Đã tạo kế hoạch ôn thi.", "success")
    return redirect(url_for("exam.planner_detail", exam_id=exam_id))


@exam_bp.route("/<int:exam_id>", methods=["GET"])
@_logged_in
def planner_detail(exam_id):
    exam = _owned_exam(exam_id)
    if not exam:
        flash("Không tìm thấy kỳ thi hoặc bạn không có quyền truy cập.", "error")
        return redirect(url_for("exam.planner_index")), 404

    return render_template(
        "exam/detail.html",
        exam=exam,
        topics=get_topics(exam_id) or [],
        plan=get_plan(exam_id, _user_id()) or [],
        progress=_progress(exam_id),
    )


@exam_bp.route("/<int:exam_id>/plan/<int:plan_id>/toggle", methods=["POST"])
@_logged_in
def planner_toggle(exam_id, plan_id):
    if not _owned_exam(exam_id):
        flash("Không tìm thấy kỳ thi hoặc bạn không có quyền truy cập.", "error")
        return redirect(url_for("exam.planner_index")), 404

    plan_items = get_plan(exam_id, _user_id()) or []
    valid_ids = {str(_value(item, "id", "plan_id")) for item in plan_items}
    if str(plan_id) not in valid_ids:
        flash("Nhiệm vụ không hợp lệ.", "error")
        return redirect(url_for("exam.planner_detail", exam_id=exam_id)), 400

    target_plan = next(
        item for item in plan_items if str(_value(item, "id", "plan_id")) == str(plan_id)
    )
    was_completed = bool(_value(target_plan, "completed", default=0))
    completed_before = get_db().execute(
        "SELECT COUNT(*) FROM study_plans sp "
        "JOIN exams e ON e.id = sp.exam_id "
        "WHERE e.user_id = ? AND sp.completed = 1",
        (_user_id(),),
    ).fetchone()[0]

    if was_completed:
        flash("Nhiệm vụ này đã hoàn thành rồi.", "success")
        return redirect(url_for("exam.planner_detail", exam_id=exam_id))

    db = get_db()
    result = db.execute(
        "UPDATE study_plans SET completed = 1 "
        "WHERE id = ? AND exam_id = ? AND completed = 0 "
        "AND EXISTS (SELECT 1 FROM exams WHERE exams.id = study_plans.exam_id "
        "AND exams.user_id = ?)",
        (plan_id, exam_id, _user_id()),
    )
    db.commit()
    newly_completed = result.rowcount == 1
    achievement_unlocked = newly_completed and completed_before == 0
    if newly_completed:
        add_exp(_user_id(), 20)
    if not newly_completed:
        flash("Nhiệm vụ này đã hoàn thành rồi.", "success")
        return redirect(url_for("exam.planner_detail", exam_id=exam_id))

    if achievement_unlocked:
        unlock_achievement(
            _user_id(),
            "Task Planner đầu tiên",
            "Hoàn thành task Planner đầu tiên của bạn.",
        )
        flash("Thành tựu mới: Task Planner đầu tiên! +20 EXP", "achievement")
    else:
        flash("Đã cập nhật trạng thái nhiệm vụ.", "success")
    # Progress is recomputed on the next GET; the browser cannot supply it.
    return redirect(url_for("exam.planner_detail", exam_id=exam_id))
