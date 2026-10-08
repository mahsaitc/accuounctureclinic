# راهنمای تهیه‌ی تصاویر بدن برای نرم‌افزار طب سوزنی (رندر از مدل سه‌بعدی آزاد)

هدف: ساخت یک ست یکدست تصویر از بدن (بدن کامل، سر، گردن، تنه، بازو، دست، ساق، پا) در نماهای روبرو، پشت و جانبی، با لایسنس قابل‌استفاده در نرم‌افزار.

وضعیت: اسکریپت روی مدل واقعی Z-Anatomy با Blender 5.2 LTS (ویندوز، گرافیک Intel، رندر با CPU) آزمایش شده است.

## ۱. نصب
1. **Blender** (نسخه‌ی LTS) از blender.org.
2. مدل Z-Anatomy از GitHub: `Z-Anatomy/Models-of-human-anatomy`. فایل `Z-Anatomy.zip` را **باز نکنید**.
3. در Blender: *Install Application Template* و سپس *File > New > Z-Anatomy*. بلافاصله با `Ctrl+Shift+S` به‌صورت `Z-Anatomy.blend` ذخیره کنید، قبل از اینکه ویوپورت را بچرخانید (روی گرافیک ضعیف ممکن است ویندوز با `VIDEO_TDR_FAILURE` ریست شود).
4. اختیاری، بدون GUI: `blender -b --app-template Z-Anatomy --python tools/blender/save_template.py -- مسیر\Z-Anatomy.blend`

## ۲. نکته‌های مدل
- collection مناسب برای سطح بدن: **`9: Regions of human body`**.
- مدل مردانه و برهنه است. اندام تناسلی و موی ناحیه با `--exclude` حذف می‌شوند.
- شیء `Regions of human body.g` متن عنوان است و باید حذف شود، وگرنه بدن از وسط تصویر کنار می‌رود.
- صحنه‌ی Z-Anatomy یک compositor و freestyle دارد که خروجی را سفید می‌کند. اسکریپت آن‌ها را خاموش می‌کند.

## ۳. پیش‌نمایش سریع (۳ تا ۵ دقیقه)
```powershell
& "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" -b "…\Z-Anatomy.blend" --python tools\blender\render_views.py -- --engine cpu --samples 8 --out build\preview --collections "9: Regions of human body" --size 380 --sheet --exclude "regions of human body,pubic hairs,urogenital region"
```
خروجی: همه‌ی نماها و یک `sheet.png` که همه را روی یک صفحه نشان می‌دهد. اگر فقط می‌خواهید `sheet.png` را از تصاویر موجود دوباره بسازید: `--sheet-only --out build\preview --size 380` (بدون باز کردن فایل مدل).

## ۴. رندر نهایی
```powershell
& "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" -b "…\Z-Anatomy.blend" --python tools\blender\render_views.py -- --engine cpu --samples 48 --out build\final --collections "9: Regions of human body" --size 1400 --exclude "regions of human body,pubic hairs,urogenital region"
```
برای فقط چند ناحیه: `--regions head,right_hand`. خروجی PNG شفاف است و فایل `manifest.json` ابعاد و محورها را ثبت می‌کند.

گزینه‌های کاربردی: `--light` (روشنایی)، `--outline` (خط دور؛ کند)، `--shadows` (سایه‌ی اشیاء؛ داخل مش را سیاه می‌کند)، `--find متن1,متن2` (فهرست نام اشیاء)، `--list-collections`.

## ۵. تنظیم نواحی (`views.json`)
- `x_half_width`: نیم‌عرض مبنا به متر (۰٫۴۱۵). خط وسط بدن `x = 0` است. مقادیر `x` کسری از `[-۰٫۴۱۵ تا ۰٫۴۱۵]` هستند.
- هر ناحیه یک جعبه `[x0,x1,y0,y1,z0,z1]` دارد. `view_boxes` جعبه‌ی جدا برای یک نما تعریف می‌کند.
- جهت‌ها: جلوی بدن ‑Y، سمت راست بیمار ‑X، بالا +Z.
- نماهای کناری/داخلی با برش ساخته می‌شوند: دوربین روی لبه‌ی جعبه است و هر چیز بیرون آن حذف می‌شود.

محدودیت‌های شناخته‌شده: نمای داخلی (medial) بازو و نمای پشتی (dorsal) پا، به‌خاطر برش از بدنه‌ی متصل، ممکن است یک سطح برش تیره داشته باشند.

## ۶. ثبت نقاط طب سوزنی
نقاط را روی تصویر نکشید. به‌صورت داده نگه دارید:
```json
{ "point": "LI4", "image": "right_hand_dorsal.png", "x": 0.42, "y": 0.61 }
```
`x` و `y` نسبت به عرض و ارتفاع تصویر هستند (۰ تا ۱، مبدأ بالا-چپ). مکان نقاط را از **WHO Standard Acupuncture Point Locations** (۲۰۰۸) بگیرید و خودتان روی تصویر بگذارید. از تصاویر آن کتاب مستقیم استفاده نکنید.

## ۷. لایسنس و ذکر منبع
- Z-Anatomy: **CC BY-SA 4.0**؛ مبنای آن BodyParts3D (**CC BY-SA 2.1 JP**).
- باید منبع را ذکر کنید (مثلاً در صفحه‌ی About نرم‌افزار): نام Z-Anatomy و BodyParts3D / Anatomography، لینک لایسنس، و اینکه تصاویر از مدل تغییر یافته و رندر شده‌اند.
- شرط Share-Alike روی خود **تصاویر رندرشده** (اثر مشتق) اعمال می‌شود و در مورد کد نرم‌افزار جای بحث دارد. قبل از انتشار تجاری، لایسنس‌ها را بررسی کنید یا مشورت حقوقی بگیرید.
