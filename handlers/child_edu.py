"""Talabalar va O'qituvchilar uchun Ta'lim Boti."""
import json
import re
from datetime import datetime

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Message

from database import db
from filters import IsAdmin, NotCommand
from keyboards import inline as kb
from middlewares import Ctx
from services import ai
from states import EduStates
from utils import chunk_text, h, safe_edit

DAYS = ["Dushanba", "Seshanba", "Chorshanba", "Payshanba", "Juma", "Shanba", "Yakshanba"]
GEN_TYPES = {"referat": "📄 Referat", "slayd": "🖼 Slayd (taqdimot)", "kurs": "📘 Kurs ishi"}
GEN_PROMPTS = {
    "referat": "Quyidagi mavzuda referat yoz: Kirish, 3-4 ta asosiy bo'lim (har biri kamida 2-3 paragraf), Xulosa va Foydalanilgan adabiyotlar ro'yxati. Mavzu: ",
    "slayd": "Quyidagi mavzuda 10-12 slaydlik taqdimot tuzilmasi va matnini yoz. Har bir slayd: 'Slayd N: Sarlavha' va 3-5 qisqa punkt, oxirida spiker uchun izoh. Mavzu: ",
    "kurs": "Quyidagi mavzuda kurs ishi yoz: Mundarija (reja), Kirish (dolzarbligi, maqsad, vazifalar, obyekt, predmet), 2-3 bob (har biri 2-3 paragraf), Xulosa, Adabiyotlar. Mavzu: ",
}
SYSTEM = "Sen tajribali o'qituvchi va akademik yozuvchisan. Foydalanuvchi qaysi tilda yozsa, shu tilda (odatda o'zbek tilida) javob ber."


def student_menu():
    return kb.build([[("📅 Dars jadvali", "edu:sched"), ("📝 Eslatmalar", "edu:note")],
                     [("✍️ Referat / Slayd / Kurs ishi (AI)", "edu:gen")],
                     [("📚 Kitoblar (PDF)", "edu:books")],
                     [("🔄 Rolni o'zgartirish", "edu:role")]])


def teacher_menu():
    return kb.build([[("🧪 Test / Quiz (AI)", "edu:quiz")],
                     [("👥 O'quvchilar", "edu:stud"), ("✅ Davomat", "edu:att")],
                     [("📖 Dars ishlanmasi (AI)", "edu:plan"), ("📊 Hisobot", "edu:rep")],
                     [("📚 Kitoblar (PDF)", "edu:books")],
                     [("🔄 Rolni o'zgartirish", "edu:role")]])


def role_kb():
    return kb.build([[("🎓 Men talabaman", "edu:setrole:student")], [("👩‍🏫 Men o'qituvchiman", "edu:setrole:teacher")]])


def home_kb():
    return kb.build([[("🏠 Menyu", "edu:menu")]])


def get_router() -> Router:
    r = Router(name="child_edu")

    async def role_of(ctx: Ctx, uid: int) -> str | None:
        u = await db.get_user(ctx.bot_pk, uid)
        return u["role"] if u else None

    async def show_menu(target, ctx: Ctx, uid: int, edit: bool = False):
        role = await role_of(ctx, uid)
        if not role:
            text, markup = "👋 Kim sifatida foydalanasiz?", role_kb()
        elif role == "teacher":
            text, markup = "👩‍🏫 <b>O'qituvchi menyusi</b>", teacher_menu()
        else:
            text, markup = "🎓 <b>Talaba menyusi</b>", student_menu()
        if edit:
            await safe_edit(target, text, markup)
        else:
            await target.answer(text, reply_markup=markup)

    async def ai_call(m: Message, ctx: Ctx, prompt: str, json_mode: bool = False) -> str | None:
        await m.bot.send_chat_action(m.chat.id, "typing")
        try:
            return await ai.chat_with_keys(ctx.bot_pk, [("user", prompt)], SYSTEM, json_mode)
        except ai.NoKeyError:
            await m.answer("⚠️ AI hali faol emas — bot egasi /admin → API kalitlar orqali Gemini kalitini ulashi kerak.")
        except ai.AIError as e:
            await m.answer(f"⚠️ AI xatosi: {h(e)}")
        return None

    # ------------------------------------------------------------- start
    @r.message(CommandStart())
    async def start(m: Message, state: FSMContext, ctx: Ctx):
        await state.clear()
        extra = "\n\n🛠 Boshqaruv: /admin" if ctx.is_admin(m.from_user.id) else ""
        await m.answer(f"🎓 Salom, <b>{h(m.from_user.full_name)}</b>! Ta'lim botiga xush kelibsiz.{extra}")
        await show_menu(m, ctx, m.from_user.id)

    @r.callback_query(F.data == "edu:menu")
    async def cb_menu(c: CallbackQuery, state: FSMContext, ctx: Ctx):
        await state.clear()
        await show_menu(c, ctx, c.from_user.id, edit=True)
        await c.answer()

    @r.callback_query(F.data == "edu:role")
    async def cb_role(c: CallbackQuery):
        await safe_edit(c, "👋 Kim sifatida foydalanasiz?", role_kb())
        await c.answer()

    @r.callback_query(F.data.startswith("edu:setrole:"))
    async def cb_setrole(c: CallbackQuery, ctx: Ctx):
        await db.set_role(ctx.bot_pk, c.from_user.id, c.data.split(":")[2])
        await show_menu(c, ctx, c.from_user.id, edit=True)
        await c.answer("✅ Saqlandi")

    # ----------------------------------------------------- dars jadvali
    @r.callback_query(F.data == "edu:sched")
    async def cb_sched(c: CallbackQuery, state: FSMContext, ctx: Ctx):
        await state.clear()
        sched = await db.get_schedule(ctx.bot_pk, c.from_user.id)
        text = "📅 <b>Dars jadvali</b>\n\n" + "\n".join(
            f"<b>{d}:</b> {h(sched.get(i, '—'))}" for i, d in enumerate(DAYS))
        rows = [[(d, f"edu:sd:{i}") for i, d in enumerate(DAYS[j:j + 3], j)] for j in range(0, 7, 3)]
        rows.append([("🏠 Menyu", "edu:menu")])
        await safe_edit(c, text + "\n\nTahrirlash uchun kunni tanlang:", kb.build(rows))
        await c.answer()

    @r.callback_query(F.data.startswith("edu:sd:"))
    async def cb_sd(c: CallbackQuery, state: FSMContext):
        day = int(c.data.split(":")[2])
        await state.set_state(EduStates.sched_text)
        await state.update_data(day=day)
        await safe_edit(c, f"📅 <b>{DAYS[day]}</b> darslarini yozing (masalan: 1) Matematika 8:30, 2) Fizika 10:00).\nTozalash uchun «-» yuboring.",
                        kb.cancel_to("edu:sched"))
        await c.answer()

    @r.message(EduStates.sched_text, F.text, NotCommand())
    async def sched_save(m: Message, state: FSMContext, ctx: Ctx):
        day = (await state.get_data())["day"]
        text = "" if m.text.strip() == "-" else m.text.strip()[:1000]
        await db.set_schedule(ctx.bot_pk, m.from_user.id, day, text)
        await state.clear()
        await m.answer(f"✅ {DAYS[day]} jadvali saqlandi.", reply_markup=kb.build([[("📅 Jadval", "edu:sched")], [("🏠 Menyu", "edu:menu")]]))

    # -------------------------------------------------------- eslatmalar
    @r.callback_query(F.data == "edu:note")
    async def cb_notes(c: CallbackQuery, state: FSMContext, ctx: Ctx):
        await state.clear()
        notes = await db.list_notes(ctx.bot_pk, c.from_user.id)
        text = "📝 <b>Eslatmalar</b>\n\n" + ("\n".join(f"• {h(n['text'][:80])}" for n in notes) if notes else "Hozircha yo'q.")
        rows = [[(f"🗑 {n['text'][:30]}", f"edu:nd:{n['id']}")] for n in notes]
        rows.append([("➕ Qo'shish", "edu:na")])
        rows.append([("🏠 Menyu", "edu:menu")])
        await safe_edit(c, text, kb.build(rows))
        await c.answer()

    @r.callback_query(F.data == "edu:na")
    async def cb_note_add(c: CallbackQuery, state: FSMContext):
        await state.set_state(EduStates.note_text)
        await safe_edit(c, "📝 Eslatma matnini yuboring:", kb.cancel_to("edu:note"))
        await c.answer()

    @r.message(EduStates.note_text, F.text, NotCommand())
    async def note_save(m: Message, state: FSMContext, ctx: Ctx):
        await db.add_note(ctx.bot_pk, m.from_user.id, m.text.strip()[:1000])
        await state.clear()
        await m.answer("✅ Saqlandi.", reply_markup=kb.build([[("📝 Eslatmalar", "edu:note")], [("🏠 Menyu", "edu:menu")]]))

    @r.callback_query(F.data.startswith("edu:nd:"))
    async def cb_note_del(c: CallbackQuery, state: FSMContext, ctx: Ctx):
        await db.del_note(ctx.bot_pk, c.from_user.id, int(c.data.split(":")[2]))
        await c.answer("🗑 O'chirildi")
        await cb_notes(c, state, ctx)

    # ------------------------------------- Referat / Slayd / Kurs ishi (AI)
    @r.callback_query(F.data == "edu:gen")
    async def cb_gen(c: CallbackQuery):
        rows = [[(v, f"edu:gen:{k}")] for k, v in GEN_TYPES.items()] + [[("🏠 Menyu", "edu:menu")]]
        await safe_edit(c, "✍️ Nimani tayyorlaymiz?", kb.build(rows))
        await c.answer()

    @r.callback_query(F.data.startswith("edu:gen:"))
    async def cb_gen_type(c: CallbackQuery, state: FSMContext):
        kind = c.data.split(":")[2]
        await state.set_state(EduStates.gen_topic)
        await state.update_data(kind=kind)
        await safe_edit(c, f"{GEN_TYPES[kind]}\n\n📌 Mavzuni yozing (fan va talablarni ham ko'rsatsangiz yaxshi):", kb.cancel_to("edu:menu"))
        await c.answer()

    @r.message(EduStates.gen_topic, F.text, NotCommand())
    async def gen_do(m: Message, state: FSMContext, ctx: Ctx):
        kind = (await state.get_data())["kind"]
        await state.clear()
        wait = await m.answer("⏳ AI tayyorlayapti, 20-60 soniya kuting...")
        text = await ai_call(m, ctx, GEN_PROMPTS[kind] + m.text.strip())
        await wait.delete()
        if not text:
            return
        for part in chunk_text(text):
            await m.answer(part, parse_mode=None)
        await m.answer_document(BufferedInputFile(text.encode("utf-8"), f"{kind}.txt"),
                                caption="📎 To'liq matn fayl ko'rinishida", reply_markup=home_kb())

    # --------------------------------------------------------- Kitoblar
    @r.callback_query(F.data == "edu:books")
    async def cb_books(c: CallbackQuery, ctx: Ctx):
        books = await db.list_books(ctx.bot_pk)
        if not books:
            await safe_edit(c, "📚 Kitoblar bazasi hozircha bo'sh.", home_kb())
        else:
            rows = [[(f"📕 {b['title']}", f"bk:{b['id']}")] for b in books] + [[("🏠 Menyu", "edu:menu")]]
            await safe_edit(c, "📚 <b>Kitoblar bazasi</b>", kb.build(rows))
        await c.answer()

    @r.callback_query(F.data.startswith("bk:"))
    async def cb_book(c: CallbackQuery, bot: Bot, ctx: Ctx):
        b = await db.get_book(ctx.bot_pk, int(c.data.split(":")[1]))
        await c.answer()
        if b:
            try:
                await bot.send_document(c.from_user.id, b["file_id"], caption=f"📕 {h(b['title'])}")
            except TelegramAPIError:
                await bot.send_message(c.from_user.id, "❌ Faylni yuborib bo'lmadi.")

    # admin: kitob qo'shish
    @r.callback_query(F.data == "adm:book_add", IsAdmin())
    async def book_add(c: CallbackQuery, state: FSMContext):
        await state.set_state(EduStates.book_file)
        await safe_edit(c, "📚 Kitob/PDF faylini yuboring:", kb.cancel_to("adm:menu"))
        await c.answer()

    @r.message(EduStates.book_file, F.document)
    async def book_file(m: Message, state: FSMContext):
        await state.update_data(file_id=m.document.file_id)
        await state.set_state(EduStates.book_title)
        await m.answer("✏️ Kitob nomini yozing:")

    @r.message(EduStates.book_title, F.text, NotCommand())
    async def book_title(m: Message, state: FSMContext, ctx: Ctx):
        fid = (await state.get_data())["file_id"]
        await db.add_book(ctx.bot_pk, m.text.strip()[:100], fid)
        await state.clear()
        await m.answer("✅ Kitob qo'shildi.", reply_markup=kb.back_admin())

    # ------------------------------------------- O'qituvchi: Test / Quiz
    @r.callback_query(F.data == "edu:quiz")
    async def cb_quiz(c: CallbackQuery, state: FSMContext):
        await state.set_state(EduStates.quiz_topic)
        await safe_edit(c, "🧪 Mavzu va savollar sonini yozing.\nMasalan: <code>Fotosintez, 8</code> (standart: 5, maks: 15)",
                        kb.cancel_to("edu:menu"))
        await c.answer()

    @r.message(EduStates.quiz_topic, F.text, NotCommand())
    async def quiz_do(m: Message, state: FSMContext, ctx: Ctx):
        mt = re.match(r"^(.*?)[,;\s]+(\d{1,2})$", m.text.strip())
        topic, n = (mt.group(1), min(int(mt.group(2)), 15)) if mt else (m.text.strip(), 5)
        n = max(n, 1)
        await state.clear()
        wait = await m.answer("⏳ Savollar tuzilmoqda...")
        prompt = (f"'{topic}' mavzusida {n} ta test savoli tuz. Faqat JSON massiv qaytar, boshqa matn yo'q: "
                  '[{"q": "savol", "options": ["A variant", "B variant", "C variant", "D variant"], "correct": 0}] '
                  "(correct — to'g'ri variant indeksi 0..3, savol 250 belgidan, variant 90 belgidan oshmasin).")
        raw = await ai_call(m, ctx, prompt, json_mode=True)
        await wait.delete()
        if not raw:
            return
        try:
            items = json.loads(re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.M).strip())
            sent = 0
            for it in items[:n]:
                opts = [str(o)[:99] for o in it["options"]][:10]
                await m.answer_poll(question=f"{sent + 1}. {it['q']}"[:299], options=opts, type="quiz",
                                    correct_option_id=int(it["correct"]), is_anonymous=False)
                sent += 1
            await m.answer(f"✅ {sent} ta quiz tayyor. Ularni o'quvchilarga forward qilishingiz mumkin.", reply_markup=home_kb())
        except (ValueError, KeyError, TypeError, TelegramAPIError):
            await m.answer("⚠️ AI javobini quizga aylantirib bo'lmadi, matn ko'rinishida:")
            for part in chunk_text(raw):
                await m.answer(part, parse_mode=None)

    # ------------------------------------------- Dars ishlanmasi (konspekt)
    @r.callback_query(F.data == "edu:plan")
    async def cb_plan(c: CallbackQuery, state: FSMContext):
        await state.set_state(EduStates.plan_topic)
        await safe_edit(c, "📖 Fan, sinf va dars mavzusini yozing.\nMasalan: <code>Biologiya, 8-sinf, Hujayra tuzilishi</code>",
                        kb.cancel_to("edu:menu"))
        await c.answer()

    @r.message(EduStates.plan_topic, F.text, NotCommand())
    async def plan_do(m: Message, state: FSMContext, ctx: Ctx):
        await state.clear()
        wait = await m.answer("⏳ Dars ishlanmasi tuzilmoqda...")
        text = await ai_call(m, ctx, "Quyidagi dars uchun batafsil dars ishlanmasi (konspekt) tuz: mavzu, maqsad va vazifalar, "
                                     "jihozlar, dars bosqichlari (vaqt bilan), yangi mavzu bayoni, interaktiv metodlar, mustahkamlash "
                                     "savollari, baholash, uyga vazifa. Ma'lumot: " + m.text.strip())
        await wait.delete()
        if text:
            for part in chunk_text(text):
                await m.answer(part, parse_mode=None)
            await m.answer_document(BufferedInputFile(text.encode("utf-8"), "konspekt.txt"), reply_markup=home_kb())

    # ------------------------------ O'quvchilar ro'yxati va davomat daftari
    @r.callback_query(F.data == "edu:stud")
    async def cb_students(c: CallbackQuery, state: FSMContext, ctx: Ctx):
        await state.clear()
        studs = await db.list_students(ctx.bot_pk, c.from_user.id)
        text = "👥 <b>O'quvchilar</b>\n\n" + ("\n".join(f"{i}. {h(s['name'])}" for i, s in enumerate(studs, 1)) if studs else "Ro'yxat bo'sh.")
        rows = [[(f"🗑 {s['name']}", f"edu:sdel:{s['id']}")] for s in studs]
        rows.append([("➕ O'quvchi qo'shish", "edu:sadd")])
        rows.append([("🏠 Menyu", "edu:menu")])
        await safe_edit(c, text, kb.build(rows))
        await c.answer()

    @r.callback_query(F.data == "edu:sadd")
    async def cb_sadd(c: CallbackQuery, state: FSMContext):
        await state.set_state(EduStates.student_name)
        await safe_edit(c, "👤 O'quvchi(lar) ism-familiyasini yozing (bir nechta bo'lsa — har birini yangi qatordan):",
                        kb.cancel_to("edu:stud"))
        await c.answer()

    @r.message(EduStates.student_name, F.text, NotCommand())
    async def student_save(m: Message, state: FSMContext, ctx: Ctx):
        names = [n.strip()[:60] for n in m.text.splitlines() if n.strip()][:60]
        for n in names:
            await db.add_student(ctx.bot_pk, m.from_user.id, n)
        await state.clear()
        await m.answer(f"✅ {len(names)} ta o'quvchi qo'shildi.", reply_markup=kb.build([[("👥 Ro'yxat", "edu:stud")], [("🏠 Menyu", "edu:menu")]]))

    @r.callback_query(F.data.startswith("edu:sdel:"))
    async def cb_sdel(c: CallbackQuery, state: FSMContext, ctx: Ctx):
        await db.del_student(ctx.bot_pk, c.from_user.id, int(c.data.split(":")[2]))
        await c.answer("🗑 O'chirildi")
        await cb_students(c, state, ctx)

    async def render_att(c: CallbackQuery, ctx: Ctx):
        today = datetime.now().strftime("%Y-%m-%d")
        studs = await db.list_students(ctx.bot_pk, c.from_user.id)
        if not studs:
            await safe_edit(c, "👥 Avval o'quvchilar ro'yxatini kiriting.", kb.build([[("➕ O'quvchilar", "edu:stud")], [("🏠 Menyu", "edu:menu")]]))
            return
        ids = [s["id"] for s in studs]
        await db.ensure_attendance(ids, today)
        att = await db.attendance_day(ids, today)
        rows = [[(("✅ " if att.get(s["id"]) else "❌ ") + s["name"], f"att:{s['id']}")] for s in studs]
        rows.append([("🏠 Menyu", "edu:menu")])
        await safe_edit(c, f"✅ <b>Davomat — {today}</b>\nHar bir o'quvchini bosib kelgan/kelmaganini belgilang:", kb.build(rows))

    @r.callback_query(F.data == "edu:att")
    async def cb_att(c: CallbackQuery, ctx: Ctx):
        await render_att(c, ctx)
        await c.answer()

    @r.callback_query(F.data.startswith("att:"))
    async def cb_att_toggle(c: CallbackQuery, ctx: Ctx):
        today = datetime.now().strftime("%Y-%m-%d")
        await db.toggle_attendance(ctx.bot_pk, c.from_user.id, int(c.data.split(":")[1]), today)
        await render_att(c, ctx)
        await c.answer()

    @r.callback_query(F.data == "edu:rep")
    async def cb_report(c: CallbackQuery, ctx: Ctx):
        rows = await db.attendance_report(ctx.bot_pk, c.from_user.id)
        if not rows:
            await safe_edit(c, "📊 Hisobot uchun ma'lumot yo'q.", home_kb())
        else:
            lines = [f"• {h(x['name'])}: {x['p']}/{x['t']} ({round(100 * x['p'] / x['t']) if x['t'] else 0}%)" for x in rows]
            await safe_edit(c, "📊 <b>Davomat hisoboti</b> (keldi/jami dars)\n\n" + "\n".join(lines), home_kb())
        await c.answer()

    # ------------------------------------------------------------ fallback
    @r.message(StateFilter(None), F.text, NotCommand())
    async def fallback(m: Message, ctx: Ctx):
        await show_menu(m, ctx, m.from_user.id)

    return r
