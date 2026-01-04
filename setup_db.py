import sqlite3
import requests
import time
import json
import sys

# اسم الملف الذي سنخزن فيه الأسئلة
DB_NAME = "anime_game.db"

def create_and_fill():
    # 1. إنشاء الملف والصندوق
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS anime (
            mal_id INTEGER PRIMARY KEY,
            title TEXT,
            popularity INTEGER,
            year INTEGER,
            studios TEXT,
            raw_json TEXT
        )
    ''')
    
    # 2. بدء التحميل (سنحمل 300 صفحة ليكون لدينا مخزون ضخم)
    print("🚀 جاري بدء تحميل البيانات... (هذا سيأخذ وقتاً، انتظر)")
    
    for page in range(1, 301): # من الصفحة 1 إلى 300
        try:
            # طباعة رقم الصفحة لنعرف أين وصلنا
            sys.stdout.write(f"\r📥 تحميل صفحة: {page} ...")
            sys.stdout.flush()

            # الاتصال بالموقع
            response = requests.get(f"https://api.jikan.moe/v4/top/anime?page={page}")
            
            if response.status_code == 200:
                data = response.json()['data']
                for anime in data:
                    # نتجاهل الأشياء التي ليست أنميات (مثل الموسيقى)
                    if anime.get('type') in ['Music', 'CM', 'Special']: continue

                    # تجهيز البيانات
                    studios = json.dumps([s['name'] for s in anime.get('studios', [])])
                    raw = json.dumps(anime)
                    
                    # الحفظ داخل الصندوق
                    c.execute('''
                        INSERT OR REPLACE INTO anime 
                        (mal_id, title, popularity, year, studios, raw_json)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (
                        anime['mal_id'],
                        anime['title'],
                        anime.get('popularity'),
                        anime.get('year'),
                        studios,
                        raw
                    ))
                conn.commit()
            
            # استراحة قصيرة جداً حتى لا يغضب الموقع منا
            time.sleep(1)
            
        except:
            pass # لو حدث خطأ بسيط تجاهله وأكمل

    conn.close()
    print("\n✅ انتهى! تم تجهيز الأسئلة.")

if __name__ == "__main__":
    create_and_fill()