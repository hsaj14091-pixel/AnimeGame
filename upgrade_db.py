import sqlite3

def add_verification_column():
    conn = sqlite3.connect("anime_game.db")
    c = conn.cursor()
    try:
        # نضيف عمود التفعيل (0 = غير مفعل، 1 = مفعل)
        c.execute('ALTER TABLE users ADD COLUMN is_verified INTEGER DEFAULT 0')
        print("✅ تم تحديث قاعدة البيانات بنجاح!")
    except:
        print("ℹ️ العمود موجود مسبقاً، لا داعي للتحديث.")
    
    conn.commit()
    conn.close()

if __name__ == "__main__":
    add_verification_column()