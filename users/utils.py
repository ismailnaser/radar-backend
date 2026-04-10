import random
import requests
from django.conf import settings

def generate_otp():
    """توليد رمز تحقق عشوائي من 6 أرقام."""
    return str(random.randint(100000, 999999))

def send_whatsapp_message(phone_number, code):
    """
    إرسال رسالة واتساب حقيقية عبر UltraMsg مع وضع المطور للتجربة.
    """
    message = f"مرحباً بك في رادار! رمز التحقق الخاص بك هو: {code}"
    
    # تحويل الرقم إلى التنسيق الدولي بدون علامة + إذا لزم الأمر
    clean_phone = phone_number.replace("+", "")

    # في وضع المطور، نقوم فقط بالطباعة
    if settings.WHATSAPP_DEBUG_MODE:
        print("\n" + "="*50)
        print("🛠️ وضع المطور مفعل (WHATSAPP_DEBUG_MODE = True)")
        print(f"📱 إرسال إلى: {phone_number}")
        print(f"💬 الرسالة: {message}")
        print("="*50 + "\n")
        return True

    # الإرسال الحقيقي (UltraMsg)
    url = f"https://api.ultramsg.com/{settings.ULTRAMSG_INSTANCE_ID}/messages/chat"
    payload = {
        "token": settings.ULTRAMSG_TOKEN,
        "to": clean_phone,
        "body": message,
        "priority": 10,
        "referenceId": ""
    }
    headers = {'content-type': 'application/x-www-form-urlencoded'}

    try:
        response = requests.post(url, data=payload, headers=headers)
        if response.status_code == 200:
            return True
        else:
            print(f"❌ خطأ من UltraMsg: {response.text}")
            return False
    except Exception as e:
        print(f"❌ فشل الاتصال بخدمة الواتساب: {str(e)}")
        return False
