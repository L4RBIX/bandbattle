"""BAND BATTLE: What's your band, Kazakhstan?
Telegram bot prototype for the IDP IELTS Kazakhstan Case Challenge (Digital Community track).

Loop: YouTube Shorts (deep link) -> bot -> voice answer -> practice band + fixes
      -> streak / school leaderboard / referrals -> Band Card share -> back to YouTube.
"""
import asyncio
import html
import logging
import os
import tempfile
from urllib.parse import quote

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (BotCommand, BufferedInputFile, CallbackQuery, InlineKeyboardButton,
                           InlineKeyboardMarkup, KeyboardButton, Message, ReplyKeyboardMarkup)

import card
import content
import db
import scoring

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("bandbattle")

BOT_TOKEN = os.environ["BOT_TOKEN"]
ADMIN_IDS = {int(x) for x in os.getenv("ADMIN_IDS", "").replace(" ", "").split(",") if x}
DAILY_LIMIT = int(os.getenv("DAILY_LIMIT", "15"))
MIN_VOICE_SEC = int(os.getenv("MIN_VOICE_SEC", "20"))
YOUTUBE_URL = os.getenv("YOUTUBE_URL", "https://www.youtube.com/@IDP.IELTS.KAZAKHSTAN")
COMMUNITY_URL = os.getenv("COMMUNITY_URL", "https://t.me/idpieltskazakhstan")
BOOK_URL = os.getenv("BOOK_URL", "https://ielts.idp.com/kazakhstan")
REFS_FOR_REWARD = 3

router = Router()
BOT_USERNAME = "BandBattleBot"
BUSY: set[int] = set()

# ---------- keyboards ----------
B_CHALLENGE = "🎤 Today's Challenge"
B_GUESS = "🎯 Guess the Band"
B_BOARD = "🏆 Leaderboard"
B_ME = "🔥 My Progress"
B_INVITE = "👥 Invite Friends"
B_YT = "📺 YouTube"
B_BOOK = "📝 Book IELTS"
MENU_BUTTONS = {B_CHALLENGE, B_GUESS, B_BOARD, B_ME, B_INVITE, B_YT, B_BOOK}


def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=B_CHALLENGE)],
            [KeyboardButton(text=B_GUESS), KeyboardButton(text=B_BOARD)],
            [KeyboardButton(text=B_ME), KeyboardButton(text=B_INVITE)],
            [KeyboardButton(text=B_YT), KeyboardButton(text=B_BOOK)],
        ],
        resize_keyboard=True,
        input_field_placeholder="Send a voice answer 🎙",
    )


def ikb(rows) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=rows)


def grid(items, prefix, per_row=2):
    rows, row = [], []
    for it in items:
        row.append(InlineKeyboardButton(text=it, callback_data=f"{prefix}:{it}"))
        if len(row) == per_row:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return rows


def book_url(uid, src="bot"):
    return f"{BOOK_URL}?utm_source=telegram&utm_medium=bandbattle_bot&utm_campaign=band_battle&utm_content={src}"


def share_url(uid):
    link = f"https://t.me/{BOT_USERNAME}?start=ref_{uid}"
    text = "I just checked my IELTS Speaking band in 60 seconds. Beat my school? #WhatsYourBand"
    return f"https://t.me/share/url?url={quote(link)}&text={quote(text)}"


# ---------- onboarding ----------
class Onb(StatesGroup):
    city = State()
    school = State()
    school_custom = State()
    target = State()


def todays_question():
    import datetime as _dt
    idx = _dt.date.fromisoformat(db.today()).toordinal() % len(content.QUESTIONS)
    return idx, content.QUESTIONS[idx]


def question_text():
    idx, (title, bullets) = todays_question()
    pts = "\n".join(f"  • {b}" for b in bullets)
    return idx, (
        f"🎤 <b>Today's Challenge</b>\n\n<b>{html.escape(title)}</b>\nYou should say:\n{pts}\n\n"
        f"🎙 Hold the mic and answer for <b>1 to 2 minutes</b>.\n"
        f"You'll get your estimated band and 3 personal fixes in about 30 seconds."
    )


@router.message(CommandStart())
async def start(m: Message, command: CommandObject, state: FSMContext):
    uid = m.from_user.id
    payload = (command.args or "").strip()[:60]
    u = db.get_user(uid)
    if not u:
        returning = db.ever_started(uid)  # /reset users must not re-trigger referrals
        ref_by = None
        source = payload or "direct"
        if payload.startswith("ref_"):
            try:
                ref_by = int(payload[4:])
                source = "referral"
            except ValueError:
                ref_by = None
            if ref_by == uid:
                ref_by = None
        db.create_user(uid, m.from_user.first_name, m.from_user.username, source, ref_by)
        db.log_event(uid, "start", source)
        if ref_by and not returning and db.get_user(ref_by):
            n = db.add_referral(ref_by)
            try:
                if n == REFS_FOR_REWARD:
                    await m.bot.send_message(
                        ref_by,
                        f"🎁 <b>{REFS_FOR_REWARD} friends joined!</b> You unlocked a free IDP Mock Test.\n"
                        f"Voucher: <code>BB-{ref_by % 100000:05d}</code>\n"
                        f"<i>Prototype demo: in the live campaign IDP issues real vouchers.</i>",
                    )
                else:
                    await m.bot.send_message(
                        ref_by, f"👥 A friend joined Band Battle with your link! +15 XP  ({n}/{REFS_FOR_REWARD} for a free Mock Test)")
            except Exception:  # noqa: BLE001
                pass
    else:
        db.log_event(uid, "restart", payload)

    u = db.get_user(uid)
    if payload.startswith("guess"):
        await state.update_data(after_onb="guess")
    if u["school"]:
        await m.answer(f"Welcome back, {html.escape(m.from_user.first_name or '')}! 🔥", reply_markup=main_menu())
        if payload.startswith("guess"):
            await send_guess(m, 0)
        return

    await m.answer(
        "🔥 <b>BAND BATTLE: What's your band, Kazakhstan?</b>\n\n"
        "Send a voice answer to an IELTS Speaking question and get your <b>estimated band</b> "
        "with 3 personal fixes in 30 seconds.\nThen battle for your school on the national leaderboard. 🏆\n\n"
        "3 quick taps to set up. Which city are you in?",
        reply_markup=ikb(grid(content.CITIES, "city", 2)),
    )
    await state.set_state(Onb.city)


@router.callback_query(F.data.startswith("city:"))
async def pick_city(c: CallbackQuery, state: FSMContext):
    city = c.data.split(":", 1)[1]
    db.update_user(c.from_user.id, city=city)
    await state.set_state(Onb.school)
    rows = grid(content.SCHOOLS, "school", 2)
    rows.append([InlineKeyboardButton(text="✍️ Type my school", callback_data="school:__custom")])
    await c.message.edit_text(f"📍 {html.escape(city)}. Which school do you play for?", reply_markup=ikb(rows))
    await c.answer()


@router.callback_query(F.data.startswith("school:"))
async def pick_school(c: CallbackQuery, state: FSMContext):
    val = c.data.split(":", 1)[1]
    if val == "__custom":
        await state.set_state(Onb.school_custom)
        await c.message.edit_text("✍️ Type your school name (for example: School-gymnasium No.12):")
        await c.answer()
        return
    await _set_school(c.from_user.id, val)
    await state.set_state(Onb.target)
    await c.message.edit_text("🎯 What band do you need?", reply_markup=ikb(grid(content.TARGETS, "target", 3)))
    await c.answer()


@router.message(Onb.school_custom, F.text)
async def custom_school(m: Message, state: FSMContext):
    name = m.text.strip()[:40]
    await _set_school(m.from_user.id, name)
    await state.set_state(Onb.target)
    await m.answer("🎯 What band do you need?", reply_markup=ikb(grid(content.TARGETS, "target", 3)))


async def _set_school(uid, school):
    u = db.get_user(uid)
    city = (u["city"] if u else None) or "Other"
    db.update_user(uid, school=f"{school} · {city}")


@router.callback_query(F.data.startswith("target:"))
async def pick_target(c: CallbackQuery, state: FSMContext):
    target = c.data.split(":", 1)[1]
    db.update_user(c.from_user.id, target=target)
    data = await state.get_data()
    await state.clear()
    u = db.get_user(c.from_user.id)
    await c.message.edit_text(
        f"✅ You're in! Team <b>{html.escape(u['school'])}</b>, target <b>{target}</b>.")
    await c.message.answer(
        "Every answer earns XP for you <b>and your school</b>. Daily streaks give bonus XP. "
        f"Invite {REFS_FOR_REWARD} friends and unlock a free IDP Mock Test. 🎁",
        reply_markup=main_menu(),
    )
    if data.get("after_onb") == "guess":
        await send_guess(c.message, 0)
    else:
        _, txt = question_text()
        await c.message.answer(txt)
    await c.answer()


# ---------- daily challenge / scoring ----------
@router.message(F.text == B_CHALLENGE)
@router.message(Command("challenge"))
async def challenge(m: Message):
    if not await ensure_onboarded(m):
        return
    _, txt = question_text()
    await m.answer(txt)


async def ensure_onboarded(m: Message) -> bool:
    u = db.get_user(m.from_user.id)
    if not u or not u["school"]:
        await m.answer("Tap /start to set up your profile first (3 taps).")
        return False
    return True


def bar(v):
    filled = int(round(v))
    return "▰" * filled + "▱" * (9 - filled)


def result_text(res, metrics, gain, u, mode):
    lines = [
        f"🎯 <b>Your estimated band: {res['overall']:.1f}</b>",
        "",
        f"<code>Fluency    {bar(res['fc'])} {res['fc']:.1f}</code>",
        f"<code>Vocabulary {bar(res['lr'])} {res['lr']:.1f}</code>",
        f"<code>Grammar    {bar(res['gra'])} {res['gra']:.1f}</code>",
        "<code>Pronunc.   not assessed in v1</code>",
    ]
    if mode == "voice":
        lines.append(f"\n📊 {metrics['words']} words · {metrics['wpm']} words/min · "
                     f"{metrics['long_pauses']} long pause{'' if metrics['long_pauses'] == 1 else 's'} · {metrics['duration']:.0f}s")
    else:
        lines.append(f"\n📊 {metrics['words']} words · typed answer (fluency estimated from text only)")
    if res["verdict"]:
        lines.append(f"\n💬 {html.escape(res['verdict'])}")
    if res["fixes"]:
        lines.append("\n🔧 <b>Your 3 fixes</b>")
        for i, f in enumerate(res["fixes"], 1):
            why = f" <i>({html.escape(f['why'])})</i>" if f.get("why") else ""
            lines.append(f"{i}. ❌ “{html.escape(f['said'])}”\n    ✅ “{html.escape(f['better'])}”{why}")
    if res["upgrade_phrase"]:
        lines.append(f"\n⬆️ <b>Upgrade phrase:</b> {html.escape(res['upgrade_phrase'])}")
    lines.append(f"\n+{gain['xp_gain']} XP · 🔥 streak {gain['streak']} · for {html.escape(u['school'] or '')}")
    lines.append("<i>🧪 AI practice estimate, not an official IELTS score.</i>")
    return "\n".join(lines)


def target_value(t):
    try:
        return float((t or "0").replace("+", ""))
    except ValueError:
        return 0.0


def result_keyboard(uid, band, target):
    rows = [
        [InlineKeyboardButton(text="🪪 Get my Band Card", callback_data="card")],
        [InlineKeyboardButton(text="🔁 Try again", callback_data="again"),
         InlineKeyboardButton(text="⚔️ Challenge a friend", url=share_url(uid))],
    ]
    rows.append([InlineKeyboardButton(text="🌟 Feature my answer on YouTube", callback_data="feature")])
    if band >= target_value(target) > 0:
        rows.append([InlineKeyboardButton(text="🎓 You hit your target. Ready for the real IELTS?",
                                          callback_data="book:target")])
    return ikb(rows)


async def run_scoring(m: Message, text: str | None, voice_path: str | None, mode: str):
    uid = m.from_user.id
    qid, (title, _) = todays_question()
    status = await m.answer("🎧 Listening to your answer..." if mode == "voice" else "🧠 Reading your answer...")
    try:
        if mode == "voice":
            tr = await asyncio.to_thread(scoring.transcribe, voice_path)
            text = tr["text"]
            metrics = scoring.speech_metrics(text, tr["segments"], tr["duration"])
        else:
            metrics = scoring.speech_metrics(text, [], 0)
        if metrics["words"] < 25:
            await status.edit_text(
                f"🤏 I only caught {metrics['words']} words. Part 2 answers should last 1 to 2 minutes. "
                "Try again and cover all the bullet points!")
            return
        await status.edit_text("🧠 Scoring with IELTS band descriptors...")
        res = await asyncio.to_thread(scoring.assess, title, text, metrics, mode)
    except Exception as e:  # noqa: BLE001
        log.exception("scoring failed: %s", e)
        await status.edit_text("😵 Our examiner-bot is overloaded right now. Please try again in a minute.")
        return
    gain = db.record_answer(uid, qid, res["overall"], res["fc"], res["lr"], res["gra"],
                            metrics["words"], metrics["wpm"], mode)
    db.log_event(uid, "answer", f"{res['overall']}|{res.get('model', '')}")
    u = db.get_user(uid)
    await status.delete()
    await m.answer(result_text(res, metrics, gain, u, mode),
                   reply_markup=result_keyboard(uid, res["overall"], u["target"]))


@router.message(F.voice | F.audio)
async def on_voice(m: Message):
    if not await ensure_onboarded(m):
        return
    uid = m.from_user.id
    media = m.voice or m.audio
    if uid in BUSY:
        await m.answer("⏳ Still scoring your previous answer, one moment...")
        return
    if db.answers_today(uid) >= DAILY_LIMIT:
        await m.answer(f"🔥 You've done {DAILY_LIMIT} answers today. Come back tomorrow to keep your streak!")
        return
    if (media.duration or 0) < MIN_VOICE_SEC:
        await m.answer(f"⏱ That was {media.duration or 0}s. Part 2 needs at least {MIN_VOICE_SEC}s "
                       "(ideally 1 to 2 minutes). Try again!")
        return
    if (getattr(media, "file_size", 0) or 0) > 19 * 1024 * 1024:
        await m.answer("That file is too big. Please send a voice message under 3 minutes.")
        return
    BUSY.add(uid)
    path = None
    try:
        ext = ".ogg"
        if m.audio and m.audio.file_name and "." in m.audio.file_name:
            ext = "." + m.audio.file_name.rsplit(".", 1)[1].lower()[:5]
        fd, path = tempfile.mkstemp(suffix=ext)
        os.close(fd)
        await m.bot.download(media, destination=path)
        await run_scoring(m, None, path, "voice")
    finally:
        BUSY.discard(uid)
        if path and os.path.exists(path):
            os.remove(path)


@router.callback_query(F.data == "again")
async def again(c: CallbackQuery):
    _, txt = question_text()
    await c.message.answer(txt)
    await c.answer()


@router.callback_query(F.data == "feature")
async def feature(c: CallbackQuery):
    db.log_event(c.from_user.id, "feature_optin", "")
    await c.message.answer(
        "🌟 Thanks! You opted in to be featured in a <b>Band Battle</b> Short. "
        "Our team will message you before anything is published. "
        "If you are under 18, we will also ask for a parent's consent.")
    await c.answer("Saved")


# ---------- band card ----------
async def send_card(m: Message, uid: int):
    u = db.get_user(uid)
    a = db.last_answer(uid)
    if not a:
        await m.answer("Send your first voice answer to unlock your Band Card! 🎙")
        return
    png = await asyncio.to_thread(
        card.render_card, u["first_name"], u["school"], u["city"], a["band"], a["fc"], a["lr"], a["gra"],
        u["streak"] or 1, u["xp"] or 0, BOT_USERNAME)
    db.log_event(uid, "card")
    await m.answer_photo(
        BufferedInputFile(png, filename="band_card.png"),
        caption="🪪 Your Band Card. Post it to your story and tag 3 friends. "
                f"Every friend who joins via your link gives +15 XP.\n#WhatsYourBand",
        reply_markup=ikb([[InlineKeyboardButton(text="⚔️ Send to a friend", url=share_url(uid))]]),
    )


@router.callback_query(F.data == "card")
async def card_cb(c: CallbackQuery):
    await c.answer("Drawing your card...")
    await send_card(c.message, c.from_user.id)


@router.message(Command("card"))
async def card_cmd(m: Message):
    if await ensure_onboarded(m):
        await send_card(m, m.from_user.id)


# ---------- guess the band ----------
async def send_guess(m: Message, idx: int):
    s = content.GUESS_SAMPLES[idx]
    rows = [[InlineKeyboardButton(text=o, callback_data=f"g:{idx}:{o}") for o in content.GUESS_OPTIONS]]
    await m.answer(
        f"🎯 <b>Guess the Band</b>  ({idx + 1}/{len(content.GUESS_SAMPLES)})\n\n"
        f"<i>Q: {html.escape(s['question'])}</i>\n\n"
        f"🗣 <b>{html.escape(s['speaker'])}:</b>\n“{html.escape(s['text'])}”\n\n"
        "What band would an examiner give? 👇",
        reply_markup=ikb(rows),
    )


@router.message(F.text == B_GUESS)
@router.message(Command("guess"))
async def guess_entry(m: Message):
    if await ensure_onboarded(m):
        await send_guess(m, 0)


@router.callback_query(F.data.startswith("g:"))
async def guess_answer(c: CallbackQuery):
    _, idx, choice = c.data.split(":")
    idx = int(idx)
    s = content.GUESS_SAMPLES[idx]
    ok = choice == s["band"]
    u = db.get_user(c.from_user.id)
    first_win = ok and u is not None and not db.has_event(c.from_user.id, "guess_ok", str(idx))
    if first_win:
        db.update_user(c.from_user.id, xp=(u["xp"] or 0) + 5)
        db.log_event(c.from_user.id, "guess_ok", str(idx))
    db.log_event(c.from_user.id, "guess", f"{idx}:{choice}:{int(ok)}")
    if ok:
        head = "✅ <b>Correct! +5 XP</b>" if first_win else "✅ <b>Correct!</b>"
    else:
        head = f"❌ Not quite. It's <b>{s['band']}</b>"
    nxt = idx + 1
    if nxt < len(content.GUESS_SAMPLES):
        kb = ikb([[InlineKeyboardButton(text="Next answer ➡️", callback_data=f"gn:{nxt}")]])
    else:
        kb = ikb([[InlineKeyboardButton(text="🎤 Now it's your turn", callback_data="again")]])
    await c.message.edit_reply_markup(reply_markup=None)
    await c.message.answer(f"{head}\n\n💡 {html.escape(s['why'])}\n\n"
                           "<i>Illustrative answers written by the Band Battle team.</i>", reply_markup=kb)
    await c.answer()


@router.callback_query(F.data.startswith("gn:"))
async def guess_next(c: CallbackQuery):
    await send_guess(c.message, int(c.data.split(":")[1]))
    await c.answer()


# ---------- leaderboard / progress / invite ----------
MEDALS = ["🥇", "🥈", "🥉"]


def medal(i):
    return MEDALS[i] if i < 3 else f"{i + 1}."


@router.message(F.text == B_BOARD)
@router.message(Command("leaderboard"))
async def leaderboard(m: Message):
    out = ["🏆 <b>BAND BATTLE LEAGUE</b>\n", "<b>🏫 Schools</b>"]
    for i, r in enumerate(db.top_schools(5)):
        out.append(f"{medal(i)} {html.escape(r['school'])}  <b>{r['xp']} XP</b>  ({r['players']} player{'' if r['players'] == 1 else 's'})")
    out.append("\n<b>🌆 Cities</b>")
    for i, r in enumerate(db.top_cities(5)):
        out.append(f"{medal(i)} {html.escape(r['city'])}  <b>{r['xp']} XP</b>")
    out.append("\n<b>👤 Players</b>")
    for i, r in enumerate(db.top_players(10)):
        tag = " <i>(demo)</i>" if r["demo"] else ""
        out.append(f"{medal(i)} {html.escape(r['first_name'] or 'Student')} · "
                   f"{html.escape(r['school'] or '')}  {r['xp']} XP · best {r['best_band']:.1f}{tag}")
    u = db.get_user(m.from_user.id)
    if u and u["school"]:
        rank, total = db.school_rank(u["school"])
        out.append(f"\nYour school is <b>#{rank}</b> of {total}. Every answer pushes it up. 🚀")
    out.append("\n🔴 Monthly Grand Final: top-3 schools battle LIVE on YouTube.")
    await m.answer("\n".join(out), reply_markup=ikb([[InlineKeyboardButton(text="📺 Watch past battles", url=YOUTUBE_URL)]]))


@router.message(F.text == B_ME)
@router.message(Command("me"))
async def progress(m: Message):
    if not await ensure_onboarded(m):
        return
    u = db.get_user(m.from_user.id)
    bands = db.recent_bands(m.from_user.id)
    trend = " → ".join(f"{b:.1f}" for b in bands) if bands else "no answers yet"
    tv = target_value(u["target"])
    gap = tv - (u["best_band"] or 0)
    gap_txt = "🎉 Target reached!" if bands and gap <= 0 else (f"{gap:.1f} to go" if bands else "")
    rows = [[InlineKeyboardButton(text="🪪 Band Card", callback_data="card")]]
    await m.answer(
        f"🔥 <b>{html.escape(u['first_name'] or '')}</b> · {html.escape(u['school'] or '')}\n\n"
        f"Best band: <b>{(u['best_band'] or 0):.1f}</b>  (target {u['target']}) {gap_txt}\n"
        f"Last answers: {trend}\n"
        f"Streak: <b>{u['streak'] or 0} day{'' if (u['streak'] or 0) == 1 else 's'}</b> · XP: <b>{u['xp'] or 0}</b> · Answers: {u['answers'] or 0}\n"
        f"Friends invited: {u['referrals'] or 0}/{REFS_FOR_REWARD} for a free Mock Test",
        reply_markup=ikb(rows),
    )


@router.message(F.text == B_INVITE)
@router.message(Command("invite"))
async def invite(m: Message):
    if not await ensure_onboarded(m):
        return
    uid = m.from_user.id
    link = f"https://t.me/{BOT_USERNAME}?start=ref_{uid}"
    u = db.get_user(uid)
    await m.answer(
        f"👥 <b>Invite friends, win a Mock Test</b>\n\nYour link:\n<code>{link}</code>\n\n"
        f"Each friend: <b>+15 XP</b> for you and your school.\n"
        f"{REFS_FOR_REWARD} friends: <b>free IDP Mock Test</b> 🎁  (now {u['referrals'] or 0}/{REFS_FOR_REWARD})",
        reply_markup=ikb([[InlineKeyboardButton(text="📤 Share", url=share_url(uid))]]),
    )


@router.message(F.text == B_YT)
async def youtube(m: Message):
    await m.answer(
        "📺 <b>Band Battle on YouTube</b>\n\n"
        "• <b>Band Check</b>: street interviews, one question, instant band\n"
        "• <b>Guess the Band</b>: guess on YouTube, reveal here in the bot\n"
        "• <b>Qazaqlish</b>: the mistakes every Kazakhstani makes (and how to fix them)\n"
        "• <b>Grand Final LIVE</b>: top schools battle every month\n\n"
        "Best voice answers from this bot get featured (with your permission). 🌟",
        reply_markup=ikb([[InlineKeyboardButton(text="▶️ Open YouTube", url=YOUTUBE_URL)],
                          [InlineKeyboardButton(text="💬 Join the community channel", url=COMMUNITY_URL)]]),
    )


async def book_flow(m: Message, uid: int, src: str):
    u = db.get_user(uid)
    db.log_event(uid, "book", src)
    best = u["best_band"] or 0 if u else 0
    tv = target_value(u["target"]) if u else 0
    if best and best >= tv:
        head = (f"🎓 Your best practice band is <b>{best:.1f}</b>, at or above your target {u['target']}.\n"
                "Time to make it official.")
    elif best:
        head = (f"Your best practice band is <b>{best:.1f}</b>, target {u['target']}. "
                "Keep your streak going, or book now to lock in a date.")
    else:
        head = "Ready to take the real test?"
    await m.answer(
        f"{head}\n\n✅ IELTS on computer with IDP\n✅ One Skill Retake: retake just one skill if needed\n"
        "✅ Test centres across Kazakhstan",
        reply_markup=ikb([[InlineKeyboardButton(text="📝 Book with IDP", url=book_url(uid, src))]]),
    )


@router.message(F.text == B_BOOK)
async def book_btn(m: Message):
    await book_flow(m, m.from_user.id, "menu")


@router.callback_query(F.data.startswith("book:"))
async def book_cb(c: CallbackQuery):
    await book_flow(c.message, c.from_user.id, c.data.split(":", 1)[1])
    await c.answer()


# ---------- admin / demo ----------
@router.message(Command("stats"))
async def stats(m: Message):
    if ADMIN_IDS and m.from_user.id not in ADMIN_IDS:
        return
    s = db.stats()
    src = "\n".join(f"  • {html.escape(r['src'])}: {r['c']}" for r in s["sources"]) or "  • none yet"
    avg = f"{s['avg_band']:.2f}" if s["avg_band"] else "n/a"
    await m.answer(
        "📊 <b>Band Battle: live dashboard</b>\n\n"
        f"Users: <b>{s['users']}</b> (onboarded {s['onboarded']})\n"
        f"Answers scored: <b>{s['answers']}</b> · active today: {s['active_today']}\n"
        f"Average band: {avg}\n"
        f"Joined via referral: {s['referrals']}\n"
        f"Band Cards generated: {s['cards']} · Guess plays: {s['guess']}\n"
        f"UGC opt-ins for Shorts: {s['ugc']}\n"
        f"'Book IELTS' clicks: <b>{s['book_clicks']}</b>\n\n"
        f"<b>Where users came from (deep links):</b>\n{src}"
    )


@router.message(Command("reset"))
async def reset(m: Message, state: FSMContext):
    db.delete_user(m.from_user.id)
    await state.clear()
    await m.answer("Profile reset. Tap /start to begin again.")


@router.message(Command("help"))
async def help_cmd(m: Message):
    await m.answer(
        "🎙 Send a <b>voice message</b> answering today's question to get your band.\n"
        "/challenge: today's question\n/guess: Guess the Band\n/leaderboard: league\n"
        "/me: my progress\n/card: my Band Card\n/invite: invite friends\n/reset: start over")


@router.message(F.text)
async def text_fallback(m: Message, state: FSMContext):
    if m.text in MENU_BUTTONS:
        return
    if await state.get_state():
        await m.answer("👆 Please tap one of the buttons above to finish setup (or /start again).")
        return
    if not await ensure_onboarded(m):
        return
    words = len(m.text.split())
    if words >= 40:
        uid = m.from_user.id
        if uid in BUSY:
            return
        if db.answers_today(uid) >= DAILY_LIMIT:
            await m.answer(f"🔥 You've done {DAILY_LIMIT} answers today. Come back tomorrow!")
            return
        BUSY.add(uid)
        try:
            await run_scoring(m, m.text, None, "text")
        finally:
            BUSY.discard(uid)
    else:
        await m.answer("🎙 Send a <b>voice message</b> (1 to 2 min) to answer today's question, "
                       "or type a full answer (40+ words). Tap 🎤 Today's Challenge to see the question.",
                       reply_markup=main_menu())


async def main():
    global BOT_USERNAME
    if os.getenv("SEED_DEMO", "1") == "1":
        db.seed_demo()
    bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    me = await bot.get_me()
    BOT_USERNAME = me.username
    await bot.set_my_commands([
        BotCommand(command="start", description="Start / main menu"),
        BotCommand(command="challenge", description="Today's speaking question"),
        BotCommand(command="guess", description="Guess the Band game"),
        BotCommand(command="leaderboard", description="School & city league"),
        BotCommand(command="me", description="My progress"),
        BotCommand(command="card", description="My Band Card"),
        BotCommand(command="invite", description="Invite friends"),
        BotCommand(command="help", description="How it works"),
    ])
    await bot.set_my_description(
        "BAND BATTLE: prototype built for the IDP IELTS Kazakhstan Case Challenge. Send a voice answer, get your estimated IELTS Speaking band "
        "and 3 personal fixes in 30 seconds. Battle for your school! #WhatsYourBand")
    await bot.set_my_short_description("What's your band, Kazakhstan? Free IELTS Speaking check in 30 sec.")
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    log.info("Starting @%s", BOT_USERNAME)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
