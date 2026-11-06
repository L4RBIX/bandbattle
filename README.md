# BAND BATTLE: What's your band, Kazakhstan?

Telegram bot prototype for the IDP IELTS Kazakhstan Case Challenge (Digital Community track).

**User flow:** YouTube Shorts (deep link) → bot → 3-tap onboarding (city, school, target) → voice answer to the daily IELTS Speaking Part 2 question → estimated band (Fluency / Vocabulary / Grammar) + 3 personal fixes in ~30 s → XP, streak, school & city leaderboard → Band Card for Instagram/TikTok stories → referral (3 friends = Mock Test) → "Ready for the real IELTS?" booking link with UTM.

Scores are an **AI practice estimate**, not an official IELTS score. Pronunciation is not assessed in v1.

## Deploy on Railway (about 10 minutes)
1. Telegram → @BotFather → `/newbot` → copy the token.
2. console.groq.com → API Keys → create a key.
3. GitHub → New repository → "uploading an existing file" → drag ALL files from this folder (including the `fonts` folder) → Commit.
4. railway.com → sign in with GitHub → New Project → Deploy from GitHub repo → choose the repo.
5. Service → **Variables** → add:
   - `BOT_TOKEN` = token from step 1
   - `GROQ_API_KEY` = key from step 2
   - `SEED_DEMO` = `1` (demo players on the leaderboard, marked "(demo)")
   - optional `ADMIN_IDS` = your Telegram numeric id (then only you can see /stats)
6. Optional but recommended: Service → **Volumes** → add volume mounted at `/data`, and set `DB_PATH=/data/bandbattle.db` so data survives redeploys.
7. Deploy. Logs should show `Starting @YourBot`. Open the bot, tap Start.

Local run: `pip install -r requirements.txt`, set the env vars, `python bot.py`.

## Deep links (attribution per video)
- `https://t.me/<bot>?start=yt_bandcheck_ep1` : source tracking per Short
- `https://t.me/<bot>?start=guess1` : opens Guess the Band (YouTube cliffhanger reveal)
- `https://t.me/<bot>?start=ref_<user_id>` : referral (generated automatically)

`/stats` shows users by source, answers, average band, Band Cards, Guess plays and "Book IELTS" clicks.

## Stack
Python, aiogram 3, Groq API (whisper-large-v3-turbo for speech-to-text; llama-3.3-70b-versatile with automatic fallback models for scoring), SQLite, Pillow.
