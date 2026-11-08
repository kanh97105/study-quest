"""Study Quest Profile/RPG Blueprint for integration into the shared Flask app."""
from __future__ import annotations

import secrets

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from models.database import get_db
from models.profile_model import get_profile, update_profile

profile_bp = Blueprint("profile", __name__, url_prefix="/profile")

AVATARS = (
    {"code": "squirath", "filename": "squirre_athlete.png", "label": "Sóc vận động viên"},
    {"code": "capysnack", "filename": "capybara_snack.png", "label": "Chuột lang ăn vặt"},
    {"code": "catgls", "filename": "cat_glasses.png", "label": "Mèo đeo kính"},
    {"code": "corgivar", "filename": "corgi_varsity.png", "label": "Corgi áo varsity"},
    {"code": "dogshade", "filename": "dog_sunglasses.png", "label": "Chó kính râm"},
    {"code": "owlstudy", "filename": "owl_student.png", "label": "Cú học sinh"},
    {"code": "rabbook", "filename": "rabbit_book.png", "label": "Thỏ ôm sách"},
)
AVATARS_BY_CODE = {avatar["code"]: avatar for avatar in AVATARS}
EXP_PER_LEVEL = 100


@profile_bp.before_request
def require_login():
    """Use the existing signed Flask session contract; do not modify app policy."""
    if session.get("user_id") is None:
        flash("Em hãy đăng nhập để xem hồ sơ nhé.", "warning")
        return redirect(url_for("login", next=request.path))
    return None


def _load_activities(user_id, limit=20):
    """Read activity rows from existing tables, always scoped to the session user."""
    return get_db().execute(
        """
        SELECT activity_type, description, exp_earned, occurred_at FROM (
            SELECT 'Planner' AS activity_type, sp.title AS description,
                   CASE WHEN sp.completed = 1 THEN 20 ELSE 0 END AS exp_earned,
                   sp.study_date AS occurred_at, sp.id AS sort_id
            FROM study_plans sp
            JOIN exams e ON e.id = sp.exam_id
            WHERE e.user_id = ?
            UNION ALL
            SELECT 'Quiz', subject || CASE WHEN topic IS NOT NULL AND topic != '' THEN ' · ' || topic ELSE '' END,
                   exp_earned, created_at, id
            FROM quiz_attempts WHERE user_id = ?
            UNION ALL
            SELECT 'Pomodoro', CAST(duration_minutes AS TEXT) || ' phút tập trung',
                   exp_earned, completed_at, id
            FROM pomodoro_sessions WHERE user_id = ?
        ) AS activities
        ORDER BY occurred_at DESC, sort_id DESC
        LIMIT ?
        """,
        (user_id, user_id, user_id, int(limit)),
    ).fetchall()


def _profile_csrf_token():
    token = session.get("admin7_profile_csrf")
    if not token:
        token = secrets.token_urlsafe(32)
        session["admin7_profile_csrf"] = token
    return token


@profile_bp.route("", methods=["GET", "POST"])
def index():
    user_id = session.get("user_id")
    profile = get_profile(user_id)
    if profile is None:
        session.clear()
        flash("Không tìm thấy hồ sơ. Em hãy đăng nhập lại nhé.", "warning")
        return redirect(url_for("login"))

    if request.method == "POST":
        posted_token = request.form.get("csrf_token", "")
        expected_token = session.get("admin7_profile_csrf", "")
        if not expected_token or not secrets.compare_digest(str(expected_token), str(posted_token)):
            flash("Phiên cập nhật không hợp lệ. Em tải lại trang rồi thử lại nhé.", "warning")
            return redirect(url_for("profile.index"))
        # Only profile presentation fields are accepted; EXP/level/points are never read from form.
        character_name = request.form.get("character_name", "").strip()
        avatar = request.form.get("avatar", "")
        if len(character_name) > 30 or any(ord(ch) < 32 for ch in character_name):
            flash("Tên nhân vật tối đa 30 ký tự và không chứa ký tự điều khiển.", "warning")
        elif avatar not in AVATARS_BY_CODE:
            flash("Avatar được chọn không hợp lệ.", "warning")
        else:
            profile = update_profile(user_id, character_name or "Quest Rookie", avatar)
            flash("Đã cập nhật hồ sơ nhân vật.", "success")
            return redirect(url_for("profile.index"))

    total_exp = int(profile["exp"])
    selected_avatar = AVATARS_BY_CODE.get(profile["avatar"], AVATARS[0])
    exp_in_level = total_exp % EXP_PER_LEVEL
    progress_percent = int(exp_in_level * 100 / EXP_PER_LEVEL)
    activities = _load_activities(user_id)
    return render_template(
        "profile/profile.html",
        profile=profile,
        avatars=AVATARS,
        selected_avatar=selected_avatar,
        csrf_token=_profile_csrf_token(),
        exp_in_level=exp_in_level,
        exp_to_next=EXP_PER_LEVEL - exp_in_level,
        progress_percent=progress_percent,
        activities=activities,
    )


@profile_bp.get("/achievements")
def achievements():
    user_id = session.get("user_id")
    profile = get_profile(user_id)
    if profile is None:
        session.clear()
        flash("Không tìm thấy hồ sơ. Em hãy đăng nhập lại nhé.", "warning")
        return redirect(url_for("login"))
    # Ownership is enforced in SQL; no user_id can be supplied by the requester.
    rows = get_db().execute(
        "SELECT title, description, unlocked_at FROM achievements WHERE user_id = ? ORDER BY unlocked_at DESC, id DESC",
        (user_id,),
    ).fetchall()
    return render_template("profile/achievements.html", profile=profile, achievements=rows)


# EXP awards are intentionally not exposed as a Profile route. Quiz/Planner/Pomodoro
# must award EXP only in their backend completion handlers using Admin 2's add_exp().
