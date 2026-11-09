from pathlib import Path
import sys

# =========================
# CẤU HÌNH
# =========================

ROOT = Path(__file__).resolve().parent
PASS = 0
WARN = 0
FAIL = 0


def ok(message):
    global PASS
    PASS += 1
    print(f"[PASS] {message}")


def warn(message):
    global WARN
    WARN += 1
    print(f"[WARN] {message}")


def fail(message):
    global FAIL
    FAIL += 1
    print(f"[FAIL] {message}")


def check_file(relative_path):
    path = ROOT / relative_path
    if path.exists():
        ok(f"Có file: {relative_path}")
        return True

    fail(f"Thiếu file: {relative_path}")
    return False


def check_any_file(paths, label):
    for relative_path in paths:
        if (ROOT / relative_path).exists():
            ok(f"{label}: {relative_path}")
            return True

    fail(f"Thiếu {label}: cần một trong {paths}")
    return False


def check_text(relative_path, keywords, label):
    path = ROOT / relative_path

    if not path.exists():
        fail(f"{label}: không tìm thấy {relative_path}")
        return

    try:
        content = path.read_text(encoding="utf-8").lower()
    except UnicodeDecodeError:
        content = path.read_text(encoding="utf-8-sig").lower()

    missing = [
        keyword for keyword in keywords
        if keyword.lower() not in content
    ]

    if missing:
        warn(f"{label}: còn thiếu từ khóa {missing} trong {relative_path}")
    else:
        ok(f"{label}: đạt trong {relative_path}")


def route_exists(app, expected_routes):
    actual_rules = {
        rule.rule
        for rule in app.url_map.iter_rules()
        if "GET" in rule.methods or "POST" in rule.methods
    }

    for route in expected_routes:
        matched = route in actual_rules

        # Hỗ trợ route có tham số, ví dụ /library/<int:book_id>
        if not matched and "<" in route:
            route_prefix = route.split("<", 1)[0]
            matched = any(rule.startswith(route_prefix) for rule in actual_rules)

        if matched:
            ok(f"Có route: {route}")
        else:
            fail(f"Thiếu route: {route}")

    return actual_rules


def test_http_routes(app, routes):
    print("\n--- KIỂM TRA PHẢN HỒI HTTP ---")

    client = app.test_client()

    for route in routes:
        try:
            response = client.get(route, follow_redirects=False)
            code = response.status_code

            # 200: trang mở bình thường
            # 3xx: route tồn tại nhưng chuyển hướng đăng nhập
            # 401/403: route tồn tại nhưng bị bảo vệ
            if code == 200:
                ok(f"{route} → HTTP {code}")
            elif code in (301, 302, 303, 307, 308, 401, 403):
                warn(f"{route} → HTTP {code} (có thể cần đăng nhập)")
            elif code == 404:
                fail(f"{route} → HTTP 404 - không tìm thấy")
            else:
                fail(f"{route} → HTTP {code}")

        except Exception as error:
            fail(f"{route} → lỗi khi chạy: {error}")


def main():
    print("=" * 60)
    print("STUDY QUEST - KIỂM TRA TỔNG QUAN PROJECT")
    print("=" * 60)

    print("\n--- KIỂM TRA CẤU TRÚC FILE ---")

    required_files = [
        "app.py",
        "config.py",
        "requirements.txt",
        "models/database.py",
        "models/user_model.py",
        "models/profile_model.py",
        "models/exam_model.py",
        "models/quiz_model.py",
        "models/library_model.py",
        "templates/base.html",
        "templates/index.html",
        "static/css/style.css",
    ]

    for file_path in required_files:
        check_file(file_path)

    check_any_file(
        [
            "routes/exam_routes.py",
            "routes/planner_routes.py",
        ],
        "route Planner",
    )

    check_any_file(
        [
            "routes/quiz_routes.py",
        ],
        "route Quiz",
    )

    check_any_file(
        [
            "routes/library_routes.py",
        ],
        "route Library",
    )

    check_any_file(
        [
            "routes/profile_routes.py",
            "routes/rpg_routes.py",
        ],
        "route Profile/RPG",
    )

    check_any_file(
        [
            "templates/exam/index.html",
            "templates/exam/new.html",
        ],
        "template Planner",
    )

    check_any_file(
        [
            "templates/quiz/index.html",
            "templates/quiz.html",
        ],
        "template Quiz",
    )

    check_any_file(
        [
            "templates/library/index.html",
        ],
        "template Library",
    )

    check_any_file(
        [
            "templates/profile/profile.html",
            "templates/profile.html",
        ],
        "template Profile/RPG",
    )

    print("\n--- KIỂM TRA NỘI DUNG TRANG CHỦ ---")

    check_text(
        "templates/index.html",
        ["study quest"],
        "Tên dự án",
    )

    check_text(
        "templates/index.html",
        ["về dự án"],
        "Phần giới thiệu dự án",
    )

    check_text(
        "templates/index.html",
        ["liên hệ"],
        "Phần liên hệ",
    )

    check_text(
        "templates/index.html",
        ["12a1 hoàng diệu"],
        "Thông tin lớp/liên hệ",
    )

    check_text(
        "templates/index.html",
        ["ngô kim ngân"],
        "Tên Admin 1",
    )

    check_text(
        "templates/index.html",
        ["đặng huỳnh thảo nhi"],
        "Tên Admin 2",
    )

    check_text(
        "templates/index.html",
        ["nguyễn trần gia mỹ"],
        "Tên Admin 3",
    )

    check_text(
        "templates/index.html",
        ["quách hồ cát tiên"],
        "Tên Admin 4",
    )

    check_text(
        "templates/index.html",
        ["khưu bảo châu"],
        "Tên Admin 5",
    )

    check_text(
        "templates/index.html",
        ["huỳnh nhật huy"],
        "Tên Admin 6",
    )

    check_text(
        "templates/index.html",
        ["nguyễn thành hậu"],
        "Tên Admin 7",
    )

    print("\n--- KIỂM TRA ROUTE FLASK ---")

    try:
        from app import app

        app.config.update(
            TESTING=True,
            WTF_CSRF_ENABLED=False,
        )

        expected_routes = [
            "/",
            "/login",
            "/register",
            "/dashboard",
            "/planner",
            "/quiz",
            "/library/",
            "/profile",
            "/profile/achievements",
            "/pomodoro",
        ]

        actual_routes = route_exists(app, expected_routes)

        print("\n--- CÁC ROUTE ĐANG CÓ TRONG APP ---")
        for route in sorted(actual_routes):
            print(f"  {route}")

        http_routes = [
            "/",
            "/login",
            "/register",
            "/dashboard",
            "/planner",
            "/quiz",
            "/library/",
            "/profile",
            "/pomodoro",
        ]

        test_http_routes(app, http_routes )

    except Exception as error:
        fail(f"Không thể import Flask app: {error}")

    print("\n--- KIỂM TRA BẢO MẬT CƠ BẢN ---")

    app_path = ROOT / "app.py"
    if not app_path.exists():
        warn("Không thể xác nhận hash mật khẩu: không tìm thấy app.py")
    else:
        try:
            app_content = app_path.read_text(encoding="utf-8").lower()
        except UnicodeDecodeError:
            app_content = app_path.read_text(encoding="utf-8-sig").lower()

        missing_hash_functions = [
            function_name
            for function_name in ("generate_password_hash", "check_password_hash")
            if function_name not in app_content
        ]
        if missing_hash_functions:
            warn(
                "Không tìm thấy đủ hàm hash mật khẩu trong app.py: "
                f"{missing_hash_functions}"
            )
        else:
            ok("Hash mật khẩu được xử lý bằng Werkzeug trong app.py")

    print("\n--- KẾT QUẢ ---")
    print(f"PASS: {PASS}")
    print(f"WARN: {WARN}")
    print(f"FAIL: {FAIL}")

    if FAIL == 0:
        print("\nKẾT LUẬN: Không phát hiện lỗi nghiêm trọng trong kiểm tra tự động.")
        print("Vẫn cần kiểm tra thủ công đăng nhập, Planner, Quiz, Library, RPG và giao diện.")
        sys.exit(0)

    print("\nKẾT LUẬN: Cần xem các dòng FAIL và sửa trước khi nộp.")
    sys.exit(1)


if __name__ == "__main__":
    main()
