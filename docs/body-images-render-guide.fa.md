# راهنمای تهیه‌ی تصاویر بدن برای نرم‌افزار طب سوزنی (رندر از مدل سه‌بعدی آزاد)

هدف: ساخت یک ست کامل تصویر یکدست از بدن (سر و صورت، گردن، تنه، دست و پا) در نماهای روبرو، پشت و جانبی، با لایسنس قابل‌استفاده در نرم‌افزار.

> اسکریپت `tools/blender/render_views.py` هنوز روی مدل واقعی اجرا نشده است. مقادیر `views.json` تخمینی‌اند و بعد از اولین رندر باید تنظیم شوند.

## ۱. نصب ابزارها
1. **Blender** نسخه‌ی ۴.x از blender.org (رایگان).
2. مدل **Z-Anatomy** را از z-anatomy.com یا صفحه‌ی GitHub آن (`Z-Anatomy`) دانلود کنید. فایل `.blend` است.

## ۲. بررسی ساختار مدل
```bash
blender -b Z-Anatomy.blend --python tools/blender/render_views.py -- --list-collections
```
نام collectionها را ببینید. معمولاً collection مربوط به پوست یا «Regions of human body» برای نمای سطحی بدن مناسب است و collectionهای عضلات و اسکلت برای نمای عمقی. برای نرم‌افزار طب سوزنی معمولاً نمای **پوست/سطح بدن** لازم است.

## ۳. رندر آزمایشی (فقط سر و دست راست)
```bash
blender -b Z-Anatomy.blend --python tools/blender/render_views.py -- \
    --out build/test --collections "نام collection پوست" --regions head,right_hand --size 1500
```
خروجی: `build/test/head_front.png`، `right_hand_palmar.png`، … و `manifest.json`.

### رندر با CPU (برای کارت گرافیک ضعیف یا Intel)
اگر هنگام کار با Blender ویندوز با خطای `VIDEO_TDR_FAILURE` ریست می‌شود، رندر را با CPU انجام دهید. کندتر است، ولی GPU را درگیر نمی‌کند:
```bash
blender -b Z-Anatomy.blend --python tools/blender/render_views.py -- --engine cpu --samples 24 --out build/test --collections "9: Regions of human body" --regions body --size 1000
```
با `--samples` کیفیت را بالا و پایین ببرید. `--outline` خط دور تصویر (Freestyle) اضافه می‌کند ولی کند و پرمصرف است.

## ۴. تنظیم جهت‌ها و جعبه‌های ناحیه‌ها
اسکریپت فرض می‌کند:
- جلوی بدن به سمت **‑Y** است،
- سمت راست بیمار **‑X** و سمت چپ او **+X** است،
- بالا **+Z** است و مدل در وضعیت آناتومیک (کف دست‌ها رو به جلو).

اگر نمای «front» پشت بدن را نشان داد، در `views.json` جهت‌های `front` و `back` و همچنین `right` و `left` را جابه‌جا کنید.

هر ناحیه در `views.json` یک جعبه به‌صورت کسری از ارتفاع و عرض کل بدن است، `[x0,x1,y0,y1,z0,z1]`. بعد از دیدن رندر آزمایشی، همین اعداد را تنظیم کنید. نماهای داخلی (medial) با برش خوردن بدنه ساخته می‌شوند: دوربین روی لبه‌ی جعبه قرار می‌گیرد و هر چیز بیرون جعبه (تنه، دست دیگر) حذف می‌شود.

## ۵. رندر کامل
```bash
blender -b Z-Anatomy.blend --python tools/blender/render_views.py -- \
    --out build/body-views --collections "نام collection پوست" --size 2400
```
نماها: body، head، neck، torso، arm، hand، leg، foot برای هر دو سمت، که نام آن‌ها با برچسب‌های palmar، dorsal، plantar، lateral، medial ساخته می‌شود. خروجی PNG با پس‌زمینه‌ی شفاف است.

اگر وکتور SVG می‌خواهید، PNG را با Inkscape (Trace Bitmap) یا `potrace` تبدیل کنید. برای دقت لازم برای نقاط، PNG با رزولوشن بالا معمولاً کافی است.

## ۶. ثبت نقاط طب سوزنی
نقاط را روی تصویر نکشید. به‌صورت داده نگه دارید:
```json
{ "point": "LI4", "image": "right_hand_dorsal.png", "x": 0.42, "y": 0.61 }
```
`x` و `y` نسبت به عرض و ارتفاع تصویر هستند (۰ تا ۱، مبدأ بالا-چپ). فایل `manifest.json` ابعاد، محورها و جعبه‌ی هر تصویر را ثبت می‌کند، پس اگر بعداً تصاویر را دوباره رندر کردید، می‌توانید نقاط را با محاسبه به تصویر جدید برگردانید. مکان نقاط را از **WHO Standard Acupuncture Point Locations** (۲۰۰۸) بگیرید و خودتان روی تصویر بگذارید. از تصاویر آن کتاب مستقیم استفاده نکنید.

## ۷. لایسنس و ذکر منبع
- Z-Anatomy: **CC BY-SA 4.0**؛ مبنای آن BodyParts3D (**CC BY-SA 2.1 JP**).
- باید منبع را ذکر کنید (مثلاً در صفحه‌ی About نرم‌افزار): نام Z-Anatomy و BodyParts3D / Anatomography، لینک لایسنس، و اینکه تصاویر از مدل تغییر یافته و رندر شده‌اند.
- شرط Share-Alike روی خود **تصاویر رندرشده** (اثر مشتق) اعمال می‌شود و در مورد کد نرم‌افزار جای بحث دارد. قبل از انتشار تجاری، لایسنس‌ها را یک بار بررسی کنید یا مشورت حقوقی بگیرید.
