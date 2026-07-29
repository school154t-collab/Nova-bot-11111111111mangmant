"""
============================================================
  Nova Town — بوت الإدارة + لوحة التحكم (ملف واحد)
============================================================
كل شي في هذا الملف: التكتات، الويتينق، النقاط، الإجازات،
الترقيات، إداري الأسبوع، والموقع (Flask).

التشغيل:
    pip install discord.py flask tzdata
    python novatown.py

يشغّل البوت والموقع مع بعض في نفس الوقت.
عدّل قسم الإعدادات بالأسفل قبل التشغيل.
============================================================
"""
import os
import re
import time
import asyncio
import sqlite3
import threading
from functools import wraps
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import discord
from discord.ext import commands, tasks
from discord import ui
from flask import (Flask, render_template_string, request, redirect,
                   url_for, session, flash)

# ============================================================
#                        الإعدادات
#   عدّل القيم هنا فقط. الرومات والرتب اللي أعطيتني مدخلة مسبقاً.
# ============================================================

# --- التوكن والسيرفر (مطلوب) ---
BOT_TOKEN = os.getenv("BOT_TOKEN", "ضع_توكن_البوت_هنا")
GUILD_ID  = int(os.getenv("GUILD_ID", "0"))   # ID السيرفر

# --- الرتب ---
ADMIN_ROLE_ID       = 1527507482421887036   # رتبة النظام الإداري
VACATION_ROLE_ID    = 1527507627838275694   # رتبة الإجازة
AOW_ROLE_ID         = 1527507457566314577   # رتبة إداري الأسبوع (تُعطى للفائز وتُشال بعد أسبوع)

# --- المالك (تحكم البوت) ---
OWNER_ID            = 888881975463673867    # الوحيد اللي يتحكم بتشغيل/إطفاء البوت

# --- الرومات ---
WAITING_CHANNEL_ID      = 1527509646640676975   # الويتينق (صوتي)
WAITING_NOTIFY_CHANNEL_ID = 1531361845959594258 # روم إشعارات الويتينق/السحب/تم الانتهاء (نصي)
DONE_CHANNEL_ID         = 1527509649731879003   # الدن (صوتي)
ADMIN_OF_WEEK_CHANNEL_ID= 1527508910225756210   # إداري الأسبوع
VACATION_CHANNEL_ID     = 1527508970942627932   # الإجازات
PROMOTION_CHANNEL_ID    = 1527508916878053377   # الترقيات
WELCOME_CHANNEL_ID      = 1527508709197090826   # الترحيب (الويلكوم)
FAQ_JOIN_CHANNEL_ID     = 1527509217664045126   # روم "كيف أدخل السيرفر" (للأسئلة الشائعة)
ATHKAR_CHANNEL_ID       = 1527509266733334610   # روم الأذكار (رسالة كل 3 ساعات)
TICKET_PANEL_CHANNEL_ID = 1527509194532585483   # روم لوحة التكتات (العرض)
TICKET_CATEGORY_ID      = 1527508134900404286   # كاتقوري التكتات (تنفتح تحته)
TICKET_LOG_CHANNEL_ID   = 0   # روم سجل التقييمات (اختياري)

# --- إعدادات عامة ---
TIMEZONE              = "Asia/Riyadh"
POINTS_TICKET_CLAIM   = 3     # نقاط استلام التكت
POINTS_WAITING_PULL   = 3     # نقاط السحب من الويتينق
AOW_DAY, AOW_HOUR, AOW_MINUTE = "thursday", 20, 5   # إداري الأسبوع (الخميس 8:05 مساءً)
VACATION_CHECK_HOURS  = 2     # يفحص الإجازات المنتهية كل ساعتين
TICKET_COOLDOWN_SECONDS = 60
TICKET_LATE_MINUTES     = 30    # لو تكت ما استُلم خلال هذا الوقت، ينبّه الإدارة

# --- الموقع ---
DASHBOARD_PASSWORD = "NovaTown123RowexM112"
WEB_PORT           = int(os.getenv("PORT", "5000"))
SECRET_KEY         = os.getenv("SECRET_KEY", "nova-town-secret-change-me")

# --- سلم الرتب (من الأسفل Support للأعلى Super Admin) ---
# رتّبتها من صور السيرفر. ضع الـ Role ID لكل رتبة مكان الـ 0.
# نظام الترقيات يستخدم الترتيب: الترقية = الرتبة اللي بعدها في القائمة.
ROLE_LADDER = [
    {"name": "Support",            "id": 1527507476692602900},
    {"name": "Trail Mod",          "id": 1527507474976870571},
    {"name": "Mod",                "id": 1527507472913273033},
    {"name": "Senior Mod",         "id": 1527507470723973160},
    {"name": "Trail",              "id": 1527507468958044231},
    # ── فاصل: صنعى ──
    {"name": "Skilled",            "id": 1527507465472573531},
    {"name": "Supervisor",         "id": 1527507463887126651},
    {"name": "Expert",             "id": 1527507462297747476},
    {"name": "Operator",           "id": 1527507460724752454},
    {"name": "Admin",              "id": 1527507459411808306},
    # ── فاصل: وسطى ──
    {"name": "Executive",          "id": 1527507429645095084},
    {"name": "Controller",         "id": 1527507431230410833},
    {"name": "Console",            "id": 1527507432887156806},
    {"name": "Head Admin",         "id": 1527507434745364510},
    # ── فاصل: علياء ──
    {"name": "Super Admin",        "id": 1527507438427836426},
]

# --- الهوية والجماليات ---
BRAND_COLOR   = 0x2F8FFF          # الأزرق الأساسي
COLOR_SUCCESS = 0x28C76F          # أخضر (نجاح/استلام)
COLOR_GOLD    = 0xFFCB47          # ذهبي (إداري الأسبوع/تقييم)
COLOR_DANGER  = 0xFF4D6A          # أحمر (إغلاق/تنبيه)
COLOR_PURPLE  = 0x9B6DFF          # بنفسجي (ترقيات)
BRAND_NAME    = "Nova Town"
BRAND_ICON    = "https://i.imgur.com/FG6XesA.png"   # شعار NT — يظهر في كل الرسائل والموقع
BRAND_BANNER  = ""                # رابط بنر عريض (اختياري) — يظهر أسفل الرسائل المهمة
WELCOME_BANNER= "https://i.imgur.com/kDtu1Ig.png"   # بنر الترحيب العريض — يظهر أسفل رسالة الويلكوم
TICKET_LOGO   = "https://i.imgur.com/FG6XesA.png"   # شعار التكتات (نفس شعار NT)
DIVIDER       = "◈ ─────────────────────── ◈"

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "novatown.db")


# ============================================================
#          محتوى روم الأذكار (مجموعة مختارة ومدقّقة)
#   لإضافة المزيد: ضِف سطراً جديداً {"type","text","source"}
#   type: ذكر / دعاء / آية / تسبيح / استغفار / حديث
# ============================================================
ATHKAR = [
    # ---------- التسبيح والتهليل ----------
    {"type": "تسبيح", "text": "سُبْحَانَ اللَّهِ وَبِحَمْدِهِ، سُبْحَانَ اللَّهِ الْعَظِيمِ", "source": "متفق عليه"},
    {"type": "تسبيح", "text": "سُبْحَانَ اللَّهِ، وَالْحَمْدُ لِلَّهِ، وَلَا إِلَهَ إِلَّا اللَّهُ، وَاللَّهُ أَكْبَرُ", "source": "رواه مسلم"},
    {"type": "ذكر", "text": "لَا إِلَهَ إِلَّا اللَّهُ وَحْدَهُ لَا شَرِيكَ لَهُ، لَهُ الْمُلْكُ وَلَهُ الْحَمْدُ وَهُوَ عَلَى كُلِّ شَيْءٍ قَدِيرٌ", "source": "متفق عليه"},
    {"type": "ذكر", "text": "لَا حَوْلَ وَلَا قُوَّةَ إِلَّا بِاللَّهِ", "source": "متفق عليه"},
    {"type": "تسبيح", "text": "سُبْحَانَ اللَّهِ وَبِحَمْدِهِ عَدَدَ خَلْقِهِ، وَرِضَا نَفْسِهِ، وَزِنَةَ عَرْشِهِ، وَمِدَادَ كَلِمَاتِهِ", "source": "رواه مسلم"},
    {"type": "ذكر", "text": "الْحَمْدُ لِلَّهِ رَبِّ الْعَالَمِينَ، حَمْدًا كَثِيرًا طَيِّبًا مُبَارَكًا فِيهِ", "source": "رواه البخاري"},
    {"type": "ذكر", "text": "اللَّهُمَّ صَلِّ وَسَلِّمْ عَلَى نَبِيِّنَا مُحَمَّدٍ", "source": "الصلاة على النبي ﷺ"},

    # ---------- الاستغفار ----------
    {"type": "استغفار", "text": "أَسْتَغْفِرُ اللَّهَ الْعَظِيمَ الَّذِي لَا إِلَهَ إِلَّا هُوَ الْحَيَّ الْقَيُّومَ وَأَتُوبُ إِلَيْهِ", "source": "رواه أبو داود والترمذي"},
    {"type": "استغفار", "text": "رَبِّ اغْفِرْ لِي وَتُبْ عَلَيَّ إِنَّكَ أَنْتَ التَّوَّابُ الرَّحِيمُ", "source": "رواه أبو داود والترمذي"},
    {"type": "استغفار", "text": "اللَّهُمَّ أَنْتَ رَبِّي لَا إِلَهَ إِلَّا أَنْتَ، خَلَقْتَنِي وَأَنَا عَبْدُكَ، وَأَنَا عَلَى عَهْدِكَ وَوَعْدِكَ مَا اسْتَطَعْتُ، أَبُوءُ لَكَ بِنِعْمَتِكَ عَلَيَّ وَأَبُوءُ بِذَنْبِي فَاغْفِرْ لِي", "source": "سيد الاستغفار — رواه البخاري"},
    {"type": "استغفار", "text": "أَسْتَغْفِرُ اللَّهَ وَأَتُوبُ إِلَيْهِ", "source": "رواه البخاري ومسلم"},

    # ---------- الأدعية النبوية ----------
    {"type": "دعاء", "text": "اللَّهُمَّ إِنِّي أَسْأَلُكَ الْهُدَى وَالتُّقَى وَالْعَفَافَ وَالْغِنَى", "source": "رواه مسلم"},
    {"type": "دعاء", "text": "اللَّهُمَّ أَعِنِّي عَلَى ذِكْرِكَ وَشُكْرِكَ وَحُسْنِ عِبَادَتِكَ", "source": "رواه أبو داود"},
    {"type": "دعاء", "text": "اللَّهُمَّ إِنِّي أَعُوذُ بِكَ مِنَ الْهَمِّ وَالْحَزَنِ، وَالْعَجْزِ وَالْكَسَلِ، وَالْبُخْلِ وَالْجُبْنِ، وَضَلَعِ الدَّيْنِ وَغَلَبَةِ الرِّجَالِ", "source": "رواه البخاري"},
    {"type": "دعاء", "text": "يَا مُقَلِّبَ الْقُلُوبِ ثَبِّتْ قَلْبِي عَلَى دِينِكَ", "source": "رواه الترمذي"},
    {"type": "دعاء", "text": "اللَّهُمَّ إِنِّي أَسْأَلُكَ الْعَافِيَةَ فِي الدُّنْيَا وَالْآخِرَةِ", "source": "رواه ابن ماجه"},
    {"type": "دعاء", "text": "اللَّهُمَّ اغْفِرْ لِي ذَنْبِي كُلَّهُ، دِقَّهُ وَجِلَّهُ، وَأَوَّلَهُ وَآخِرَهُ، وَعَلَانِيَتَهُ وَسِرَّهُ", "source": "رواه مسلم"},
    {"type": "دعاء", "text": "اللَّهُمَّ إِنِّي أَعُوذُ بِرِضَاكَ مِنْ سَخَطِكَ، وَبِمُعَافَاتِكَ مِنْ عُقُوبَتِكَ", "source": "رواه مسلم"},
    {"type": "دعاء", "text": "رَبَّنَا آتِنَا فِي الدُّنْيَا حَسَنَةً وَفِي الْآخِرَةِ حَسَنَةً وَقِنَا عَذَابَ النَّارِ", "source": "سورة البقرة: 201"},
    {"type": "دعاء", "text": "اللَّهُمَّ إِنَّكَ عَفُوٌّ تُحِبُّ الْعَفْوَ فَاعْفُ عَنِّي", "source": "رواه الترمذي"},
    {"type": "دعاء", "text": "حَسْبُنَا اللَّهُ وَنِعْمَ الْوَكِيلُ", "source": "سورة آل عمران: 173"},
    {"type": "دعاء", "text": "لَا إِلَهَ إِلَّا أَنْتَ سُبْحَانَكَ إِنِّي كُنْتُ مِنَ الظَّالِمِينَ", "source": "سورة الأنبياء: 87"},
    {"type": "دعاء", "text": "رَبِّ اشْرَحْ لِي صَدْرِي وَيَسِّرْ لِي أَمْرِي", "source": "سورة طه: 25-26"},
    {"type": "دعاء", "text": "رَبَّنَا لَا تُؤَاخِذْنَا إِنْ نَسِينَا أَوْ أَخْطَأْنَا", "source": "سورة البقرة: 286"},
    {"type": "دعاء", "text": "رَبِّ زِدْنِي عِلْمًا", "source": "سورة طه: 114"},
    {"type": "دعاء", "text": "رَبَّنَا هَبْ لَنَا مِنْ أَزْوَاجِنَا وَذُرِّيَّاتِنَا قُرَّةَ أَعْيُنٍ وَاجْعَلْنَا لِلْمُتَّقِينَ إِمَامًا", "source": "سورة الفرقان: 74"},

    # ---------- آيات قصيرة ----------
    {"type": "آية", "text": "إِنَّ مَعَ الْعُسْرِ يُسْرًا", "source": "سورة الشرح: 6"},
    {"type": "آية", "text": "وَمَنْ يَتَّقِ اللَّهَ يَجْعَلْ لَهُ مَخْرَجًا • وَيَرْزُقْهُ مِنْ حَيْثُ لَا يَحْتَسِبُ", "source": "سورة الطلاق: 2-3"},
    {"type": "آية", "text": "أَلَا بِذِكْرِ اللَّهِ تَطْمَئِنُّ الْقُلُوبُ", "source": "سورة الرعد: 28"},
    {"type": "آية", "text": "وَقُلْ رَبِّ زِدْنِي عِلْمًا", "source": "سورة طه: 114"},
    {"type": "آية", "text": "إِنَّ اللَّهَ مَعَ الصَّابِرِينَ", "source": "سورة البقرة: 153"},
    {"type": "آية", "text": "فَاذْكُرُونِي أَذْكُرْكُمْ وَاشْكُرُوا لِي وَلَا تَكْفُرُونِ", "source": "سورة البقرة: 152"},
    {"type": "آية", "text": "وَبَشِّرِ الصَّابِرِينَ", "source": "سورة البقرة: 155"},
    {"type": "آية", "text": "وَاللَّهُ خَيْرٌ حَافِظًا وَهُوَ أَرْحَمُ الرَّاحِمِينَ", "source": "سورة يوسف: 64"},
    {"type": "آية", "text": "وَعَسَى أَنْ تَكْرَهُوا شَيْئًا وَهُوَ خَيْرٌ لَكُمْ", "source": "سورة البقرة: 216"},
    {"type": "آية", "text": "إِنَّ اللَّهَ لَا يُضِيعُ أَجْرَ الْمُحْسِنِينَ", "source": "سورة التوبة: 120"},
    {"type": "آية", "text": "وَمَنْ يَتَوَكَّلْ عَلَى اللَّهِ فَهُوَ حَسْبُهُ", "source": "سورة الطلاق: 3"},
    {"type": "آية", "text": "فَإِنَّ اللَّهَ يُحِبُّ الْمُتَّقِينَ", "source": "سورة آل عمران: 76"},

    # ---------- أذكار الصباح والمساء ----------
    {"type": "ذكر", "text": "أَعُوذُ بِكَلِمَاتِ اللَّهِ التَّامَّاتِ مِنْ شَرِّ مَا خَلَقَ", "source": "رواه مسلم"},
    {"type": "ذكر", "text": "بِسْمِ اللَّهِ الَّذِي لَا يَضُرُّ مَعَ اسْمِهِ شَيْءٌ فِي الْأَرْضِ وَلَا فِي السَّمَاءِ وَهُوَ السَّمِيعُ الْعَلِيمُ", "source": "رواه أبو داود والترمذي"},
    {"type": "ذكر", "text": "رَضِيتُ بِاللَّهِ رَبًّا، وَبِالْإِسْلَامِ دِينًا، وَبِمُحَمَّدٍ ﷺ نَبِيًّا", "source": "رواه أبو داود والترمذي"},
    {"type": "ذكر", "text": "حَسْبِيَ اللَّهُ لَا إِلَهَ إِلَّا هُوَ عَلَيْهِ تَوَكَّلْتُ وَهُوَ رَبُّ الْعَرْشِ الْعَظِيمِ", "source": "رواه أبو داود"},
    {"type": "ذكر", "text": "اللَّهُمَّ إِنِّي أَصْبَحْتُ أُشْهِدُكَ وَأُشْهِدُ حَمَلَةَ عَرْشِكَ وَمَلَائِكَتَكَ وَجَمِيعَ خَلْقِكَ أَنَّكَ أَنْتَ اللَّهُ لَا إِلَهَ إِلَّا أَنْتَ", "source": "رواه أبو داود"},
    {"type": "ذكر", "text": "اللَّهُمَّ مَا أَصْبَحَ بِي مِنْ نِعْمَةٍ أَوْ بِأَحَدٍ مِنْ خَلْقِكَ فَمِنْكَ وَحْدَكَ لَا شَرِيكَ لَكَ، فَلَكَ الْحَمْدُ وَلَكَ الشُّكْرُ", "source": "رواه أبو داود"},
    {"type": "ذكر", "text": "اللَّهُمَّ عَافِنِي فِي بَدَنِي، اللَّهُمَّ عَافِنِي فِي سَمْعِي، اللَّهُمَّ عَافِنِي فِي بَصَرِي، لَا إِلَهَ إِلَّا أَنْتَ", "source": "رواه أبو داود"},
    {"type": "ذكر", "text": "يَا حَيُّ يَا قَيُّومُ بِرَحْمَتِكَ أَسْتَغِيثُ، أَصْلِحْ لِي شَأْنِي كُلَّهُ وَلَا تَكِلْنِي إِلَى نَفْسِي طَرْفَةَ عَيْنٍ", "source": "رواه الحاكم والنسائي"},

    # ---------- فضائل وأحاديث قصيرة ----------
    {"type": "حديث", "text": "كَلِمَتَانِ خَفِيفَتَانِ عَلَى اللِّسَانِ، ثَقِيلَتَانِ فِي الْمِيزَانِ، حَبِيبَتَانِ إِلَى الرَّحْمَنِ: سُبْحَانَ اللَّهِ وَبِحَمْدِهِ، سُبْحَانَ اللَّهِ الْعَظِيمِ", "source": "متفق عليه"},
    {"type": "حديث", "text": "مَنْ قَالَ: سُبْحَانَ اللَّهِ وَبِحَمْدِهِ فِي يَوْمٍ مِائَةَ مَرَّةٍ حُطَّتْ خَطَايَاهُ وَإِنْ كَانَتْ مِثْلَ زَبَدِ الْبَحْرِ", "source": "متفق عليه"},
    {"type": "حديث", "text": "أَحَبُّ الْكَلَامِ إِلَى اللَّهِ أَرْبَعٌ: سُبْحَانَ اللَّهِ، وَالْحَمْدُ لِلَّهِ، وَلَا إِلَهَ إِلَّا اللَّهُ، وَاللَّهُ أَكْبَرُ", "source": "رواه مسلم"},
    {"type": "حديث", "text": "مَنْ صَلَّى عَلَيَّ صَلَاةً وَاحِدَةً صَلَّى اللَّهُ عَلَيْهِ بِهَا عَشْرًا", "source": "رواه مسلم"},
    {"type": "حديث", "text": "الطُّهُورُ شَطْرُ الْإِيمَانِ، وَالْحَمْدُ لِلَّهِ تَمْلَأُ الْمِيزَانَ", "source": "رواه مسلم"},
    {"type": "حديث", "text": "مَنْ لَزِمَ الِاسْتِغْفَارَ جَعَلَ اللَّهُ لَهُ مِنْ كُلِّ ضِيقٍ مَخْرَجًا، وَمِنْ كُلِّ هَمٍّ فَرَجًا، وَرَزَقَهُ مِنْ حَيْثُ لَا يَحْتَسِبُ", "source": "رواه أبو داود"},

    # ---------- أدعية جامعة ----------
    {"type": "دعاء", "text": "اللَّهُمَّ إِنِّي أَسْأَلُكَ مِنْ خَيْرِ مَا سَأَلَكَ مِنْهُ نَبِيُّكَ مُحَمَّدٌ ﷺ، وَأَعُوذُ بِكَ مِنْ شَرِّ مَا اسْتَعَاذَكَ مِنْهُ نَبِيُّكَ مُحَمَّدٌ ﷺ", "source": "رواه الترمذي"},
    {"type": "دعاء", "text": "اللَّهُمَّ اهْدِنِي فِيمَنْ هَدَيْتَ، وَعَافِنِي فِيمَنْ عَافَيْتَ، وَتَوَلَّنِي فِيمَنْ تَوَلَّيْتَ", "source": "رواه أبو داود والترمذي"},
    {"type": "دعاء", "text": "اللَّهُمَّ رَبَّنَا لَكَ الْحَمْدُ مِلْءَ السَّمَاوَاتِ وَمِلْءَ الْأَرْضِ وَمِلْءَ مَا شِئْتَ مِنْ شَيْءٍ بَعْدُ", "source": "رواه مسلم"},
    {"type": "دعاء", "text": "اللَّهُمَّ لَا سَهْلَ إِلَّا مَا جَعَلْتَهُ سَهْلًا، وَأَنْتَ تَجْعَلُ الْحَزْنَ إِذَا شِئْتَ سَهْلًا", "source": "رواه ابن حبان"},
    {"type": "دعاء", "text": "اللَّهُمَّ إِنِّي أَسْأَلُكَ عِلْمًا نَافِعًا، وَرِزْقًا طَيِّبًا، وَعَمَلًا مُتَقَبَّلًا", "source": "رواه ابن ماجه"},
    {"type": "دعاء", "text": "اللَّهُمَّ اكْفِنِي بِحَلَالِكَ عَنْ حَرَامِكَ، وَأَغْنِنِي بِفَضْلِكَ عَمَّنْ سِوَاكَ", "source": "رواه الترمذي"},
    {"type": "دعاء", "text": "اللَّهُمَّ بَارِكْ لَنَا فِيمَا رَزَقْتَنَا، وَقِنَا عَذَابَ النَّارِ", "source": "دعاء مأثور"},
    {"type": "دعاء", "text": "اللَّهُمَّ أَحْسِنْ عَاقِبَتَنَا فِي الْأُمُورِ كُلِّهَا، وَأَجِرْنَا مِنْ خِزْيِ الدُّنْيَا وَعَذَابِ الْآخِرَةِ", "source": "رواه أحمد"},

    # ---------- تسابيح إضافية ----------
    {"type": "تسبيح", "text": "سُبْحَانَ اللَّهِ", "source": "من الباقيات الصالحات"},
    {"type": "تسبيح", "text": "الْحَمْدُ لِلَّهِ", "source": "من الباقيات الصالحات"},
    {"type": "تسبيح", "text": "لَا إِلَهَ إِلَّا اللَّهُ", "source": "أفضل الذكر"},
    {"type": "تسبيح", "text": "اللَّهُ أَكْبَرُ", "source": "من الباقيات الصالحات"},
    {"type": "ذكر", "text": "سُبْحَانَ اللَّهِ وَالْحَمْدُ لِلَّهِ وَلَا إِلَهَ إِلَّا اللَّهُ وَاللَّهُ أَكْبَرُ وَلَا حَوْلَ وَلَا قُوَّةَ إِلَّا بِاللَّهِ", "source": "الباقيات الصالحات"},

    # ---------- أدعية الفرج والهم ----------
    {"type": "دعاء", "text": "لَا إِلَهَ إِلَّا اللَّهُ الْعَظِيمُ الْحَلِيمُ، لَا إِلَهَ إِلَّا اللَّهُ رَبُّ الْعَرْشِ الْعَظِيمِ، لَا إِلَهَ إِلَّا اللَّهُ رَبُّ السَّمَاوَاتِ وَرَبُّ الْأَرْضِ وَرَبُّ الْعَرْشِ الْكَرِيمِ", "source": "دعاء الكرب — متفق عليه"},
    {"type": "دعاء", "text": "اللَّهُمَّ رَحْمَتَكَ أَرْجُو فَلَا تَكِلْنِي إِلَى نَفْسِي طَرْفَةَ عَيْنٍ، وَأَصْلِحْ لِي شَأْنِي كُلَّهُ، لَا إِلَهَ إِلَّا أَنْتَ", "source": "رواه أبو داود"},
    {"type": "دعاء", "text": "اللَّهُمَّ إِنِّي عَبْدُكَ، ابْنُ عَبْدِكَ، ابْنُ أَمَتِكَ، نَاصِيَتِي بِيَدِكَ، مَاضٍ فِيَّ حُكْمُكَ، عَدْلٌ فِيَّ قَضَاؤُكَ", "source": "رواه أحمد"},
    {"type": "دعاء", "text": "اللَّهُمَّ إِنِّي أَعُوذُ بِكَ مِنْ زَوَالِ نِعْمَتِكَ، وَتَحَوُّلِ عَافِيَتِكَ، وَفُجَاءَةِ نِقْمَتِكَ، وَجَمِيعِ سَخَطِكَ", "source": "رواه مسلم"},

    # ---------- ختام ----------
    {"type": "ذكر", "text": "اللَّهُمَّ صَلِّ وَسَلِّمْ وَبَارِكْ عَلَى سَيِّدِنَا مُحَمَّدٍ وَعَلَى آلِهِ وَصَحْبِهِ أَجْمَعِينَ", "source": "الصلاة على النبي ﷺ"},
    {"type": "آية", "text": "وَقُلِ الْحَمْدُ لِلَّهِ الَّذِي لَمْ يَتَّخِذْ وَلَدًا وَلَمْ يَكُنْ لَهُ شَرِيكٌ فِي الْمُلْكِ", "source": "سورة الإسراء: 111"},
    {"type": "دعاء", "text": "سُبْحَانَ رَبِّكَ رَبِّ الْعِزَّةِ عَمَّا يَصِفُونَ • وَسَلَامٌ عَلَى الْمُرْسَلِينَ • وَالْحَمْدُ لِلَّهِ رَبِّ الْعَالَمِينَ", "source": "سورة الصافات: 180-182"},
]


def brand_embed(title=None, description=None, color=None, *,
                thumb=True, banner=False, author=True, timestamp=True):
    """يبني embed أنيق موحّد الهوية لكل رسائل البوت."""
    em = discord.Embed(
        title=title,
        description=description,
        color=color if color is not None else BRAND_COLOR,
    )
    if author:
        em.set_author(name=f"◈ {BRAND_NAME} ◈",
                      icon_url=BRAND_ICON or discord.utils.MISSING)
    if thumb and BRAND_ICON:
        em.set_thumbnail(url=BRAND_ICON)
    if banner and BRAND_BANNER:
        em.set_image(url=BRAND_BANNER)
    if timestamp:
        em.timestamp = datetime.now(ZoneInfo(TIMEZONE))
    em.set_footer(text=f"{BRAND_NAME} • نظام الإدارة",
                  icon_url=BRAND_ICON or discord.utils.MISSING)
    return em


# ============================================================
#                     قاعدة البيانات
# ============================================================
_lock = threading.Lock()

def _conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

def init_db():
    with _lock, _conn() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS points(
            user_id TEXT PRIMARY KEY, username TEXT,
            weekly INTEGER DEFAULT 0, total INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS points_log(
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT,
            amount INTEGER, reason TEXT, created_at TEXT);
        CREATE TABLE IF NOT EXISTS vacations(
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT, username TEXT,
            reason TEXT, duration_hours REAL, start_at TEXT, end_at TEXT,
            active INTEGER DEFAULT 1, message_id TEXT);
        CREATE TABLE IF NOT EXISTS tickets(
            id INTEGER PRIMARY KEY AUTOINCREMENT, channel_id TEXT, owner_id TEXT,
            category TEXT, claimed_by TEXT, status TEXT DEFAULT 'open',
            rating INTEGER, created_at TEXT, closed_at TEXT,
            priority TEXT DEFAULT 'normal', transcript TEXT, owner_name TEXT);
        CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE IF NOT EXISTS promo_queue(
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT, count INTEGER,
            reason TEXT, processed INTEGER DEFAULT 0, created_at TEXT);
        CREATE TABLE IF NOT EXISTS vac_log(
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT, username TEXT,
            action TEXT, detail TEXT, at TEXT);
        """)
        # ترقية الجداول القديمة (لو ناقصة أعمدة)
        for col, ddl in [("priority", "ALTER TABLE tickets ADD COLUMN priority TEXT DEFAULT 'normal'"),
                         ("transcript", "ALTER TABLE tickets ADD COLUMN transcript TEXT"),
                         ("owner_name", "ALTER TABLE tickets ADD COLUMN owner_name TEXT"),
                         ("message_id", "ALTER TABLE vacations ADD COLUMN message_id TEXT")]:
            try:
                c.execute(ddl)
            except sqlite3.OperationalError:
                pass  # العمود موجود مسبقاً

def get_setting(key, default=None):
    with _lock, _conn() as c:
        r = c.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return r["value"] if r else default

def set_setting(key, value):
    with _lock, _conn() as c:
        c.execute("INSERT INTO settings(key,value) VALUES(?,?) "
                  "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, str(value)))

def is_bot_active():
    """هل البوت مفعّل؟ افتراضياً مطفي (0)."""
    return get_setting("bot_active", "0") == "1"

def set_bot_active(state: bool):
    set_setting("bot_active", "1" if state else "0")

def add_points(user_id, username, amount, reason=""):
    with _lock, _conn() as c:
        c.execute("INSERT INTO points(user_id,username,weekly,total) VALUES(?,?,?,?) "
                  "ON CONFLICT(user_id) DO UPDATE SET weekly=weekly+excluded.weekly, "
                  "total=total+excluded.total, username=excluded.username",
                  (str(user_id), username, amount, amount))
        c.execute("INSERT INTO points_log(user_id,amount,reason,created_at) VALUES(?,?,?,?)",
                  (str(user_id), amount, reason, datetime.utcnow().isoformat()))

def get_leaderboard(period="weekly", limit=100):
    col = "weekly" if period == "weekly" else "total"
    with _lock, _conn() as c:
        return [dict(r) for r in c.execute(
            f"SELECT user_id,username,weekly,total FROM points ORDER BY {col} DESC LIMIT ?",
            (limit,)).fetchall()]

def get_top_weekly():
    with _lock, _conn() as c:
        r = c.execute("SELECT user_id,username,weekly,total FROM points "
                      "WHERE weekly>0 ORDER BY weekly DESC LIMIT 1").fetchone()
        return dict(r) if r else None

def reset_weekly():
    with _lock, _conn() as c:
        c.execute("UPDATE points SET weekly=0")

def add_vacation(user_id, username, reason, hours, start_at, end_at, message_id=None):
    with _lock, _conn() as c:
        cur = c.execute("INSERT INTO vacations(user_id,username,reason,duration_hours,"
                        "start_at,end_at,active,message_id) VALUES(?,?,?,?,?,?,1,?)",
                        (str(user_id), username, reason, hours, start_at, end_at,
                         str(message_id) if message_id else None))
        return cur.lastrowid

def get_vacation_by_message(message_id):
    with _lock, _conn() as c:
        r = c.execute("SELECT * FROM vacations WHERE message_id=? AND active=1",
                      (str(message_id),)).fetchone()
        return dict(r) if r else None

def delete_vacation(vac_id):
    with _lock, _conn() as c:
        c.execute("DELETE FROM vacations WHERE id=?", (vac_id,))

def queue_promotion(user_id, count, reason):
    with _lock, _conn() as c:
        c.execute("INSERT INTO promo_queue(user_id,count,reason,processed,created_at) "
                  "VALUES(?,?,?,0,?)", (str(user_id), count, reason, datetime.utcnow().isoformat()))

def get_pending_promotions():
    with _lock, _conn() as c:
        return [dict(r) for r in c.execute(
            "SELECT * FROM promo_queue WHERE processed=0 ORDER BY id ASC").fetchall()]

def mark_promotion_done(pid):
    with _lock, _conn() as c:
        c.execute("UPDATE promo_queue SET processed=1 WHERE id=?", (pid,))

def add_vac_log(user_id, username, action, detail=""):
    with _lock, _conn() as c:
        c.execute("INSERT INTO vac_log(user_id,username,action,detail,at) VALUES(?,?,?,?,?)",
                  (str(user_id), username, action, detail, datetime.utcnow().isoformat()))

def get_vac_log(limit=100):
    with _lock, _conn() as c:
        return [dict(r) for r in c.execute(
            "SELECT * FROM vac_log ORDER BY id DESC LIMIT ?", (limit,)).fetchall()]

def get_last_vac_check():
    return get_setting("last_vac_check", None)

def set_last_vac_check(iso):
    set_setting("last_vac_check", iso)

def get_active_vacations():
    with _lock, _conn() as c:
        return [dict(r) for r in c.execute(
            "SELECT * FROM vacations WHERE active=1 ORDER BY end_at ASC").fetchall()]

def get_all_vacations(limit=200):
    """كل الإجازات (نشطة ومنتهية) — للوق الموقع."""
    with _lock, _conn() as c:
        return [dict(r) for r in c.execute(
            "SELECT * FROM vacations ORDER BY active DESC, start_at DESC LIMIT ?", (limit,)).fetchall()]

def get_expired_vacations(now_iso):
    with _lock, _conn() as c:
        return [dict(r) for r in c.execute(
            "SELECT * FROM vacations WHERE active=1 AND end_at<=?", (now_iso,)).fetchall()]

def deactivate_vacation(vid):
    with _lock, _conn() as c:
        c.execute("UPDATE vacations SET active=0 WHERE id=?", (vid,))

def update_vacation_duration(vid, new_end, new_hours):
    with _lock, _conn() as c:
        c.execute("UPDATE vacations SET end_at=?, duration_hours=? WHERE id=?",
                  (new_end, new_hours, vid))

def get_vacation(vid):
    with _lock, _conn() as c:
        r = c.execute("SELECT * FROM vacations WHERE id=?", (vid,)).fetchone()
        return dict(r) if r else None

def create_ticket(channel_id, owner_id, category, owner_name=None):
    with _lock, _conn() as c:
        cur = c.execute("INSERT INTO tickets(channel_id,owner_id,category,status,created_at,owner_name) "
                        "VALUES(?,?,?,'open',?,?)",
                        (str(channel_id), str(owner_id), category,
                         datetime.utcnow().isoformat(), owner_name))
        return cur.lastrowid

def set_ticket_priority(channel_id, priority):
    with _lock, _conn() as c:
        c.execute("UPDATE tickets SET priority=? WHERE channel_id=?", (priority, str(channel_id)))

def save_transcript(channel_id, html):
    with _lock, _conn() as c:
        c.execute("UPDATE tickets SET transcript=? WHERE channel_id=?", (html, str(channel_id)))

def get_ticket_by_id(ticket_id):
    with _lock, _conn() as c:
        r = c.execute("SELECT * FROM tickets WHERE id=?", (ticket_id,)).fetchone()
        return dict(r) if r else None

def get_all_tickets(limit=200):
    with _lock, _conn() as c:
        return [dict(r) for r in c.execute(
            "SELECT * FROM tickets ORDER BY id DESC LIMIT ?", (limit,)).fetchall()]

def get_late_unclaimed(cutoff_iso):
    """تكتات مفتوحة (غير مستلمة) أُنشئت قبل cutoff."""
    with _lock, _conn() as c:
        return [dict(r) for r in c.execute(
            "SELECT * FROM tickets WHERE status='open' AND created_at<=?", (cutoff_iso,)).fetchall()]

def get_ticket_stats():
    with _lock, _conn() as c:
        total = c.execute("SELECT COUNT(*) AS n FROM tickets").fetchone()["n"]
        open_n = c.execute("SELECT COUNT(*) AS n FROM tickets WHERE status IN ('open','claimed')").fetchone()["n"]
        closed_n = c.execute("SELECT COUNT(*) AS n FROM tickets WHERE status='closed'").fetchone()["n"]
        by_cat = [dict(r) for r in c.execute(
            "SELECT category, COUNT(*) AS n FROM tickets GROUP BY category ORDER BY n DESC").fetchall()]
        rated = c.execute("SELECT COUNT(*) AS n, AVG(rating) AS avg FROM tickets WHERE rating IS NOT NULL").fetchone()
        return {"total": total, "open": open_n, "closed": closed_n, "by_cat": by_cat,
                "rated_count": rated["n"], "avg_rating": rated["avg"]}


def claim_ticket(channel_id, claimed_by):
    with _lock, _conn() as c:
        c.execute("UPDATE tickets SET claimed_by=?, status='claimed' "
                  "WHERE channel_id=? AND status='open'", (str(claimed_by), str(channel_id)))
        r = c.execute("SELECT * FROM tickets WHERE channel_id=?", (str(channel_id),)).fetchone()
        return dict(r) if r else None

def get_ticket_by_channel(channel_id):
    with _lock, _conn() as c:
        r = c.execute("SELECT * FROM tickets WHERE channel_id=?", (str(channel_id),)).fetchone()
        return dict(r) if r else None

def close_ticket(channel_id, rating=None):
    with _lock, _conn() as c:
        c.execute("UPDATE tickets SET status='closed', rating=?, closed_at=? WHERE channel_id=?",
                  (rating, datetime.utcnow().isoformat(), str(channel_id)))

def set_ticket_rating(channel_id, rating):
    with _lock, _conn() as c:
        c.execute("UPDATE tickets SET rating=? WHERE channel_id=?", (rating, str(channel_id)))


def get_ratings_summary():
    """متوسط تقييم كل إداري + عدد التقييمات، مرتّب من الأعلى."""
    with _lock, _conn() as c:
        rows = c.execute(
            "SELECT claimed_by, COUNT(rating) AS cnt, AVG(rating) AS avg_r, "
            "SUM(rating) AS sum_r FROM tickets "
            "WHERE rating IS NOT NULL AND claimed_by IS NOT NULL "
            "GROUP BY claimed_by ORDER BY avg_r DESC, cnt DESC"
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            # اسم الإداري من جدول النقاط لو موجود
            u = c.execute("SELECT username FROM points WHERE user_id=?",
                          (d["claimed_by"],)).fetchone()
            d["username"] = u["username"] if u else d["claimed_by"]
            result.append(d)
        return result


def get_recent_ratings(limit=30):
    """آخر التقييمات الواصلة."""
    with _lock, _conn() as c:
        rows = c.execute(
            "SELECT claimed_by, category, rating, closed_at FROM tickets "
            "WHERE rating IS NOT NULL ORDER BY closed_at DESC LIMIT ?", (limit,)
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            u = c.execute("SELECT username FROM points WHERE user_id=?",
                          (d["claimed_by"],)).fetchone()
            d["username"] = u["username"] if u else (d["claimed_by"] or "—")
            result.append(d)
        return result


# ============================================================
#                         البوت
# ============================================================
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.voice_states = True
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

def is_admin(member: discord.Member) -> bool:
    return any(r.id == ADMIN_ROLE_ID for r in member.roles)

# كل قسم: roles = الرتب اللي تشوف التكت وتستلمه (غير صاحب التكت).
# roles=[] يعني كل الإدارة (ADMIN_ROLE_ID) تشوفه.
TICKET_CATEGORIES = [
    {"label": "استفسار",        "value": "ask",          "emoji": "📩", "desc": "استفسار أو شكوى",
     "roles": []},  # كل الإدارة
    {"label": "شكوى على إداري", "value": "complaint",    "emoji": "⚠️", "desc": "شكوى على اداري",
     "roles": [1527507454575771648]},
    {"label": "باند",           "value": "ban",          "emoji": "🔨", "desc": "اعتراض على باند",
     "roles": [1527507560251527190]},
    {"label": "تعويض",          "value": "compensation", "emoji": "💰", "desc": "طلب تعويض",
     "roles": [1527507587560374364]},
    {"label": "استراتيجي",      "value": "strategy",     "emoji": "📋", "desc": "طلب انشاء سيناريو",
     "roles": [1527507587560374364]},
    {"label": "متجر",           "value": "store",        "emoji": "🛒", "desc": "شراء من متجر",
     "roles": [1527507536113172500]},
    {"label": "النقل",          "value": "transport",    "emoji": "🚗", "desc": "طلب نقل",
     "roles": [1527507532237770872, 1527507543562256404]},
]
_cooldowns = {}


# ---------- التقييم (5 نجوم) ----------
class RatingView(ui.View):
    def __init__(self, channel_id, admin_id):
        super().__init__(timeout=86400)
        self.channel_id, self.admin_id = channel_id, admin_id

    async def _rate(self, interaction, stars):
        set_ticket_rating(self.channel_id, stars)
        if TICKET_LOG_CHANNEL_ID:
            ch = interaction.client.get_channel(TICKET_LOG_CHANNEL_ID)
            if ch:
                stars_bar = "🌟" * stars + "☆" * (5 - stars)
                em = brand_embed(
                    title="⭐ تقييم جديد لتكت",
                    description=(f"{DIVIDER}\n"
                                f"👨‍💼 **الإداري:** <@{self.admin_id}>\n"
                                f"📊 **التقييم:** {stars_bar}\n"
                                f"🔢 **الدرجة:** `{stars}/5`\n"
                                f"{DIVIDER}"),
                    color=COLOR_GOLD)
                await ch.send(embed=em)
        await interaction.response.edit_message(
            content=f"شكراً لك! تم تسجيل تقييمك: {'⭐'*stars} ({stars}/5)", view=None)

    @ui.button(label="1", style=discord.ButtonStyle.secondary, emoji="⭐")
    async def s1(self, i, b): await self._rate(i, 1)
    @ui.button(label="2", style=discord.ButtonStyle.secondary, emoji="⭐")
    async def s2(self, i, b): await self._rate(i, 2)
    @ui.button(label="3", style=discord.ButtonStyle.secondary, emoji="⭐")
    async def s3(self, i, b): await self._rate(i, 3)
    @ui.button(label="4", style=discord.ButtonStyle.secondary, emoji="⭐")
    async def s4(self, i, b): await self._rate(i, 4)
    @ui.button(label="5", style=discord.ButtonStyle.success, emoji="⭐")
    async def s5(self, i, b): await self._rate(i, 5)


# ---------- توليد النسخة الاحتياطية (Transcript) ----------
async def build_transcript(channel, ticket):
    """يبني HTML كامل لمحادثة التكت."""
    msgs = []
    try:
        async for m in channel.history(limit=500, oldest_first=True):
            ts = m.created_at.strftime("%Y-%m-%d %H:%M")
            content = discord.utils.escape_markdown(m.content or "")
            content = content.replace("<", "&lt;").replace(">", "&gt;") or "<i>[مرفق/إيموجي]</i>"
            atts = ""
            for a in m.attachments:
                atts += f'<div class="att">📎 <a href="{a.url}">{a.filename}</a></div>'
            author = discord.utils.escape_markdown(str(m.author))
            avatar = m.author.display_avatar.url
            msgs.append(f'''<div class="msg"><img class="av" src="{avatar}">
<div class="body"><div class="head"><span class="name">{author}</span>
<span class="time">{ts}</span></div><div class="text">{content}{atts}</div></div></div>''')
    except Exception:
        pass
    rows = "\n".join(msgs) or '<p class="empty">لا توجد رسائل.</p>'
    cat = ticket.get("category", "—")
    owner = ticket.get("owner_name") or ticket.get("owner_id", "—")
    return rows, cat, owner


# ---------- أزرار التكت ----------
class TicketControlView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="استلام", style=discord.ButtonStyle.success,
               emoji="✋", custom_id="nt_ticket_claim", row=0)
    async def claim(self, interaction, button):
        ticket0 = get_ticket_by_channel(interaction.channel.id)
        if ticket0 and str(interaction.user.id) == str(ticket0.get("owner_id")):
            return await interaction.response.send_message(
                "❌ لا يمكنك استلام تذكرتك الخاصة.", ephemeral=True)
        ticket = claim_ticket(interaction.channel.id, interaction.user.id)
        if not ticket or ticket.get("claimed_by") != str(interaction.user.id):
            return await interaction.response.send_message("⚠️ هذا التكت مستلم مسبقاً.", ephemeral=True)
        add_points(interaction.user.id, str(interaction.user), POINTS_TICKET_CLAIM, "استلام تكت")
        em = brand_embed(
            title="✋ تم استلام التذكرة",
            description=(f"{DIVIDER}\n"
                        f"👨‍💼 **الإداري المستلم:** {interaction.user.mention}\n"
                        f"💎 **النقاط المضافة:** `+{POINTS_TICKET_CLAIM}`\n"
                        f"📌 **الحالة:** قيد المعالجة الآن\n"
                        f"{DIVIDER}"),
            color=COLOR_SUCCESS)
        await interaction.response.send_message(embed=em)

    @ui.button(label="استدعاء العضو", style=discord.ButtonStyle.secondary,
               emoji="🔔", custom_id="nt_ticket_call", row=0)
    async def call_user(self, interaction, button):
        ticket = get_ticket_by_channel(interaction.channel.id)
        if not ticket:
            return await interaction.response.send_message("⚠️ تكت غير معروف.", ephemeral=True)
        await interaction.response.send_message(
            f"🔔 <@{ticket['owner_id']}> يرجى الرد، الإدارة بانتظارك.")

    @ui.button(label="إضافة عضو", style=discord.ButtonStyle.secondary,
               emoji="👥", custom_id="nt_ticket_add", row=0)
    async def add_member(self, interaction, button):
        if not is_admin(interaction.user):
            return await interaction.response.send_message("❌ للإداريين فقط.", ephemeral=True)
        await interaction.response.send_modal(AddMemberModal(interaction.channel))

    @ui.button(label="الأولوية", style=discord.ButtonStyle.secondary,
               emoji="📌", custom_id="nt_ticket_priority", row=1)
    async def priority(self, interaction, button):
        if not is_admin(interaction.user):
            return await interaction.response.send_message("❌ للإداريين فقط.", ephemeral=True)
        await interaction.response.send_message(
            "اختر أولوية التذكرة:", view=PriorityView(interaction.channel.id), ephemeral=True)

    @ui.button(label="قفل/فتح", style=discord.ButtonStyle.secondary,
               emoji="🔐", custom_id="nt_ticket_lock", row=1)
    async def lock(self, interaction, button):
        if not is_admin(interaction.user):
            return await interaction.response.send_message("❌ للإداريين فقط.", ephemeral=True)
        ticket = get_ticket_by_channel(interaction.channel.id)
        if not (ticket and ticket.get("owner_id")):
            return await interaction.response.send_message("⚠️ تكت غير معروف.", ephemeral=True)
        member = interaction.guild.get_member(int(ticket["owner_id"]))
        if not member:
            return await interaction.response.send_message("⚠️ صاحب التكت غير موجود.", ephemeral=True)
        # اقرأ الحالة الحالية للصلاحية
        ow = interaction.channel.overwrites_for(member)
        currently_locked = ow.send_messages is False
        if currently_locked:
            await interaction.channel.set_permissions(member, view_channel=True, send_messages=True)
            em = brand_embed(title="🔓 تم فتح التذكرة",
                             description="يستطيع العضو الكتابة الآن.", color=COLOR_SUCCESS)
        else:
            await interaction.channel.set_permissions(member, view_channel=True, send_messages=False)
            em = brand_embed(title="🔐 تم قفل التذكرة",
                             description="العضو لا يستطيع الكتابة مؤقتاً.", color=COLOR_GOLD)
        await interaction.response.send_message(embed=em)

    @ui.button(label="إغلاق", style=discord.ButtonStyle.danger,
               emoji="🔒", custom_id="nt_ticket_close", row=1)
    async def close(self, interaction, button):
        ticket = get_ticket_by_channel(interaction.channel.id)
        # صاحب التكت والمختص كلاهما يقدر يغلق
        await interaction.response.send_message("🔒 يتم حفظ النسخة الاحتياطية وإغلاق التكت...")

        # احفظ النسخة الاحتياطية في قاعدة البيانات (للموقع)
        if ticket:
            try:
                rows, cat, owner = await build_transcript(interaction.channel, ticket)
                save_transcript(interaction.channel.id, rows)
            except Exception:
                pass

        close_ticket(interaction.channel.id)

        # تقييم بالخاص للعضو
        if ticket and ticket.get("claimed_by") and ticket.get("owner_id"):
            try:
                owner_user = await interaction.client.fetch_user(int(ticket["owner_id"]))
                em = brand_embed(
                    title="⭐ قيّم تجربتك معنا",
                    description=(f"{DIVIDER}\n"
                                f"شكراً لتواصلك مع فريق **{BRAND_NAME}** 💙\n\n"
                                f"كيف كانت خدمة الإداري في تذكرتك؟\n"
                                f"اختر تقييمك من ⭐ إلى 🌟🌟🌟🌟🌟\n"
                                f"{DIVIDER}"),
                    color=COLOR_GOLD, banner=True)
                await owner_user.send(embed=em, view=RatingView(ticket["channel_id"], ticket["claimed_by"]))
            except discord.Forbidden:
                pass
        await asyncio.sleep(5)
        try:
            await interaction.channel.delete()
        except discord.HTTPException:
            pass


class AddMemberModal(ui.Modal, title="إضافة عضو للتذكرة"):
    user_id = ui.TextInput(label="ID العضو", placeholder="مثال: 123456789012345678")

    def __init__(self, channel):
        super().__init__()
        self.channel = channel

    async def on_submit(self, interaction):
        try:
            member = interaction.guild.get_member(int(str(self.user_id).strip()))
            if not member:
                return await interaction.response.send_message("⚠️ لم أجد العضو.", ephemeral=True)
            await self.channel.set_permissions(member, view_channel=True, send_messages=True)
            await interaction.response.send_message(f"✅ تم إضافة {member.mention} للتذكرة.")
        except ValueError:
            await interaction.response.send_message("⚠️ ID غير صحيح.", ephemeral=True)


class PriorityView(ui.View):
    def __init__(self, channel_id):
        super().__init__(timeout=60)
        self.channel_id = channel_id

    async def _set(self, interaction, level, label, color):
        set_ticket_priority(self.channel_id, level)
        ch = interaction.client.get_channel(int(self.channel_id))
        # جدّد اسم الروم بعلامة الأولوية
        if ch:
            prio_emoji = {"normal": "", "important": "🟡", "urgent": "🔴"}.get(level, "")
            base = ch.name
            # شِل أي علامة أولوية قديمة من البداية
            base = re.sub(r'^[🔴🟡]', '', base)
            new_name = f"{prio_emoji}{base}" if prio_emoji else base
            try:
                await ch.edit(name=new_name[:100])
            except discord.HTTPException:
                pass
        em = brand_embed(title=f"📌 الأولوية: {label}",
                         description=f"تم تحديد أولوية التذكرة كـ **{label}**.", color=color)
        await interaction.response.edit_message(content=None, embed=em, view=None)
        if ch:
            await ch.send(embed=em)

    @ui.button(label="عادي", style=discord.ButtonStyle.secondary, emoji="🟢")
    async def normal(self, i, b): await self._set(i, "normal", "عادي 🟢", COLOR_SUCCESS)
    @ui.button(label="مهم", style=discord.ButtonStyle.primary, emoji="🟡")
    async def important(self, i, b): await self._set(i, "important", "مهم 🟡", COLOR_GOLD)
    @ui.button(label="عاجل", style=discord.ButtonStyle.danger, emoji="🔴")
    async def urgent(self, i, b): await self._set(i, "urgent", "عاجل 🔴", COLOR_DANGER)


class TicketSelect(ui.Select):
    def __init__(self):
        options = [discord.SelectOption(label=c["label"], value=c["value"],
                   description=c["desc"], emoji=c["emoji"]) for c in TICKET_CATEGORIES]
        super().__init__(placeholder="اختر قسم التكت", options=options,
                         custom_id="nt_ticket_select", min_values=1, max_values=1)

    async def callback(self, interaction):
        if not is_bot_active():
            return await interaction.response.send_message(
                "⚠️ النظام متوقف حالياً. يرجى المحاولة لاحقاً.", ephemeral=True)
        user = interaction.user
        now = time.time()
        if now - _cooldowns.get(user.id, 0) < TICKET_COOLDOWN_SECONDS:
            wait = int(TICKET_COOLDOWN_SECONDS - (now - _cooldowns.get(user.id, 0)))
            return await interaction.response.send_message(
                f"⏳ لمنع السبام، انتظر {wait} ثانية قبل فتح تكت جديد.", ephemeral=True)
        cat = next(c for c in TICKET_CATEGORIES if c["value"] == self.values[0])
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            user: discord.PermissionOverwrite(view_channel=True, send_messages=True,
                                              attach_files=True, embed_links=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True),
        }
        # حدّد الرتب اللي تشوف هذا القسم: لو roles فاضية → كل الإدارة، وإلا الرتب المحددة فقط
        allowed_roles = []
        if cat.get("roles"):
            allowed_roles = [guild.get_role(rid) for rid in cat["roles"]]
        else:
            allowed_roles = [guild.get_role(ADMIN_ROLE_ID)]
        allowed_roles = [r for r in allowed_roles if r]
        for r in allowed_roles:
            overwrites[r] = discord.PermissionOverwrite(view_channel=True, send_messages=True)

        # منشن الرتب المسؤولة عن القسم
        ping_roles = " ".join(r.mention for r in allowed_roles)

        # اسم الروم: إيموجي القسم + اسم العضو (منظّف)
        clean_name = re.sub(r'[^0-9a-zA-Z\u0600-\u06FF]+', '-', user.display_name).strip('-').lower()
        clean_name = clean_name[:20] or "member"
        cat_emoji = {"ask": "📩", "complaint": "⚠️", "ban": "🔨",
                     "compensation": "💰", "strategy": "📋", "store": "🛒",
                     "transport": "🚗"}.get(cat["value"], "🎫")
        category_obj = guild.get_channel(TICKET_CATEGORY_ID) if TICKET_CATEGORY_ID else None
        channel = await guild.create_text_channel(name=f"{cat_emoji}・{cat['label']}・{clean_name}",
                    overwrites=overwrites, category=category_obj,
                    topic=f"تذكرة {cat['label']} — صاحبها {user} ({user.id})")
        _cooldowns[user.id] = now
        create_ticket(channel.id, user.id, cat["label"], str(user))
        _logo = TICKET_LOGO or BRAND_ICON
        em = brand_embed(
            title=f"{cat['emoji']} تذكرة {cat['label']}",
            description=(f"{DIVIDER}\n"
                        f"مرحباً {user.mention} 👋\n\n"
                        f"📝 اشرح مشكلتك أو طلبك بشكل **واضح ومختصر**.\n"
                        f"⏳ سيتم الرد عليك في أقرب وقت.\n"
                        f"👨‍💼 سيقوم أحد المختصين باستلام تذكرتك قريباً.\n"
                        f"{DIVIDER}\n"
                        f"🗂️ **القسم:** {cat['label']}"),
            color=BRAND_COLOR, thumb=False)
        if _logo:
            em.set_thumbnail(url=_logo)   # شعار NT كبير جنب النص
        em.set_footer(text=f"{BRAND_NAME} • رقم صاحب التذكرة: {user.id}",
                      icon_url=_logo or discord.utils.MISSING)
        await channel.send(content=f"{user.mention} {ping_roles}",
                           embed=em, view=TicketControlView())
        await interaction.followup.send(f"✅ تم فتح تكتك: {channel.mention}", ephemeral=True)
        try:
            await interaction.message.edit(view=TicketPanelView())
        except discord.HTTPException:
            pass


class TicketPanelView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketSelect())
        self.add_item(FAQButton())


class FAQButton(ui.Button):
    def __init__(self):
        super().__init__(label="الأسئلة الشائعة", style=discord.ButtonStyle.secondary,
                         emoji="❓", custom_id="nt_faq_btn", row=1)

    async def callback(self, interaction):
        em = brand_embed(
            title="❓ الأسئلة الشائعة — Nova Town",
            description=(f"{DIVIDER}\n"
                        f"**1️⃣ هل النقل فاتح؟**\n"
                        f"↳ نعم ✅ ويرجى التواصل مع الإدارة العليا.\n\n"
                        f"**2️⃣ كيف أدخل السيرفر؟**\n"
                        f"↳ اكتب الاسم في فايف إم، أو توجّه إلى الروم التالي:\n"
                        f"<#{FAQ_JOIN_CHANNEL_ID}>\n"
                        f"{DIVIDER}\n"
                        f"💡 لو ما لقيت إجابتك، افتح تذكرة من القائمة بالأعلى."),
            color=BRAND_COLOR)
        await interaction.response.send_message(embed=em, ephemeral=True)


# ---------- لوحة تحكم المالك (تشغيل/إطفاء) ----------
async def publish_ticket_panel(guild):
    """ينشر لوحة التكتات في روم البانل. يرجّع True لو نجح."""
    channel = guild.get_channel(TICKET_PANEL_CHANNEL_ID)
    if not channel:
        return False
    em = brand_embed(
        title="🎫 نظام التذاكر — Nova Town",
        description=(f"{DIVIDER}\n"
            "مرحباً بك في **قسم التذاكر** 💙\n"
            "يرجى اختيار القسم المناسب قبل فتح التذكرة لضمان سرعة معالجة طلبك.\n\n"
            "⚠️ **تعليمات مهمة:**\n"
            "> ◈ يمنع فتح أكثر من تذكرة لنفس المشكلة أو الطلب.\n"
            "> ◈ احرص على احترام الطاقم الإداري والتحدث بأسلوب لائق.\n"
            "> ◈ اشرح مشكلتك أو طلبك بشكل واضح ومختصر.\n"
            "> ◈ يمنع منشن الإدارة أو إرسال رسائل متكررة داخل التذكرة.\n"
            "> ◈ يمنع إدخال أي شخص إلى التذكرة إلا بإذن من الإدارة.\n"
            "> ◈ يرجى التحلي بالصبر، وسيتم الرد حسب أولوية الطلبات.\n\n"
            f"{DIVIDER}\n"
            "📌 **اختر القسم من القائمة بالأسفل لإنشاء تذكرتك.**"),
        color=BRAND_COLOR, banner=True)
    await channel.send(embed=em, view=TicketPanelView())
    return True


class ControlPanelView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def interaction_check(self, interaction):
        if interaction.user.id != OWNER_ID:
            await interaction.response.send_message("❌ هذه اللوحة للمالك فقط.", ephemeral=True)
            return False
        return True

    @ui.button(label="تشغيل", style=discord.ButtonStyle.success,
               emoji="🟢", custom_id="nt_ctrl_on")
    async def turn_on(self, interaction, button):
        already = is_bot_active()
        set_bot_active(True)
        # فعّل حضور البوت
        try:
            await bot.change_presence(status=discord.Status.online,
                activity=discord.Activity(type=discord.ActivityType.watching, name="Nova Town 💙"))
        except Exception:
            pass
        published = False
        # انشر لوحة التكتات في كل السيرفرات
        for g in bot.guilds:
            if await publish_ticket_panel(g):
                published = True
        msg = "✅ تم **تشغيل** البوت وتفعيل كل الأنظمة."
        if published:
            msg += "\n🎫 تم نشر لوحة التكتات."
        else:
            msg += "\n⚠️ ما قدرت أنشر لوحة التكتات (تأكد من TICKET_PANEL_CHANNEL_ID)."
        if already:
            msg = "ℹ️ البوت مُشغّل مسبقاً. أعدت نشر لوحة التكتات."
        em = brand_embed(title="🟢 البوت يعمل الآن", description=msg, color=COLOR_SUCCESS)
        await interaction.response.edit_message(embed=em, view=ControlPanelView())

    @ui.button(label="إطفاء", style=discord.ButtonStyle.danger,
               emoji="🔴", custom_id="nt_ctrl_off")
    async def turn_off(self, interaction, button):
        set_bot_active(False)
        try:
            await bot.change_presence(status=discord.Status.idle,
                activity=discord.Activity(type=discord.ActivityType.watching, name="مطفأ — بانتظار التشغيل"))
        except Exception:
            pass
        em = brand_embed(
            title="🔴 تم إطفاء البوت",
            description=(f"{DIVIDER}\n"
                        "توقّفت كل الأنظمة (تكتات، ويتينق، ترحيب، إجازات، ترقيات).\n"
                        "البوت لا يزال متصلاً لكنه صامت.\n\n"
                        "أرسل لي أي رسالة بالخاص لإعادة فتح لوحة التحكم.\n"
                        f"{DIVIDER}"),
            color=COLOR_DANGER)
        await interaction.response.edit_message(embed=em, view=ControlPanelView())


# ---------- الويتينق ----------
class DoneView(ui.View):
    def __init__(self, target_user_id):
        super().__init__(timeout=None)
        self.target_user_id = target_user_id

    @ui.button(label="تم الانتهاء", style=discord.ButtonStyle.success,
               emoji="✅", custom_id="nt_wait_done")
    async def done(self, interaction, button):
        if not is_admin(interaction.user):
            return await interaction.response.send_message("❌ هذا الزر للإداريين فقط.", ephemeral=True)
        guild = interaction.guild
        member = guild.get_member(self.target_user_id)
        done_channel = guild.get_channel(DONE_CHANNEL_ID)
        if not member:
            return await interaction.response.send_message("⚠️ الشخص لم يعد في السيرفر.", ephemeral=True)
        if not (done_channel and isinstance(done_channel, discord.VoiceChannel)):
            return await interaction.response.send_message("⚠️ روم Done غير موجود أو ليس صوتياً.", ephemeral=True)
        try:
            await member.move_to(done_channel)
            button.disabled = True
            button.label = "تم الانتهاء ✓"
            await interaction.response.edit_message(view=self)
            await interaction.followup.send(f"✅ تم نقل {member.mention} إلى روم Done.", ephemeral=True)
        except discord.HTTPException as e:
            await interaction.response.send_message(f"⚠️ تعذّر النقل: {e}", ephemeral=True)


class ClaimWaitingView(ui.View):
    def __init__(self, target_user_id):
        super().__init__(timeout=None)
        self.target_user_id = target_user_id
        self.claimed = False

    @ui.button(label="استلام", style=discord.ButtonStyle.primary,
               emoji="📥", custom_id="nt_wait_claim")
    async def claim(self, interaction, button):
        if not is_admin(interaction.user):
            return await interaction.response.send_message("❌ هذا الزر للإداريين فقط.", ephemeral=True)
        if self.claimed:
            return await interaction.response.send_message("⚠️ تم استلام هذا الشخص مسبقاً.", ephemeral=True)
        guild = interaction.guild
        member = guild.get_member(self.target_user_id)
        if not member or not member.voice:
            return await interaction.response.send_message("⚠️ الشخص لم يعد في الويتينق.", ephemeral=True)
        if not interaction.user.voice or not interaction.user.voice.channel:
            return await interaction.response.send_message("⚠️ ادخل روم صوتي أولاً حتى أسحب الشخص لك.", ephemeral=True)
        admin_channel = interaction.user.voice.channel
        try:
            await member.move_to(admin_channel)
        except discord.HTTPException as e:
            return await interaction.response.send_message(f"⚠️ تعذّر السحب: {e}", ephemeral=True)
        self.claimed = True
        add_points(interaction.user.id, str(interaction.user), POINTS_WAITING_PULL, "سحب من الويتينق")
        button.disabled = True
        button.label = f"مستلم — {interaction.user.display_name}"
        await interaction.response.edit_message(view=self)
        await interaction.followup.send(
            f"✅ تم سحب {member.mention} إلى {admin_channel.mention}\n➕ {POINTS_WAITING_PULL} نقاط",
            ephemeral=True)
        try:
            em = brand_embed(
                title="📥 تم استلامك من الويتينق",
                description=(f"{DIVIDER}\n"
                            f"مرحباً {member.mention} 👋\n\n"
                            f"👨‍💼 **الإداري:** {interaction.user.mention}\n"
                            f"🔊 **تم سحبك إلى:** {admin_channel.mention}\n\n"
                            f"✅ عند انتهاء معاملتك سيضغط الإداري زر **تم الانتهاء** "
                            f"لنقلك إلى روم Done.\n\n"
                            f"شكراً لتعاونك معنا 💙\n"
                            f"{DIVIDER}"),
                color=COLOR_SUCCESS, banner=True)
            await member.send(embed=em)
        except discord.Forbidden:
            pass
        em2 = brand_embed(
            title="🛠️ جلسة استلام نشطة",
            description=(f"{DIVIDER}\n"
                        f"👤 **الشخص:** {member.mention}\n"
                        f"👨‍💼 **الإداري:** {interaction.user.mention}\n"
                        f"💎 **النقاط:** `+{POINTS_WAITING_PULL}`\n\n"
                        f"اضغط **تم الانتهاء** عند إنهاء المعاملة لنقله لروم Done.\n"
                        f"{DIVIDER}"),
            color=BRAND_COLOR)
        await interaction.channel.send(embed=em2, view=DoneView(member.id))


# ---------- المدة والنماذج ----------
def parse_duration_to_hours(text):
    text = (text or "").strip().lower()
    # الأرقام المكتوبة بالحروف (عربي) → قيمة
    words_num = {
        "نص": 0.5, "نصف": 0.5,
        "وحدة": 1, "واحد": 1, "واحده": 1, "يوم": 1, "ساعه": 1, "ساعة": 1, "اسبوع": 1, "أسبوع": 1,
        "ثلاث": 3, "ثلاثة": 3, "ثلاثه": 3,
        "اربع": 4, "أربع": 4, "اربعة": 4, "اربعه": 4,
        "خمس": 5, "خمسة": 5, "خمسه": 5,
        "ست": 6, "ستة": 6, "سته": 6,
        "سبع": 7, "سبعة": 7, "سبعه": 7,
        "ثمان": 8, "ثمانية": 8, "ثمانيه": 8,
        "تسع": 9, "تسعة": 9, "تسعه": 9,
        "عشر": 10, "عشرة": 10, "عشره": 10,
    }
    # هل فيه رقم صريح؟
    m = re.search(r"(\d+(?:\.\d+)?)", text)
    # صيغة المثنى (يومين، ساعتين، اسبوعين) = 2
    is_dual = any(d in text for d in ("يومين", "ساعتين", "اسبوعين", "أسبوعين", "يومان", "ساعتان"))

    if m:
        num = float(m.group(1))
    elif is_dual:
        num = 2.0
    else:
        # ابحث عن رقم مكتوب بالحروف
        num = None
        for w, val in words_num.items():
            if w in text and val not in (1,):  # تجاهل كلمات الوحدات نفسها مؤقتاً
                num = val; break
        if num is None:
            num = 1.0

    # حدّد الوحدة
    if any(w in text for w in ("اسبوع", "أسبوع", "week")):
        return num * 168
    if any(w in text for w in ("ساعة", "ساعات", "ساعه", "ساعت", "hour")):
        return num
    if any(w in text for w in ("يوم", "ايام", "أيام", "day")):
        return num * 24
    return num * 24  # افتراضي: أيام

def _clean_field(text):
    """ينظّف قيمة حقل: يشيل النجوم والرموز الزائدة والمسافات والنقطتين الزائدة."""
    if not text:
        return "—"
    text = text.strip().strip("*").strip().strip("`").strip().lstrip(":").strip()
    text = re.split(r"\s*\**(?:Reason|Duration|Requirements|Name|From|To|By|Count)\**\s*:",
                    text, flags=re.I)[0]
    return text.strip().strip("*").strip() or "—"

def parse_vacation_form(content):
    d = {}
    m = re.search(r"Name\s*:\s*<@!?(\d+)>", content, re.I); d["user_id"] = m.group(1) if m else None
    m = (re.search(r"Duration\**\s*:?\s*([^\n]+)", content, re.I)
         or re.search(r"(?:Requirements|المدة)\**\s*:?\s*([^\n]+)", content, re.I))
    d["duration_raw"] = _clean_field(m.group(1)) if m else None
    m = re.search(r"Reason\**\s*:?\s*([^\n]+)", content, re.I)
    d["reason"] = _clean_field(m.group(1)) if m else "—"
    return d

def parse_promo_form(content):
    d = {}
    m = re.search(r"Name\s*:\s*<@!?(\d+)>", content, re.I); d["user_id"] = m.group(1) if m else None
    m = re.search(r"From\s*:\s*<@&(\d+)>", content, re.I); d["from_role"] = m.group(1) if m else None
    m = re.search(r"To\s*:\s*<@&(\d+)>", content, re.I); d["to_role"] = m.group(1) if m else None
    m = re.search(r"Reason\**\s*:?\s*([^\n]+)", content, re.I)
    d["reason"] = _clean_field(m.group(1)) if m else "—"
    m = re.search(r"Count\**\s*:?\s*(\d+)", content, re.I); d["count"] = int(m.group(1)) if m else 1
    return d


def ladder_index(role_id):
    """يرجّع موقع الرتبة في السلم (0=الأدنى) أو None لو مو موجودة."""
    for i, r in enumerate(ROLE_LADDER):
        if r["id"] and str(r["id"]) == str(role_id):
            return i
    return None


async def apply_promotion(guild, member, from_role_id, count):
    """يرقّي العضو (count) درجات فوق from_role في السلم. يرجّع (نجاح, رتبة_جديدة_id)."""
    idx = ladder_index(from_role_id)
    if idx is None:
        return False, None
    new_idx = min(idx + max(1, count), len(ROLE_LADDER) - 1)
    new_role_id = ROLE_LADDER[new_idx]["id"]
    if not new_role_id:
        return False, None
    old_role = guild.get_role(int(from_role_id))
    new_role = guild.get_role(int(new_role_id))
    try:
        if old_role and old_role in member.roles:
            await member.remove_roles(old_role, reason="ترقية")
        if new_role:
            await member.add_roles(new_role, reason="ترقية")
        return True, new_role_id
    except discord.Forbidden:
        return False, new_role_id


# ---------- الأحداث والأوامر ----------
@bot.event
async def on_ready():
    bot.add_view(TicketPanelView())
    bot.add_view(TicketControlView())
    bot.add_view(ControlPanelView())
    # اضبط الحضور حسب الحالة المحفوظة (افتراضياً مطفأ)
    try:
        if is_bot_active():
            await bot.change_presence(status=discord.Status.online,
                activity=discord.Activity(type=discord.ActivityType.watching, name="Nova Town 💙"))
        else:
            await bot.change_presence(status=discord.Status.idle,
                activity=discord.Activity(type=discord.ActivityType.watching, name="مطفأ — بانتظار التشغيل"))
    except Exception:
        pass
    state = "🟢 مُشغّل" if is_bot_active() else "🔴 مُطفأ (أرسل رسالة خاصة للمالك للتحكم)"
    print(f"✅ {bot.user} جاهز! متصل بـ {len(bot.guilds)} سيرفر. الحالة: {state}")
    if not check_vacations.is_running(): check_vacations.start()
    if not aow_tick.is_running(): aow_tick.start()
    if not late_ticket_check.is_running(): late_ticket_check.start()
    if not athkar_loop.is_running(): athkar_loop.start()
    if not promo_queue_check.is_running(): promo_queue_check.start()


@bot.event
async def on_member_join(member: discord.Member):
    if member.bot or not is_bot_active():
        return
    channel = member.guild.get_channel(WELCOME_CHANNEL_ID)
    if not channel:
        return

    guild = member.guild
    count = guild.member_count
    created = member.created_at
    account_age_days = (datetime.now(created.tzinfo) - created).days
    # علامة توثيق: الحساب أقدم من 7 أيام
    verified = "✅ موثّق" if account_age_days >= 7 else "⚠️ حساب جديد"
    _logo = TICKET_LOGO or BRAND_ICON

    em = discord.Embed(
        title=f"💙 Welcome To {BRAND_NAME}",
        description=(f"{DIVIDER}\n"
                    f"نورت السيرفر {member.mention} 🎉\n"
                    f"{DIVIDER}"),
        color=BRAND_COLOR,
    )
    em.set_author(name=f"◈ {BRAND_NAME} • Welcome ◈",
                  icon_url=_logo or discord.utils.MISSING)
    em.set_thumbnail(url=member.display_avatar.url)
    em.add_field(name="👤 العضو", value=member.mention, inline=True)
    em.add_field(name="📊 عدد الأعضاء", value=f"`{count}`", inline=True)
    em.add_field(name="🆔 الايدي", value=f"`{member.id}`", inline=True)
    em.add_field(name="🎂 عمر الحساب",
                 value=f"{verified}\n<t:{int(created.timestamp())}:R>", inline=True)
    em.add_field(name="📅 تاريخ الانضمام",
                 value=f"<t:{int(datetime.now().timestamp())}:F>", inline=True)
    em.add_field(name="🔗 السيرفر", value=f"**{guild.name}**", inline=True)
    if WELCOME_BANNER:
        em.set_image(url=WELCOME_BANNER)
    elif BRAND_BANNER:
        em.set_image(url=BRAND_BANNER)
    em.set_footer(text=f"{BRAND_NAME} • Welcome System",
                  icon_url=_logo or discord.utils.MISSING)
    em.timestamp = datetime.now(ZoneInfo(TIMEZONE))

    await channel.send(content=member.mention, embed=em)


@bot.command(name="panel")
@commands.has_permissions(administrator=True)
async def panel(ctx):
    em = brand_embed(
        title="🎫 نظام التذاكر — Nova Town",
        description=(f"{DIVIDER}\n"
            "مرحباً بك في **قسم التذاكر** 💙\n"
            "يرجى اختيار القسم المناسب قبل فتح التذكرة لضمان سرعة معالجة طلبك.\n\n"
            "⚠️ **تعليمات مهمة:**\n"
            "> ◈ يمنع فتح أكثر من تذكرة لنفس المشكلة أو الطلب.\n"
            "> ◈ احرص على احترام الطاقم الإداري والتحدث بأسلوب لائق.\n"
            "> ◈ اشرح مشكلتك أو طلبك بشكل واضح ومختصر.\n"
            "> ◈ يمنع منشن الإدارة أو إرسال رسائل متكررة داخل التذكرة.\n"
            "> ◈ يمنع إدخال أي شخص إلى التذكرة إلا بإذن من الإدارة.\n"
            "> ◈ يرجى التحلي بالصبر، وسيتم الرد حسب أولوية الطلبات.\n\n"
            f"{DIVIDER}\n"
            "📌 **اختر القسم من القائمة بالأسفل لإنشاء تذكرتك.**"),
        color=BRAND_COLOR, banner=True)
    await ctx.send(embed=em, view=TicketPanelView())
    try: await ctx.message.delete()
    except discord.HTTPException: pass


@bot.command(name="testwelcome")
@commands.has_permissions(administrator=True)
async def testwelcome(ctx):
    """يجرّب رسالة الترحيب عليك (للمعاينة)."""
    await on_member_join(ctx.author)
    try: await ctx.message.delete()
    except discord.HTTPException: pass


@bot.command(name="thikr")
@commands.has_permissions(administrator=True)
async def thikr(ctx):
    """يرسل ذكراً الآن في روم الأذكار (تجربة)."""
    prev = is_bot_active()
    if not prev:
        set_bot_active(True)
    await athkar_loop()
    if not prev:
        set_bot_active(False)
    try: await ctx.message.delete()
    except discord.HTTPException: pass


@bot.command(name="ladder")
async def ladder(ctx):
    """يعرض سلم الرتب بالترتيب من الأعلى للأسفل."""
    total = len(ROLE_LADDER)
    lines = []
    for i, r in enumerate(reversed(ROLE_LADDER), 1):
        rank_num = total - i + 1
        tag = f"<@&{r['id']}>" if r["id"] else f"**{r['name']}**"
        medal = "👑" if i == 1 else ("💠" if rank_num > total - 5 else "🔹")
        lines.append(f"{medal} `{rank_num:>2}` ─ {tag}")
    em = brand_embed(
        title="🪜 سلم الرتب — Nova Town",
        description=f"{DIVIDER}\n" + "\n".join(lines) + f"\n{DIVIDER}",
        color=COLOR_PURPLE, banner=True)
    await ctx.send(embed=em)


@bot.event
async def on_voice_state_update(member, before, after):
    if not is_bot_active():
        return
    joined = (after.channel and after.channel.id == WAITING_CHANNEL_ID
              and (not before.channel or before.channel.id != WAITING_CHANNEL_ID))
    if not joined or member.bot:
        return
    guild = member.guild
    admin_role = guild.get_role(ADMIN_ROLE_ID)
    # روم الإشعارات المحدد
    notify = guild.get_channel(WAITING_NOTIFY_CHANNEL_ID) if WAITING_NOTIFY_CHANNEL_ID else None
    if notify is None:
        for ch in guild.text_channels:
            if any(k in ch.name.lower() for k in ("waiting", "ويتينق", "notify", "استلام")):
                notify = ch; break
    if notify is None:
        notify = guild.system_channel or (guild.text_channels[0] if guild.text_channels else None)
    if notify is None:
        return
    em = brand_embed(
        title="🔔 شخص جديد في الويتينق!",
        description=(f"{DIVIDER}\n"
                    f"👤 **الشخص:** {member.mention}\n"
                    f"📍 **الحالة:** ينتظر الاستلام الآن\n\n"
                    f"📥 اضغط **استلام** لسحبه إلى رومك\n"
                    f"🔊 *(يجب أن تكون داخل روم صوتي)*\n"
                    f"💎 **كل سحب =** `+{POINTS_WAITING_PULL}` نقاط\n"
                    f"{DIVIDER}"),
        color=BRAND_COLOR)
    await notify.send(content=admin_role.mention if admin_role else "",
                      embed=em, view=ClaimWaitingView(member.id))

    # رسالة خاصة للعضو تذكّره يملأ وقت الانتظار بالاستغفار
    try:
        _logo = TICKET_LOGO or BRAND_ICON
        dm = brand_embed(
            title="🤍 في انتظار الاستلام",
            description=(f"{DIVIDER}\n"
                        f"مرحباً بك في **{BRAND_NAME}** 🌿\n\n"
                        f"أنت الآن في قائمة الانتظار، وسيتم استلامك قريباً بإذن الله.\n\n"
                        f"✨ اغتنم دقائق انتظارك بالاستغفار:\n"
                        f"> *أستغفر الله العظيم وأتوب إليه*\n\n"
                        f"قال ﷺ: «من لزم الاستغفار جعل الله له من كل ضيق مخرجاً، "
                        f"ومن كل هم فرجاً، ورزقه من حيث لا يحتسب».\n"
                        f"{DIVIDER}\n"
                        f"🤍 شكراً لصبرك."),
            color=BRAND_COLOR)
        await member.send(embed=dm)
    except discord.Forbidden:
        pass


@bot.event
async def on_message_delete(message):
    # لو انحذفت رسالة إجازة، ألغِ الإجازة واشِل الرتبة
    if not is_bot_active() or message.guild is None:
        return
    if message.channel.id != VACATION_CHANNEL_ID:
        return
    vac = get_vacation_by_message(message.id)
    if not vac:
        return
    delete_vacation(vac["id"])
    add_vac_log(vac["user_id"], vac["username"], "أُلغيت الإجازة", "حُذفت رسالة الإجازة")
    guild = message.guild
    member = guild.get_member(int(vac["user_id"]))
    role = guild.get_role(VACATION_ROLE_ID)
    if member and role and role in member.roles:
        try:
            await member.remove_roles(role, reason="حُذفت رسالة الإجازة")
        except discord.Forbidden:
            pass
    ch = guild.get_channel(VACATION_CHANNEL_ID)
    if ch:
        em = brand_embed(
            title="🗑️ أُلغيت الإجازة",
            description=(f"{DIVIDER}\n"
                        f"تم حذف رسالة إجازة **{vac['username']}**.\n"
                        f"لم تُحتسب الإجازة، وأُزيلت رتبة الإجازة.\n"
                        f"{DIVIDER}"),
            color=COLOR_DANGER)
        try:
            await ch.send(embed=em)
        except discord.HTTPException:
            pass


@bot.event
async def on_message(message):
    if message.author.bot:
        await bot.process_commands(message); return

    # --- تحكم المالك في الخاص (DM) ---
    if message.guild is None and message.author.id == OWNER_ID:
        status = "🟢 مُشغّل" if is_bot_active() else "🔴 مُطفأ"
        em = brand_embed(
            title="🎛️ لوحة تحكم Nova Town",
            description=(f"{DIVIDER}\n"
                        f"مرحباً بك أيها المالك 👑\n\n"
                        f"📊 **الحالة الحالية:** {status}\n\n"
                        f"🟢 **تشغيل:** يفعّل كل الأنظمة وينشر لوحة التكتات.\n"
                        f"🔴 **إطفاء:** يوقف كل الأنظمة (البوت يظل أونلاين لكن صامت).\n"
                        f"{DIVIDER}"),
            color=(COLOR_SUCCESS if is_bot_active() else COLOR_DANGER))
        await message.channel.send(embed=em, view=ControlPanelView())
        return

    # باقي الأنظمة تشتغل فقط لو البوت مفعّل
    if not is_bot_active():
        await bot.process_commands(message); return

    # إجازة
    if message.channel.id == VACATION_CHANNEL_ID:
        c = message.content.lower()
        if "name" in c and ("duration" in c or "requirements" in c):
            p = parse_vacation_form(message.content)
            if p["user_id"] and p["duration_raw"]:
                hours = parse_duration_to_hours(p["duration_raw"])
                member = message.guild.get_member(int(p["user_id"]))
                if member:
                    role = message.guild.get_role(VACATION_ROLE_ID)
                    if role:
                        try: await member.add_roles(role, reason="إجازة")
                        except discord.Forbidden: pass
                    start = datetime.utcnow(); end = start + timedelta(hours=hours)
                    add_vacation(member.id, str(member), p["reason"], hours,
                                 start.isoformat(), end.isoformat(), message.id)
                    add_vac_log(member.id, str(member), "بدأت الإجازة",
                                f"{p['duration_raw']} (~{hours:.0f}س) — {p['reason']}")
                    em = brand_embed(
                        title="🏖️ تم تسجيل الإجازة",
                        description=(f"{DIVIDER}\n"
                            f"👤 **العضو:** {member.mention}\n"
                            f"⏱️ **المدة:** {p['duration_raw']} `(~{hours:.0f} ساعة)`\n"
                            f"📝 **السبب:** {p['reason']}\n"
                            f"📅 **تنتهي:** <t:{int(end.timestamp())}:R>\n"
                            f"🎖️ **تم منح رتبة الإجازة** ✅\n"
                            f"{DIVIDER}"),
                        color=COLOR_SUCCESS)
                    await message.reply(embed=em)

    # ترقية
    elif message.channel.id == PROMOTION_CHANNEL_ID:
        c = message.content.lower()
        if "name" in c and "from" in c and "to" in c:
            p = parse_promo_form(message.content)
            if p["user_id"]:
                member = message.guild.get_member(int(p["user_id"]))
                count = p.get("count", 1)
                applied_role_id = p["to_role"]
                # نفّذ الترقية الفعلية عبر السلم لو عرفنا الرتبة الحالية
                if member and p["from_role"]:
                    ok, new_id = await apply_promotion(
                        message.guild, member, p["from_role"], count)
                    if new_id:
                        applied_role_id = new_id

                desc = (f"{DIVIDER}\n"
                        f"🎊 مبروك الترقية! 🎊\n\n"
                        f"👤 **العضو:** <@{p['user_id']}>\n")
                if p["from_role"]:   desc += f"⬇️ **من:** <@&{p['from_role']}>\n"
                if applied_role_id:  desc += f"⬆️ **إلى:** <@&{applied_role_id}>\n"
                if count > 1:        desc += f"🔼 **عدد الترقيات:** `{count}` درجات دفعة واحدة\n"
                desc += (f"📝 **السبب:** {p['reason']}\n"
                         f"✍️ **بواسطة:** Nova High Mangment\n"
                         f"{DIVIDER}")
                em = brand_embed(title="🎉 ترقية جديدة — Nova Town",
                                 description=desc, color=COLOR_PURPLE, banner=True)
                await message.channel.send(embed=em)

    await bot.process_commands(message)


# ---------- المهام المجدولة ----------
DAYS = {"monday":0,"tuesday":1,"wednesday":2,"thursday":3,"friday":4,"saturday":5,"sunday":6}
_last_aow_run = {"date": None}

@tasks.loop(hours=VACATION_CHECK_HOURS)
async def check_vacations():
    await bot.wait_until_ready()
    set_last_vac_check(datetime.utcnow().isoformat())
    for vac in get_expired_vacations(datetime.utcnow().isoformat()):
        guild = bot.get_guild(GUILD_ID)
        if not guild: continue
        member = guild.get_member(int(vac["user_id"]))
        role = guild.get_role(VACATION_ROLE_ID)
        removed = False
        if member and role and role in member.roles:
            try:
                await member.remove_roles(role, reason="انتهت الإجازة")
                removed = True
            except discord.Forbidden: pass
        deactivate_vacation(vac["id"])
        # سجّل في لوق الموقع
        detail = f"مدة {vac['duration_hours']:.0f}س" + (" — أُزيلت الرتبة" if removed else " — الرتبة غير موجودة")
        add_vac_log(vac["user_id"], vac["username"], "انتهت الإجازة", detail)
        ch = guild.get_channel(VACATION_CHANNEL_ID)
        if ch and member:
            em = brand_embed(
                title="⏰ انتهت الإجازة",
                description=(f"{DIVIDER}\n"
                            f"👤 **العضو:** {member.mention}\n"
                            f"🎖️ تمت إزالة رتبة الإجازة تلقائياً.\n"
                            f"🔄 أهلاً بعودتك للعمل!\n"
                            f"{DIVIDER}"),
                color=COLOR_DANGER)
            await ch.send(embed=em)

@tasks.loop(minutes=1)
async def aow_tick():
    await bot.wait_until_ready()
    now = datetime.now(ZoneInfo(TIMEZONE))
    day = get_setting("aow_day", AOW_DAY).lower()
    hour = int(get_setting("aow_hour", AOW_HOUR))
    minute = int(get_setting("aow_minute", AOW_MINUTE))
    if now.weekday() == DAYS.get(day, 3) and now.hour == hour and now.minute == minute:
        today = now.strftime("%Y-%m-%d")
        if _last_aow_run["date"] == today: return
        _last_aow_run["date"] = today
        guild = bot.get_guild(GUILD_ID)
        if not guild: return
        ch = guild.get_channel(ADMIN_OF_WEEK_CHANNEL_ID)
        if not ch: return
        top = get_top_weekly()
        if not top:
            await ch.send("📊 لا يوجد نقاط هذا الأسبوع لاختيار إداري الأسبوع.")
            reset_weekly(); return
        em = brand_embed(
            title="🏆 إداري الأسبوع — Nova Town",
            description=(f"{DIVIDER}\n"
                f"✨ نبارك للإداري المتألق لهذا الأسبوع! ✨\n\n"
                f"👑 **الإداري:** <@{top['user_id']}>\n"
                f"⭐ **النقاط الأسبوعية:** `{top['weekly']}`\n"
                f"📊 **النقاط الإجمالية:** `{top['total']}`\n"
                f"🎖️ **تم منح رتبة إداري الأسبوع** ✅\n\n"
                f"شكراً على جهودك وتفاعلك المميز 💙\n"
                f"{DIVIDER}"),
            color=COLOR_GOLD, banner=True)

        # بدّل رتبة إداري الأسبوع: شِلها من السابق وأعطها للجديد
        aow_role = guild.get_role(AOW_ROLE_ID)
        if aow_role:
            prev_id = get_setting("aow_current_winner")
            if prev_id:
                prev = guild.get_member(int(prev_id))
                if prev and aow_role in prev.roles:
                    try: await prev.remove_roles(aow_role, reason="انتهى أسبوعه كإداري الأسبوع")
                    except discord.Forbidden: pass
            winner = guild.get_member(int(top["user_id"]))
            if winner:
                try: await winner.add_roles(aow_role, reason="إداري الأسبوع")
                except discord.Forbidden: pass
            set_setting("aow_current_winner", top["user_id"])

        await ch.send(embed=em)
        reset_weekly()


_alerted_late = set()

_athkar_index = {"i": 0}

@tasks.loop(seconds=15)
async def promo_queue_check():
    await bot.wait_until_ready()
    pending = get_pending_promotions()
    if not pending:
        return
    guild = bot.get_guild(GUILD_ID)
    if not guild:
        return
    for pr in pending:
        mark_promotion_done(pr["id"])
        member = guild.get_member(int(pr["user_id"]))
        if not member:
            continue
        # الرتبة الحالية = أعلى رتبة للعضو موجودة في السلم
        cur_idx = None
        cur_role_id = None
        for r in member.roles:
            idx = ladder_index(r.id)
            if idx is not None and (cur_idx is None or idx > cur_idx):
                cur_idx = idx; cur_role_id = r.id
        if cur_role_id is None:
            # ما عنده رتبة في السلم — أعطه أول رتبة
            if ROLE_LADDER and ROLE_LADDER[0]["id"]:
                role = guild.get_role(ROLE_LADDER[0]["id"])
                if role:
                    try: await member.add_roles(role, reason="ترقية من الموقع")
                    except discord.Forbidden: pass
                new_id = ROLE_LADDER[0]["id"]
            else:
                continue
        else:
            ok, new_id = await apply_promotion(guild, member, cur_role_id, pr["count"])
        # انشر إعلان الترقية
        ch = guild.get_channel(PROMOTION_CHANNEL_ID)
        if ch and new_id:
            desc = (f"{DIVIDER}\n🎊 مبروك الترقية! 🎊\n\n"
                    f"👤 **العضو:** {member.mention}\n")
            if cur_role_id:
                desc += f"⬇️ **من:** <@&{cur_role_id}>\n"
            desc += (f"⬆️ **إلى:** <@&{new_id}>\n")
            if pr["count"] > 1:
                desc += f"🔼 **عدد الترقيات:** `{pr['count']}` درجات\n"
            desc += (f"📝 **السبب:** {pr['reason']}\n"
                     f"✍️ **بواسطة:** Nova High Mangment\n{DIVIDER}")
            em = brand_embed(title="🎉 ترقية جديدة — Nova Town",
                             description=desc, color=COLOR_PURPLE, banner=True)
            try: await ch.send(embed=em)
            except discord.HTTPException: pass



@tasks.loop(hours=3)
async def athkar_loop():
    await bot.wait_until_ready()
    if not is_bot_active():
        return
    guild = bot.get_guild(GUILD_ID)
    if not guild:
        return
    channel = guild.get_channel(ATHKAR_CHANNEL_ID)
    if not channel or not ATHKAR:
        return
    import random
    item = random.choice(ATHKAR)
    icons = {"ذكر": "📿", "دعاء": "🤲", "آية": "📖", "تسبيح": "✨",
             "استغفار": "🌿", "حديث": "💬"}
    icon = icons.get(item["type"], "🕌")
    _logo = TICKET_LOGO or BRAND_ICON
    em = discord.Embed(
        description=(f"{DIVIDER}\n\n"
                    f"### {icon} {item['text']}\n\n"
                    f"{DIVIDER}\n"
                    f"📚 **المصدر:** {item['source']}\n"
                    f"🏷️ **النوع:** {item['type']}"),
        color=BRAND_COLOR,
    )
    em.set_author(name=f"◈ {BRAND_NAME} • أذكار وتذكير ◈",
                  icon_url=_logo or discord.utils.MISSING)
    if _logo:
        em.set_thumbnail(url=_logo)
    em.set_footer(text=f"{BRAND_NAME} • اللهم اجعله في ميزان حسناتنا 🤍",
                  icon_url=_logo or discord.utils.MISSING)
    em.timestamp = datetime.now(ZoneInfo(TIMEZONE))
    try:
        await channel.send(embed=em)
    except discord.HTTPException:
        pass

@tasks.loop(minutes=5)
async def late_ticket_check():
    await bot.wait_until_ready()
    if not is_bot_active():
        return
    cutoff = (datetime.utcnow() - timedelta(minutes=TICKET_LATE_MINUTES)).isoformat()
    for t in get_late_unclaimed(cutoff):
        if t["channel_id"] in _alerted_late:
            continue
        _alerted_late.add(t["channel_id"])
        guild = bot.get_guild(GUILD_ID)
        if not guild:
            continue
        channel = guild.get_channel(int(t["channel_id"]))
        if not channel:
            continue
        admin_role = guild.get_role(ADMIN_ROLE_ID)
        em = brand_embed(
            title="⏰ تذكرة متأخرة بدون استلام",
            description=(f"{DIVIDER}\n"
                        f"🎫 القسم: **{t['category']}**\n"
                        f"👤 صاحبها: {t.get('owner_name') or t['owner_id']}\n"
                        f"⌛ مر أكثر من {TICKET_LATE_MINUTES} دقيقة بدون استلام!\n"
                        f"{DIVIDER}"),
            color=COLOR_DANGER)
        try:
            await channel.send(content=admin_role.mention if admin_role else "", embed=em)
        except discord.HTTPException:
            pass
# ============================================================
flask_app = Flask(__name__)
flask_app.secret_key = SECRET_KEY

def login_required(f):
    @wraps(f)
    def w(*a, **k):
        if not session.get("authed"): return redirect(url_for("login"))
        return f(*a, **k)
    return w

LOGIN_HTML = """<!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Nova Town — دخول</title>
<link href="https://fonts.googleapis.com/css2?family=Rubik:wght@400;500;700;900&family=Orbitron:wght@700;900&display=swap" rel="stylesheet">
<style>{{ css|safe }}</style></head><body class="login-body"><div class="grid-bg"></div>
<div class="orb orb-1"></div><div class="orb orb-2"></div>
<div class="login-card"><div class="login-logo">
{% if logo %}<img src="{{ logo }}" class="nt-img" alt="NT">{% else %}<span class="nt-mark">NT</span>{% endif %}
</div>
<h1 class="login-title">NOVA TOWN</h1><p class="login-sub">لوحة الإدارة العليا</p>
{% if error %}<div class="error-banner">{{ error }}</div>{% endif %}
<form method="POST" class="login-form"><label for="password">كلمة المرور</label>
<input type="password" id="password" name="password" autocomplete="off" placeholder="••••••••••••" required autofocus>
<button type="submit" class="btn-primary">دخول <span class="arr">→</span></button></form>
<p class="login-foot">وصول مقيّد — Nova High Mangment</p></div></body></html>"""

DASH_HTML = """<!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Nova Town — لوحة التحكم</title>
<link href="https://fonts.googleapis.com/css2?family=Rubik:wght@400;500;700;900&family=Orbitron:wght@700;900&display=swap" rel="stylesheet">
<style>{{ css|safe }}</style></head><body><div class="grid-bg"></div>
<div class="orb orb-1"></div>
<header class="topbar"><div class="brand">
{% if logo %}<img src="{{ logo }}" class="nt-img small" alt="NT">{% else %}<span class="nt-mark small">NT</span>{% endif %}
<div><div class="brand-name">NOVA TOWN</div><div class="brand-tag">Nova High Mangment</div></div></div>
<a href="{{ url_for('logout') }}" class="btn-ghost">خروج</a></header>
{% with m = get_flashed_messages() %}{% if m %}<div class="flash">{{ m[0] }}</div>{% endif %}{% endwith %}
<main class="wrap">
{% if top %}<section class="hero-card">
{% if logo %}<img src="{{ logo }}" class="hero-wm" alt="">{% endif %}
<div class="hero-label">👑 إداري الأسبوع الحالي</div>
<div class="hero-name">{{ top.username }}</div><div class="hero-stats">
<span><b>{{ top.weekly }}</b> نقطة أسبوعية</span><span class="dot">•</span>
<span><b>{{ top.total }}</b> إجمالية</span></div></section>{% endif %}
<nav class="tabs"><button class="tab active" data-tab="weekly">النقاط الأسبوعية</button>
<button class="tab" data-tab="total">الإجمالية</button><button class="tab" data-tab="vacations">الإجازات</button>
<button class="tab" data-tab="ratings">التقييمات</button>
<button class="tab" data-tab="tickets">التكتات</button>
<button class="tab" data-tab="settings">الإعدادات</button></nav>
<section class="panel active" id="weekly"><div class="panel-head"><h2>ترتيب النقاط الأسبوعية</h2>
<form method="POST" action="{{ url_for('reset_weekly_route') }}" onsubmit="return confirm('تأكيد تصفير النقاط الأسبوعية؟');">
<button class="btn-danger-sm">تصفير الأسبوع</button></form></div>
<table class="rank-table"><thead><tr><th>#</th><th>الإداري</th><th>أسبوعية</th><th>إجمالية</th><th>ترقية</th></tr></thead><tbody>
{% for a in weekly %}<tr><td class="rank">{{ loop.index }}</td><td>{{ a.username }}</td>
<td class="num-blue">{{ a.weekly }}</td><td class="num-dim">{{ a.total }}</td>
<td><button class="btn-promote" onclick="openPromote('{{ a.user_id }}','{{ a.username }}')">⬆️ ترقية</button></td></tr>
{% else %}<tr><td colspan="5" class="empty">لا توجد نقاط بعد.</td></tr>{% endfor %}</tbody></table></section>
<section class="panel" id="total"><div class="panel-head"><h2>الترتيب الإجمالي</h2></div>
<table class="rank-table"><thead><tr><th>#</th><th>الإداري</th><th>إجمالية</th><th>أسبوعية</th><th>ترقية</th></tr></thead><tbody>
{% for a in total %}<tr><td class="rank">{{ loop.index }}</td><td>{{ a.username }}</td>
<td class="num-blue">{{ a.total }}</td><td class="num-dim">{{ a.weekly }}</td>
<td><button class="btn-promote" onclick="openPromote('{{ a.user_id }}','{{ a.username }}')">⬆️ ترقية</button></td></tr>
{% else %}<tr><td colspan="5" class="empty">لا توجد نقاط بعد.</td></tr>{% endfor %}</tbody></table></section>
<section class="panel" id="vacations"><div class="panel-head"><h2>الإجازات النشطة</h2></div><div class="vac-grid">
{% for v in vacations %}<div class="vac-card"><div class="vac-top"><span class="vac-user">{{ v.username }}</span>
<span class="vac-remain">{{ v.remaining_hours }} ساعة متبقية</span></div>
<div class="vac-reason">السبب: {{ v.reason }}</div><div class="vac-actions">
<form method="POST" action="{{ url_for('edit_vacation', vac_id=v.id) }}" class="inline">
<input type="number" name="hours" step="0.5" min="0" value="{{ v.duration_hours }}"><button class="btn-sm">حفظ المدة</button></form>
<form method="POST" action="{{ url_for('recalc_vacation', vac_id=v.id) }}" class="inline" onsubmit="return confirm('إعادة حساب الوقت من الآن؟');">
<button class="btn-sm ghost">إعادة الحساب</button></form></div></div>
{% else %}<p class="empty">لا توجد إجازات نشطة.</p>{% endfor %}</div>
<h3 class="sub-h">📋 سجل الإجازات (الكل)</h3>
<table class="rank-table"><thead><tr><th>العضو</th><th>المدة</th><th>السبب</th><th>البداية</th><th>النهاية</th><th>الحالة</th></tr></thead><tbody>
{% for v in vac_log %}<tr>
<td>{{ v.username }}</td>
<td>{{ v.duration_hours|round(0)|int }} ساعة</td>
<td>{{ v.reason }}</td>
<td class="num-dim">{{ v.start_disp }}</td>
<td class="num-dim">{{ v.end_disp }}</td>
<td>{% if v.is_active %}<span class="prio prio-normal">نشطة</span>{% else %}<span class="prio prio-urgent">منتهية</span>{% endif %}</td>
</tr>
{% else %}<tr><td colspan="6" class="empty">لا يوجد سجل إجازات.</td></tr>{% endfor %}
</tbody></table>
<div class="check-info">🔄 آخر فحص للإجازات: <b>{{ last_check_disp }}</b> · يفحص كل <b>{{ check_hours }}</b> ساعتين</div>
<h3 class="sub-h">🧾 سجل عمليات الإجازات</h3>
<table class="rank-table"><thead><tr><th>العضو</th><th>العملية</th><th>التفاصيل</th><th>الوقت</th></tr></thead><tbody>
{% for a in vac_actions %}<tr>
<td>{{ a.username }}</td>
<td>{% if a.action=='بدأت الإجازة' %}<span class="prio prio-normal">{{ a.action }}</span>{% elif a.action=='انتهت الإجازة' %}<span class="prio prio-important">{{ a.action }}</span>{% else %}<span class="prio prio-urgent">{{ a.action }}</span>{% endif %}</td>
<td class="num-dim">{{ a.detail }}</td>
<td class="num-dim">{{ a.at_disp }}</td>
</tr>
{% else %}<tr><td colspan="4" class="empty">لا توجد عمليات بعد.</td></tr>{% endfor %}
</tbody></table>
</section>
<section class="panel" id="ratings"><div class="panel-head"><h2>تقييمات الإداريين</h2></div>
<div class="rate-grid">
{% for r in ratings %}
<div class="rate-card">
<div class="rate-top"><span class="rate-name">{{ r.username }}</span>
<span class="rate-avg">{{ r.avg_display }} <span class="star">★</span></span></div>
<div class="rate-bar"><div class="rate-fill" style="width: {{ (r.avg_r / 5 * 100)|round(0) }}%"></div></div>
<div class="rate-meta">{{ r.cnt }} تقييم · مجموع {{ r.sum_r }}</div>
</div>
{% else %}<p class="empty">لا توجد تقييمات بعد.</p>{% endfor %}
</div>
{% if recent %}<h3 class="sub-h">آخر التقييمات</h3>
<table class="rank-table"><thead><tr><th>الإداري</th><th>القسم</th><th>التقييم</th></tr></thead><tbody>
{% for r in recent %}<tr><td>{{ r.username }}</td><td>{{ r.category or '—' }}</td>
<td class="stars-cell">{% for i in range(r.rating) %}★{% endfor %}{% for i in range(5 - r.rating) %}<span class="star-empty">★</span>{% endfor %} <span class="num-dim">({{ r.rating }}/5)</span></td></tr>
{% endfor %}</tbody></table>{% endif %}
</section>
<section class="panel" id="tickets"><div class="panel-head"><h2>إحصائيات التكتات</h2></div>
<div class="stat-row">
<div class="stat-box"><div class="stat-num">{{ tstats.total }}</div><div class="stat-lbl">إجمالي التكتات</div></div>
<div class="stat-box"><div class="stat-num num-blue">{{ tstats.open }}</div><div class="stat-lbl">مفتوحة حالياً</div></div>
<div class="stat-box"><div class="stat-num">{{ tstats.closed }}</div><div class="stat-lbl">مغلقة</div></div>
<div class="stat-box"><div class="stat-num" style="color:var(--gold)">{{ tstats.avg_display }}</div><div class="stat-lbl">متوسط التقييم</div></div>
</div>
{% if tstats.by_cat %}<h3 class="sub-h">حسب القسم</h3>
<div class="cat-row">
{% for c in tstats.by_cat %}<div class="cat-chip">{{ c.category }} <b>{{ c.n }}</b></div>{% endfor %}
</div>{% endif %}
<h3 class="sub-h">سجل التكتات (النسخ الاحتياطية)</h3>
<table class="rank-table"><thead><tr><th>#</th><th>صاحب التكت</th><th>القسم</th><th>الأولوية</th><th>الحالة</th><th>التقييم</th><th>النسخة</th></tr></thead><tbody>
{% for t in tickets %}<tr>
<td class="rank">{{ t.id }}</td>
<td>{{ t.owner_name or t.owner_id }}</td>
<td>{{ t.category }}</td>
<td><span class="prio prio-{{ t.priority or 'normal' }}">{{ t.prio_ar }}</span></td>
<td>{{ t.status_ar }}</td>
<td class="stars-cell">{% if t.rating %}{% for i in range(t.rating) %}★{% endfor %}{% else %}<span class="num-dim">—</span>{% endif %}</td>
<td>{% if t.transcript %}<a class="view-link" href="{{ url_for('transcript', ticket_id=t.id) }}" target="_blank">عرض</a>{% else %}<span class="num-dim">—</span>{% endif %}</td>
</tr>
{% else %}<tr><td colspan="7" class="empty">لا توجد تكتات بعد.</td></tr>{% endfor %}
</tbody></table>
</section>
<section class="panel" id="settings"><div class="panel-head"><h2>موعد إعلان إداري الأسبوع</h2></div>
<form method="POST" action="{{ url_for('update_schedule') }}" class="settings-form">
<div class="field"><label>اليوم</label><select name="day">
{% for val, ar in [('saturday','السبت'),('sunday','الأحد'),('monday','الإثنين'),('tuesday','الثلاثاء'),('wednesday','الأربعاء'),('thursday','الخميس'),('friday','الجمعة')] %}
<option value="{{ val }}" {% if schedule.day==val %}selected{% endif %}>{{ ar }}</option>{% endfor %}</select></div>
<div class="field"><label>الساعة (0-23)</label><input type="number" name="hour" min="0" max="23" value="{{ schedule.hour }}"></div>
<div class="field"><label>الدقيقة</label><input type="number" name="minute" min="0" max="59" value="{{ schedule.minute }}"></div>
<button class="btn-primary">حفظ الموعد</button></form>
<p class="hint">التوقيت حسب توقيت السعودية. الافتراضي: الخميس 8:00 مساءً.</p></section>
</main>

<div id="promoteModal" class="modal-overlay" style="display:none;">
<div class="modal-box">
<h3>⬆️ ترقية إداري</h3>
<form method="POST" action="{{ url_for('promote_admin') }}">
<input type="hidden" name="user_id" id="pm_uid">
<div class="field"><label>الإداري</label><input type="text" id="pm_name" disabled></div>
<div class="field"><label>عدد الدرجات</label>
<select name="count"><option value="1">درجة واحدة</option><option value="2">درجتين</option><option value="3">3 درجات</option></select></div>
<div class="field"><label>السبب</label><input type="text" name="reason" placeholder="سبب الترقية" required></div>
<div class="modal-actions">
<button type="button" class="btn-ghost" onclick="closePromote()">إلغاء</button>
<button type="submit" class="btn-primary">تأكيد الترقية</button></div>
</form></div></div>

<script>
document.querySelectorAll('.tab').forEach(t=>t.addEventListener('click',()=>{
document.querySelectorAll('.tab').forEach(x=>x.classList.remove('active'));
document.querySelectorAll('.panel').forEach(p=>p.classList.remove('active'));
t.classList.add('active');document.getElementById(t.dataset.tab).classList.add('active');}));
function openPromote(uid,name){document.getElementById('pm_uid').value=uid;
document.getElementById('pm_name').value=name;
document.getElementById('promoteModal').style.display='flex';}
function closePromote(){document.getElementById('promoteModal').style.display='none';}
</script></body></html>"""

TRANSCRIPT_HTML = """<!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0"><title>نسخة التذكرة #{{ t.id }} — Nova Town</title>
<link href="https://fonts.googleapis.com/css2?family=Rubik:wght@400;500;700;900&family=Orbitron:wght@700;900&display=swap" rel="stylesheet">
<style>{{ css|safe }}</style></head><body><div class="grid-bg"></div>
<header class="topbar"><div class="brand">
{% if logo %}<img src="{{ logo }}" class="nt-img small" alt="NT">{% else %}<span class="nt-mark small">NT</span>{% endif %}
<div><div class="brand-name">NOVA TOWN</div><div class="brand-tag">نسخة احتياطية للتذكرة</div></div></div>
<a href="{{ url_for('dashboard') }}" class="btn-ghost">رجوع</a></header>
<div class="ts-wrap">
<div class="ts-head">
<h1>🎫 تذكرة #{{ t.id }} — {{ t.category }}</h1>
<div class="ts-meta">
👤 صاحب التذكرة: {{ t.owner_name or t.owner_id }}<br>
{% if t.claimed_by %}👨‍💼 استلمها: {{ t.claimed_by }}<br>{% endif %}
{% if t.rating %}⭐ التقييم: {{ t.rating }}/5<br>{% endif %}
📌 الأولوية: {{ t.priority or 'normal' }}<br>
📅 أُنشئت: {{ t.created_at[:16] }}{% if t.closed_at %} · أُغلقت: {{ t.closed_at[:16] }}{% endif %}
</div></div>
<div class="ts-body">{{ transcript_html|safe }}</div>
</div></body></html>"""

CSS = """
:root{--bg:#060810;--bg-2:#0b0f1c;--panel:#0e1526;--panel-2:#131d33;--line:#1e2b46;
--blue:#2f8fff;--blue-hi:#66b8ff;--blue-glow:rgba(47,143,255,.3);--text:#e4ecf7;
--text-dim:#8493ad;--danger:#ff4d6a;--gold:#ffcb47;--radius:10px}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Rubik',system-ui,sans-serif;background:var(--bg);color:var(--text);
min-height:100vh;line-height:1.6;position:relative;overflow-x:hidden;letter-spacing:.1px}
.grid-bg{position:fixed;inset:0;z-index:0;pointer-events:none;
background-image:linear-gradient(var(--line) 1px,transparent 1px),linear-gradient(90deg,var(--line) 1px,transparent 1px);
background-size:52px 52px;opacity:.1;mask-image:radial-gradient(ellipse 80% 60% at 50% 0%,#000 20%,transparent 75%)}
body::before{content:"";position:fixed;top:-30%;left:50%;transform:translateX(-50%);width:900px;height:600px;
z-index:0;pointer-events:none;background:radial-gradient(circle,var(--blue-glow),transparent 65%);filter:blur(50px);opacity:.4}
.nt-mark{font-family:'Orbitron',sans-serif;font-weight:900;display:inline-flex;align-items:center;justify-content:center;
width:74px;height:74px;background:linear-gradient(145deg,#0b1120,#05070d);border:2px solid var(--blue);border-radius:50%;
color:var(--blue-hi);font-size:1.6rem;letter-spacing:1px;box-shadow:0 0 22px var(--blue-glow),inset 0 0 18px rgba(47,143,255,.15)}
.nt-mark.small{width:46px;height:46px;font-size:1rem}
.nt-mark{animation:pulse-ring 3s ease-in-out infinite}
@keyframes pulse-ring{0%,100%{box-shadow:0 0 22px var(--blue-glow),inset 0 0 18px rgba(47,143,255,.15)}50%{box-shadow:0 0 38px var(--blue-glow),inset 0 0 22px rgba(47,143,255,.28)}}
.nt-img{width:88px;height:88px;border-radius:50%;object-fit:cover;
box-shadow:0 0 30px var(--blue-glow);animation:pulse-ring 3s ease-in-out infinite}
.nt-img.small{width:46px;height:46px;box-shadow:0 0 16px var(--blue-glow)}
.orb{position:fixed;border-radius:50%;pointer-events:none;z-index:0;filter:blur(60px);opacity:.35}
.orb-1{width:400px;height:400px;background:radial-gradient(circle,#2f8fff,transparent 70%);
top:-120px;right:-100px;animation:float1 14s ease-in-out infinite}
.orb-2{width:340px;height:340px;background:radial-gradient(circle,#9b6dff,transparent 70%);
bottom:-120px;left:-90px;animation:float2 18s ease-in-out infinite}
@keyframes float1{0%,100%{transform:translate(0,0)}50%{transform:translate(-40px,50px)}}
@keyframes float2{0%,100%{transform:translate(0,0)}50%{transform:translate(50px,-40px)}}
.arr{display:inline-block;transition:transform .2s}
.btn-primary:hover .arr{transform:translateX(-4px)}
.login-body{display:flex;align-items:center;justify-content:center;padding:24px}
.login-card{position:relative;z-index:1;width:100%;max-width:400px;text-align:center;
background:linear-gradient(180deg,rgba(13,20,36,.85),rgba(10,14,26,.9));backdrop-filter:blur(16px);
border:1px solid var(--line);border-radius:14px;
padding:44px 34px;box-shadow:0 30px 80px rgba(0,0,0,.6),0 0 0 1px rgba(47,143,255,.08);
animation:card-in .6s cubic-bezier(.16,1,.3,1)}
@keyframes card-in{from{opacity:0;transform:translateY(24px) scale(.97)}to{opacity:1;transform:none}}
.login-logo{margin-bottom:18px}
.login-title{font-family:'Orbitron',sans-serif;font-size:1.9rem;letter-spacing:6px;color:#fff;margin-bottom:4px;text-shadow:0 0 20px var(--blue-glow)}
.login-sub{color:var(--text-dim);font-size:.95rem;margin-bottom:28px}
.login-form{display:flex;flex-direction:column;gap:14px;text-align:right}
.login-form label{font-size:.85rem;color:var(--text-dim)}
.login-form input{background:var(--bg);border:1px solid var(--line);border-radius:var(--radius);padding:13px 15px;
color:var(--text);font-size:1rem;font-family:inherit;transition:border-color .2s,box-shadow .2s}
.login-form input:focus{outline:none;border-color:var(--blue);box-shadow:0 0 0 3px var(--blue-glow)}
.login-foot{margin-top:22px;font-size:.75rem;color:var(--text-dim);letter-spacing:1px}
.error-banner{background:rgba(255,77,106,.12);border:1px solid rgba(255,77,106,.4);color:#ffa9b8;
padding:10px;border-radius:var(--radius);font-size:.85rem;margin-bottom:18px}
.btn-primary{background:linear-gradient(135deg,var(--blue),#1f6fd6);color:#fff;border:none;border-radius:var(--radius);
padding:13px 20px;font-size:1rem;font-weight:700;font-family:inherit;cursor:pointer;transition:transform .12s,box-shadow .2s;box-shadow:0 6px 20px var(--blue-glow)}
.btn-primary:hover{transform:translateY(-1px);box-shadow:0 10px 28px var(--blue-glow)}
.btn-ghost{color:var(--text-dim);text-decoration:none;border:1px solid var(--line);padding:8px 16px;border-radius:var(--radius);font-size:.85rem;transition:.2s}
.btn-ghost:hover{border-color:var(--blue);color:var(--blue-hi)}
.btn-sm{background:var(--panel-2);border:1px solid var(--line);color:var(--text);padding:7px 12px;border-radius:var(--radius);font-size:.8rem;cursor:pointer;font-family:inherit;transition:.2s}
.btn-sm:hover{border-color:var(--blue);color:var(--blue-hi)}
.btn-sm.ghost{background:transparent}
.btn-danger-sm{background:transparent;border:1px solid rgba(255,77,106,.4);color:#ffa9b8;padding:7px 14px;border-radius:var(--radius);font-size:.8rem;cursor:pointer;font-family:inherit;transition:.2s}
.btn-danger-sm:hover{background:rgba(255,77,106,.12)}
.topbar{position:relative;z-index:2;display:flex;justify-content:space-between;align-items:center;padding:18px 28px;border-bottom:1px solid var(--line);background:rgba(5,7,13,.7);backdrop-filter:blur(10px)}
.brand{display:flex;align-items:center;gap:14px}
.brand-name{font-family:'Orbitron',sans-serif;font-weight:900;letter-spacing:3px;font-size:1.1rem}
.brand-tag{font-size:.72rem;color:var(--text-dim);letter-spacing:1px}
.flash{position:relative;z-index:2;max-width:1100px;margin:16px auto 0;background:rgba(47,143,255,.1);border:1px solid rgba(47,143,255,.35);color:var(--blue-hi);padding:11px 18px;border-radius:var(--radius);font-size:.88rem}
.wrap{position:relative;z-index:2;max-width:1100px;margin:0 auto;padding:28px 24px 80px}
.hero-card{background:linear-gradient(120deg,var(--panel-2),var(--panel));border:1px solid var(--line);border-radius:12px;padding:26px 30px;margin-bottom:26px;position:relative;overflow:hidden;animation:card-in .6s cubic-bezier(.16,1,.3,1)}
.hero-card::before{content:"";position:absolute;top:0;left:-60%;width:40%;height:100%;
background:linear-gradient(90deg,transparent,rgba(255,203,71,.12),transparent);
animation:shimmer 4.5s ease-in-out infinite}
@keyframes shimmer{0%{left:-60%}60%,100%{left:120%}}
.hero-card::after{content:"";position:absolute;top:0;left:0;width:5px;height:100%;background:linear-gradient(var(--blue),var(--blue-hi));box-shadow:0 0 18px var(--blue-glow)}
.hero-label{font-size:.78rem;color:var(--text-dim);letter-spacing:2px;text-transform:uppercase}
.hero-name{font-size:1.9rem;font-weight:900;margin:6px 0;color:#fff;letter-spacing:.5px}
.hero-wm{position:absolute;left:24px;top:50%;transform:translateY(-50%);width:120px;height:120px;border-radius:50%;opacity:.12;filter:blur(1px)}
.hero-stats{color:var(--text-dim);font-size:.95rem}.hero-stats b{color:var(--blue-hi)}.hero-stats .dot{margin:0 10px;opacity:.5}
.tabs{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:20px;border-bottom:1px solid var(--line)}
.tab{background:none;border:none;color:var(--text-dim);font-family:inherit;font-size:.92rem;padding:12px 18px;cursor:pointer;position:relative;transition:color .2s}
.tab:hover{color:var(--text)}.tab.active{color:var(--blue-hi)}
.tab.active::after{content:"";position:absolute;bottom:-1px;right:0;left:0;height:2px;background:var(--blue);box-shadow:0 0 12px var(--blue-glow)}
.panel{display:none;animation:fade .3s ease}.panel.active{display:block}
@keyframes fade{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}
.panel-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px}.panel-head h2{font-size:1.15rem;font-weight:700}
.rank-table{width:100%;border-collapse:collapse;background:var(--panel);border:1px solid var(--line);border-radius:var(--radius);overflow:hidden}
.rank-table th{text-align:right;padding:13px 16px;font-size:.78rem;color:var(--text-dim);letter-spacing:1px;text-transform:uppercase;background:var(--bg-2);border-bottom:1px solid var(--line)}
.rank-table td{padding:13px 16px;border-bottom:1px solid var(--line);font-size:.92rem}
.rank-table tr:last-child td{border-bottom:none}.rank-table tbody tr{transition:background .15s}.rank-table tbody tr:hover{background:var(--panel-2)}
.rank-table tbody tr:nth-child(1){background:rgba(255,203,71,.06)}
.rank-table tbody tr:nth-child(2){background:rgba(191,201,216,.05)}
.rank-table tbody tr:nth-child(3){background:rgba(205,127,50,.05)}
.rank{font-family:'Orbitron',sans-serif;color:var(--blue);font-weight:700;width:60px}
.rank-table tbody tr:nth-child(1) .rank{color:var(--gold)}
.num-blue{color:var(--blue-hi);font-weight:700}.num-dim{color:var(--text-dim)}
.empty{text-align:center;color:var(--text-dim);padding:30px!important}
.vac-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:16px}
.vac-card{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:18px;transition:transform .18s,border-color .18s,box-shadow .18s}
.vac-card:hover{transform:translateY(-3px);border-color:var(--blue);box-shadow:0 12px 30px rgba(0,0,0,.4),0 0 0 1px var(--blue-glow)}
.vac-top{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px}.vac-user{font-weight:700}
.vac-remain{font-size:.78rem;color:var(--blue-hi);background:rgba(47,143,255,.1);padding:3px 10px;border-radius:20px;border:1px solid rgba(47,143,255,.25)}
.vac-reason{font-size:.85rem;color:var(--text-dim);margin-bottom:14px}
.vac-actions{display:flex;gap:8px;flex-wrap:wrap;align-items:center}.vac-actions .inline{display:flex;gap:6px;align-items:center}
.vac-actions input{width:80px;background:var(--bg);border:1px solid var(--line);border-radius:var(--radius);color:var(--text);padding:6px 8px;font-family:inherit;font-size:.82rem}
.settings-form{display:flex;gap:16px;flex-wrap:wrap;align-items:flex-end;background:var(--panel);border:1px solid var(--line);border-radius:var(--radius);padding:22px}
.field{display:flex;flex-direction:column;gap:6px}.field label{font-size:.8rem;color:var(--text-dim)}
.field input,.field select{background:var(--bg);border:1px solid var(--line);border-radius:var(--radius);color:var(--text);padding:10px 12px;font-family:inherit;font-size:.9rem;min-width:130px}
.field input:focus,.field select:focus{outline:none;border-color:var(--blue)}
.hint{margin-top:12px;font-size:.8rem;color:var(--text-dim)}
.check-info{margin:16px 0;padding:11px 16px;background:rgba(47,143,255,.08);border:1px solid rgba(47,143,255,.2);border-radius:8px;font-size:.85rem;color:var(--text-dim)}
.check-info b{color:var(--blue-hi)}
.rate-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:16px;margin-bottom:26px}
.rate-card{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:18px;transition:transform .18s,border-color .18s,box-shadow .18s}
.rate-card:hover{transform:translateY(-3px);border-color:var(--gold);box-shadow:0 12px 30px rgba(0,0,0,.4),0 0 0 1px rgba(255,203,71,.25)}
.rate-top{display:flex;justify-content:space-between;align-items:center;margin-bottom:10px}
.rate-name{font-weight:700}
.rate-avg{font-size:1.15rem;font-weight:900;color:var(--gold)}.rate-avg .star{font-size:.95rem}
.rate-bar{height:8px;background:var(--bg);border-radius:20px;overflow:hidden;margin-bottom:8px}
.rate-fill{height:100%;background:linear-gradient(90deg,#ffcb47,#ffe08a);border-radius:20px;box-shadow:0 0 10px rgba(255,203,71,.4)}
.rate-meta{font-size:.78rem;color:var(--text-dim)}
.sub-h{font-size:1rem;font-weight:700;margin:8px 0 14px;color:var(--text)}
.stars-cell{color:var(--gold);letter-spacing:2px}.star-empty{color:var(--line)}
.stat-row{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:14px;margin-bottom:22px}
.stat-box{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:20px;text-align:center;transition:transform .18s,border-color .18s}
.stat-box:hover{transform:translateY(-3px);border-color:var(--blue)}
.stat-num{font-family:'Orbitron',sans-serif;font-size:2rem;font-weight:900;color:var(--text)}
.stat-lbl{font-size:.8rem;color:var(--text-dim);margin-top:4px}
.cat-row{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:8px}
.cat-chip{background:var(--panel);border:1px solid var(--line);border-radius:20px;padding:6px 14px;font-size:.82rem;color:var(--text-dim)}
.cat-chip b{color:var(--blue-hi)}
.prio{padding:3px 10px;border-radius:20px;font-size:.75rem;font-weight:700}
.prio-normal{background:rgba(40,199,111,.12);color:#28c76f;border:1px solid rgba(40,199,111,.3)}
.prio-important{background:rgba(255,203,71,.12);color:#ffcb47;border:1px solid rgba(255,203,71,.3)}
.prio-urgent{background:rgba(255,77,106,.12);color:#ff4d6a;border:1px solid rgba(255,77,106,.3)}
.view-link{color:var(--blue-hi);text-decoration:none;border:1px solid rgba(47,143,255,.3);padding:3px 12px;border-radius:6px;font-size:.8rem;transition:.2s}
.view-link:hover{background:rgba(47,143,255,.1)}
.ts-wrap{max-width:800px;margin:0 auto;padding:30px 20px}
.ts-head{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:22px;margin-bottom:20px}
.ts-head h1{font-size:1.3rem;margin-bottom:8px}
.ts-meta{color:var(--text-dim);font-size:.88rem;line-height:1.8}
.msg{display:flex;gap:12px;padding:10px 14px;border-radius:8px;margin-bottom:4px}
.msg:hover{background:var(--panel)}
.msg .av{width:40px;height:40px;border-radius:50%;flex-shrink:0}
.msg .head{display:flex;gap:10px;align-items:baseline;margin-bottom:2px}
.msg .name{font-weight:700;color:var(--blue-hi)}
.msg .time{font-size:.72rem;color:var(--text-dim)}
.msg .text{color:var(--text);font-size:.92rem;line-height:1.5;word-break:break-word}
.msg .att{margin-top:4px;font-size:.85rem}
.msg .att a{color:var(--blue-hi)}
.btn-promote{background:linear-gradient(135deg,#9b6dff,#7d4fd6);color:#fff;border:none;border-radius:6px;padding:6px 12px;font-size:.78rem;font-weight:700;font-family:inherit;cursor:pointer;transition:transform .12s,box-shadow .2s;white-space:nowrap}
.btn-promote:hover{transform:translateY(-1px);box-shadow:0 6px 16px rgba(155,109,255,.4)}
.modal-overlay{position:fixed;inset:0;background:rgba(3,5,10,.8);backdrop-filter:blur(6px);z-index:100;align-items:center;justify-content:center}
.modal-box{background:linear-gradient(180deg,var(--panel),var(--bg-2));border:1px solid var(--line);border-radius:14px;padding:28px;width:90%;max-width:400px;box-shadow:0 30px 80px rgba(0,0,0,.7);animation:card-in .4s cubic-bezier(.16,1,.3,1)}
.modal-box h3{font-size:1.2rem;margin-bottom:18px;color:#fff}
.modal-box .field{margin-bottom:14px}
.modal-box input,.modal-box select{width:100%;background:var(--bg);border:1px solid var(--line);border-radius:8px;padding:11px 13px;color:var(--text);font-family:inherit;font-size:.92rem}
.modal-box input:focus,.modal-box select:focus{outline:none;border-color:var(--blue)}
.modal-box input:disabled{color:var(--blue-hi);font-weight:700}
.modal-actions{display:flex;gap:10px;justify-content:flex-start;margin-top:20px}
@media(max-width:600px){.settings-form{flex-direction:column;align-items:stretch}.hero-name{font-size:1.4rem}.topbar{padding:14px 16px}.wrap{padding:20px 14px 60px}.rank-table{font-size:.8rem}.rank-table th,.rank-table td{padding:9px 8px}}
"""

@flask_app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        if request.form.get("password") == DASHBOARD_PASSWORD:
            session["authed"] = True
            return redirect(url_for("dashboard"))
        error = "كلمة المرور غير صحيحة."
    return render_template_string(LOGIN_HTML, error=error, css=CSS,
                                  logo=(TICKET_LOGO or BRAND_ICON))

@flask_app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@flask_app.route("/")
@login_required
def dashboard():
    weekly = get_leaderboard("weekly")
    total = get_leaderboard("total")
    vacations = get_active_vacations()
    now = datetime.utcnow()
    for v in vacations:
        try:
            v["remaining_hours"] = max(0, round(
                (datetime.fromisoformat(v["end_at"]) - now).total_seconds() / 3600, 1))
        except Exception:
            v["remaining_hours"] = "—"
    schedule = {"day": get_setting("aow_day", AOW_DAY),
                "hour": get_setting("aow_hour", str(AOW_HOUR)),
                "minute": get_setting("aow_minute", str(AOW_MINUTE))}
    ratings = get_ratings_summary()
    for r in ratings:
        r["avg_display"] = f"{r['avg_r']:.2f}" if r["avg_r"] is not None else "—"
    recent = get_recent_ratings(30)
    tstats = get_ticket_stats()
    tstats["avg_display"] = f"{tstats['avg_rating']:.2f}" if tstats["avg_rating"] else "—"
    tickets = get_all_tickets(100)
    prio_ar = {"normal": "عادي", "important": "مهم", "urgent": "عاجل"}
    for t in tickets:
        t["prio_ar"] = prio_ar.get(t.get("priority") or "normal", "عادي")
        t["status_ar"] = {"open": "مفتوح", "claimed": "مُستلم", "closed": "مغلق"}.get(t.get("status"), t.get("status"))
    vac_log = get_all_vacations(200)
    for v in vac_log:
        v["is_active"] = v.get("active") == 1
        try:
            v["start_disp"] = v["start_at"][:16].replace("T", " ")
            v["end_disp"] = v["end_at"][:16].replace("T", " ")
        except Exception:
            v["start_disp"] = v["end_disp"] = "—"
    vac_actions = get_vac_log(60)
    for a in vac_actions:
        try:
            a["at_disp"] = a["at"][:16].replace("T", " ")
        except Exception:
            a["at_disp"] = "—"
    last_check = get_last_vac_check()
    last_check_disp = last_check[:16].replace("T", " ") if last_check else "لم يبدأ بعد"
    return render_template_string(DASH_HTML, weekly=weekly, total=total,
        vacations=vacations, top=get_top_weekly(), schedule=schedule, css=CSS,
        logo=(TICKET_LOGO or BRAND_ICON), ratings=ratings, recent=recent,
        tstats=tstats, tickets=tickets, vac_log=vac_log,
        vac_actions=vac_actions, last_check_disp=last_check_disp,
        check_hours=VACATION_CHECK_HOURS)


@flask_app.route("/transcript/<int:ticket_id>")
@login_required
def transcript(ticket_id):
    t = get_ticket_by_id(ticket_id)
    if not t:
        return "التذكرة غير موجودة", 404
    return render_template_string(TRANSCRIPT_HTML, t=t, css=CSS,
                                  logo=(TICKET_LOGO or BRAND_ICON),
                                  transcript_html=(t.get("transcript") or '<p class="empty">لا توجد نسخة محفوظة لهذه التذكرة.</p>'))

@flask_app.route("/api/schedule", methods=["POST"])
@login_required
def update_schedule():
    set_setting("aow_day", request.form.get("day", "thursday").lower())
    set_setting("aow_hour", request.form.get("hour", "20"))
    set_setting("aow_minute", request.form.get("minute", "0"))
    flash("تم تحديث موعد إداري الأسبوع.")
    return redirect(url_for("dashboard"))

@flask_app.route("/api/vacation/<int:vac_id>/duration", methods=["POST"])
@login_required
def edit_vacation(vac_id):
    vac = get_vacation(vac_id)
    if vac:
        new_hours = float(request.form.get("hours", 0))
        new_end = datetime.fromisoformat(vac["start_at"]) + timedelta(hours=new_hours)
        update_vacation_duration(vac_id, new_end.isoformat(), new_hours)
        flash("تم تعديل مدة الإجازة.")
    return redirect(url_for("dashboard"))

@flask_app.route("/api/vacation/<int:vac_id>/recalc", methods=["POST"])
@login_required
def recalc_vacation(vac_id):
    vac = get_vacation(vac_id)
    if vac:
        new_end = datetime.utcnow() + timedelta(hours=vac["duration_hours"])
        update_vacation_duration(vac_id, new_end.isoformat(), vac["duration_hours"])
        flash("تمت إعادة حساب وقت الإجازة من الآن.")
    return redirect(url_for("dashboard"))

@flask_app.route("/api/reset-weekly", methods=["POST"])
@login_required
def reset_weekly_route():
    reset_weekly()
    flash("تم تصفير النقاط الأسبوعية.")
    return redirect(url_for("dashboard"))


@flask_app.route("/api/promote", methods=["POST"])
@login_required
def promote_admin():
    user_id = request.form.get("user_id")
    count = int(request.form.get("count", 1))
    reason = request.form.get("reason", "ترقية من الإدارة العليا")
    if user_id:
        queue_promotion(user_id, count, reason)
        flash("تم إرسال طلب الترقية — سينفّذها البوت خلال ثوانٍ.")
    return redirect(url_for("dashboard"))


# ============================================================
#                       التشغيل
# ============================================================
def run_web():
    flask_app.run(host="0.0.0.0", port=WEB_PORT, debug=False, use_reloader=False)

def main():
    init_db()
    # شغّل الموقع في ثريد منفصل
    threading.Thread(target=run_web, daemon=True).start()
    print(f"🌐 الموقع شغّال على المنفذ {WEB_PORT}")
    # شغّل البوت (الثريد الرئيسي)
    bot.run(BOT_TOKEN)

if __name__ == "__main__":
    main()
