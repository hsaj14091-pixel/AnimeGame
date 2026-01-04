import requests
import json

username = "Bomahdey"
# نستخدم الرابط الخام بدون أي فلاتر
url = f"https://api.jikan.moe/v4/users/{username}/animelist"

print(f"--- 📡 جاري اختبار الاتصال بـ: {url} ---")

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

try:
    # 1. المحاولة الأولى: محاكاة متصفح
    response = requests.get(url, headers=headers, timeout=15)
    
    print(f"\nStatus Code: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json().get('data', [])
        print(f"✅ نجاح! تم العثور على {len(data)} أنمي.")
        if len(data) > 0:
            first_anime = data[0]
            print(f"مثال على البيانات: {json.dumps(first_anime.get('status'), ensure_ascii=False)}")
    else:
        print("❌ فشل الاتصال.")
        print(f"الرد من السيرفر: {response.text[:200]}") # طباعة أول 200 حرف من الخطأ

except Exception as e:
    print(f"\n🔥 حدث خطأ فني: {e}")

input("\nاضغط Enter للإغلاق...")