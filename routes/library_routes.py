# routes/library_routes.py
# Module: Smart Learning Hub / Library
# Admin 5 - Study Quest
#
# CHỈ sử dụng model có sẵn, KHÔNG tự kết nối SQLite, KHÔNG sửa bảng books.

from flask import (
    Blueprint,
    render_template,
    request,
    abort,
)
from urllib.parse import urlencode

from models.library_model import (
    list_books,
    get_book,
    list_subjects,
    list_categories,
)

library_bp = Blueprint(
    "library",
    __name__,
    url_prefix="/library",
    template_folder="../templates",
)


# ---------------------------------------------------------------------------
# Helper: gọi list_books an toàn với nhiều kiểu chữ ký model khác nhau.
# Mục tiêu: nếu model của Admin 2 dùng tên tham số khác (q/search/keyword,
# subject/subject_id, category/category_id) thì vẫn chạy được, KHÔNG sửa model.
# ---------------------------------------------------------------------------
def _safe_list_books(keyword="", subject="", category=""):
    attempts = [
        # Ưu tiên chữ ký phổ biến nhất
        dict(q=keyword, subject=subject, category=category),
        dict(search=keyword, subject=subject, category=category),
        dict(keyword=keyword, subject=subject, category=category),
        dict(q=keyword, subject_id=subject, category_id=category),
        dict(search=keyword, subject_id=subject, category_id=category),
        dict(keyword=keyword, subject_id=subject, category_id=category),
        dict(q=keyword, subject=subject),
        dict(q=keyword, category=category),
        dict(q=keyword),
        dict(),
    ]
    last_error = None
    for kwargs in attempts:
        # Bỏ các tham số rỗng để tránh model hiểu nhầm là lọc theo chuỗi rỗng
        cleaned = {k: v for k, v in kwargs.items() if v not in (None, "", [])}
        try:
            return list_books(**cleaned) if cleaned else list_books()
        except TypeError as exc:
            last_error = exc
            continue
    # Nếu mọi cách đều lỗi, raise lại lỗi cuối để dễ debug
    raise last_error


def _safe_list_options(func):
    """Gọi list_subjects / list_categories an toàn."""
    try:
        return func() or []
    except Exception:
        return []


def _normalize_options(items):
    """
    Chuẩn hóa danh sách môn học / thể loại về list các dict có 'value' và 'label'.
    Chấp nhận nhiều kiểu dữ liệu: str, dict, tuple, object có thuộc tính.
    """
    result = []
    for item in items or []:
        if isinstance(item, str):
            result.append({"value": item, "label": item})
        elif isinstance(item, dict):
            value = (
                item.get("value")
                or item.get("id")
                or item.get("name")
                or item.get("subject")
                or item.get("category")
            )
            label = (
                item.get("label")
                or item.get("name")
                or item.get("title")
                or value
            )
            if value is not None:
                result.append({"value": str(value), "label": str(label)})
        elif isinstance(item, (list, tuple)) and len(item) >= 2:
            result.append({"value": str(item[0]), "label": str(item[1])})
        else:
            value = getattr(item, "id", None) or getattr(item, "name", None)
            label = getattr(item, "name", None) or value
            if value is not None:
                result.append({"value": str(value), "label": str(label)})
    # Loại trùng theo value
    seen = set()
    unique = []
    for opt in result:
        if opt["value"] not in seen:
            seen.add(opt["value"])
            unique.append(opt)
    return unique


# ---------------------------------------------------------------------------
# ROUTE 1: Danh sách tài liệu (kèm tìm kiếm + lọc)
# ---------------------------------------------------------------------------
@library_bp.route("/", methods=["GET"])
def list_books_view():
    keyword = (request.args.get("q") or "").strip()
    subject = (request.args.get("subject") or "").strip()
    category = (request.args.get("category") or "").strip()

    try:
        books = _safe_list_books(keyword=keyword, subject=subject, category=category)
    except Exception:
        # Không để crash trang; hiển thị danh sách rỗng + thông báo
        books = []

    subjects_raw = _safe_list_options(list_subjects)
    categories_raw = _safe_list_options(list_categories)

    subjects = _normalize_options(subjects_raw)
    categories = _normalize_options(categories_raw)

    return render_template(
        "library/index.html",
        books=books or [],
        subjects=subjects,
        categories=categories,
        keyword=keyword,
        selected_subject=subject,
        selected_category=category,
    )


# ---------------------------------------------------------------------------
# ROUTE 2: Chi tiết tài liệu
# ---------------------------------------------------------------------------
@library_bp.route("/<int:book_id>", methods=["GET"])
def book_detail(book_id):
    # book_id đã được ép kiểu int bởi converter; kiểm tra dương
    if not isinstance(book_id, int) or book_id <= 0:
        abort(404)

    try:
        book = get_book(book_id)
    except Exception:
        book = None

    if not book:
        abort(404)

    # Chuẩn bị link quiz theo môn / chủ đề (không bắt buộc model quiz tồn tại)
    subject_value = _get_field(book, "subject", "subject_name", "mon_hoc")
    topic_value = _get_field(book, "topic", "topic_name", "chu_de")

    quiz_by_subject_url = None
    quiz_by_topic_url = None

    if subject_value:
        params = {"subject": str(subject_value)}
        if topic_value:
            params["topic"] = str(topic_value)
        quiz_by_subject_url = "/quiz?" + urlencode(params)
    if topic_value:
        params = {"topic": str(topic_value)}
        if subject_value:
            params["subject"] = str(subject_value)
        quiz_by_topic_url = "/quiz?" + urlencode(params)

    return render_template(
        "library/detail.html",
        book=book,
        quiz_by_subject_url=quiz_by_subject_url,
        quiz_by_topic_url=quiz_by_topic_url,
    )


# ---------------------------------------------------------------------------
# Tiện ích đọc field linh hoạt (hỗ trợ dict hoặc object)
# ---------------------------------------------------------------------------
def _get_field(obj, *names, default=None):
    if obj is None:
        return default
    for name in names:
        if isinstance(obj, dict):
            if name in obj and obj[name] not in (None, ""):
                return obj[name]
        else:
            if hasattr(obj, name):
                value = getattr(obj, name)
                if value not in (None, ""):
                    return value
    return default
