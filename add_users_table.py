import sqlite3

# فتح قاعدة البيانات الموجودة
conn = sqlite3.connect("anime_game.db")
c = conn.cursor()

# إنشاء جدول المستخدمين
c.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        mal_username TEXT
    )
''')

conn.commit()
conn.close()
print("✅ تم إضافة جدول المستخدمين بنجاح!")