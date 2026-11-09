"""Profile/RPG model. Đây là nơi duy nhất cập nhật EXP."""
from .database import get_db


def get_profile(user_id):
    return get_db().execute(
        'SELECT u.id, u.username, u.email, u.role, u.admin_permission, '
        'p.character_name, p.avatar, p.level, p.exp, p.reward_points '
        'FROM users u JOIN profiles p ON p.user_id = u.id WHERE u.id = ?',
        (user_id,),
    ).fetchone()


def add_exp(user_id, amount):
    """Cộng EXP ở backend; không nhận EXP do client tự gửi tùy ý."""
    amount = max(0, int(amount))
    db = get_db()
    profile = db.execute('SELECT exp FROM profiles WHERE user_id = ?', (user_id,)).fetchone()
    if profile is None:
        return None
    total_exp = profile['exp'] + amount
    level = 1 + total_exp // 100
    db.execute(
        'UPDATE profiles SET exp = ?, level = ?, reward_points = reward_points + ? WHERE user_id = ?',
        (total_exp, level, amount // 5, user_id),
    )
    db.commit()
    return get_profile(user_id)


def update_profile(user_id, character_name, avatar):
    db = get_db()
    db.execute(
        'UPDATE profiles SET character_name = ?, avatar = ? WHERE user_id = ?',
        (character_name.strip()[:30] or 'Quest Rookie', avatar[:10], user_id),
    )
    db.commit()
    return get_profile(user_id)


def unlock_achievement(user_id, title, description):
    db = get_db()
    db.execute(
        'INSERT OR IGNORE INTO achievements(user_id,title,description) VALUES(?,?,?)',
        (user_id, title, description),
    )
    db.commit()
