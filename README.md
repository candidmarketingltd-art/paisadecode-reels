# Paisa Decode — automated Instagram Reels

Three Hindi reels a day, made from the @PaisaDecodeHQ YouTube channel and posted to Instagram with no one touching anything.

```
calendar slot ─▶ YouTube transcript ─▶ Claude Sonnet writes script ─▶ Claude Opus edits (scene plan) ─▶ fact-check every number
   (Apify)                               (prompts/script_writer.md)          (stops if anything is invented)
        ─▶ ElevenLabs "Rohan" voice + word timings ─▶ render Rohan mascot reel ─▶ theme music + mix ─▶ Buffer queue ─▶ Instagram
           (free Microsoft voice when credits run out)  (pipeline/render)
```

| When (IST) | Slot | What gets posted |
|---|---|---|
| 08:30 | 1 · economics | "How much does the owner really make" stories |
| 13:30 | 2 · money | Personal-finance math and comparisons |
| 19:30 | 3 · ideas | One business from a "5 boring businesses" list |

The plan lives in [`calendar/calendar.csv`](calendar/calendar.csv): 170 reels from the channel's 59 videos (30 Oct – 25 Dec 2026).
New uploads are detected every morning and jump to the front of the queue. After each post the row is marked `posted`
with the Instagram link, and every run is logged in `logs/runs.csv`. Scripts are saved in `logs/plans/`.

---

## One-time setup (~20 minutes)

Secrets go in **GitHub → this repo → Settings → Secrets and variables → Actions → Secrets**.
Plain settings go in the **Variables** tab of the same page. Never paste keys into chat or commit them.

### 0. Make this repo public
Settings → General → Danger zone → *Change visibility* → Public.
Buffer downloads each video from a public link, and public repos get **unlimited free GitHub Actions minutes**.
Your keys stay private (secrets are never shown, even in public repos).

### 1. Claude API — script (Sonnet) + video editing (Opus 5.5)
console.anthropic.com → API keys → create key → secret **`ANTHROPIC_API_KEY`**.
- **Claude Sonnet** (`claude-sonnet-5-5`) writes each Hindi script in your channel's tone.
- **Claude Opus 5.5** (`claude-opus-5-5`) edits the video: picks every card, when it appears, Rohan's reactions, cuts and the cold open.
- Billed per use from API credits you top up (no monthly plan). To change models later, set variables `SCRIPT_MODEL` / `EDIT_MODEL`.

### 2. Voice — ElevenLabs "Rohan" while credits last, then a free Microsoft voice
elevenlabs.io → API keys → create key (same workspace as the "Rohan" voice) → secret **`ELEVENLABS_API_KEY`**.
When your monthly ElevenLabs credits run out, reels automatically switch to Microsoft's free Hindi voice
(`hi-IN-MadhurNeural`) until credits refill, so posting never stops.
Want the free voice always (consistent sound, ₹0)? Add variable **`VOICE_PROVIDER`** = `edge`.

### 3. Transcripts — Apify (free plan)
console.apify.com → Settings → API & Integrations → personal token → secret **`APIFY_TOKEN`**.

### 4. Posting — Buffer (free plan)
1. Instagram app → switch to a **Professional (Creator or Business)** account.
2. buffer.com → sign up free → *Connect channel* → Instagram.
3. Buffer → *Settings → Posting schedule* for the Instagram channel → set times **08:30, 13:30, 19:30** (timezone Asia/Kolkata), every day.
4. publish.buffer.com/settings/api → create an API key → secret **`BUFFER_API_KEY`**.
5. Open the Instagram channel in Buffer — the address bar shows `.../channels/<ID>/...` → variable **`BUFFER_CHANNEL_ID`** = that ID.
6. Variable **`POSTING_MODE`** = `buffer`.

Twice a day the bot checks Buffer's queue and adds reels until **6** are waiting — always under the free plan's limit.
Buffer publishes them at your three daily times.

### 5. Test, then go live
- **Actions → Top up Buffer queue → Run workflow** with *target* = `1` and *dry_run* ticked → download the reel from *Artifacts*.
- Happy? Run it again with *dry_run* unticked and target `6`. From then on it runs by itself.

<details><summary>Other posting options (optional)</summary>

- **Meta's own API (free, no queue limit, more setup):** follow Meta's System User token steps, add secrets `IG_USER_ID` + `IG_ACCESS_TOKEN`,
  and leave `POSTING_MODE` empty — the *Make & post reel* workflow then posts directly at 08:30 / 13:30 / 19:30.
- **Upload-Post (paid for 3/day):** secret `UPLOAD_POST_API_KEY`, variable `UPLOAD_POST_USER`.
</details>

## Everyday controls
- **Pause everything:** Actions → *Make & post reel* → ⋯ → *Disable workflow*.
- **Change what posts next:** edit `calendar/calendar.csv` on GitHub — put `1` in the `priority` column of a row, or change `status` to `skip`.
- **Post a specific video soon:** add it to `calendar/videos.json`, then run *Add new YouTube uploads to the calendar*.
- **Change tone or structure of scripts:** edit `prompts/script_writer.md`; **change the editing style:** edit `prompts/video_editor.md` (both plain English).
- **Something failed:** the run shows red in Actions; the calendar row gets a note. A reel that fails twice is marked `failed` and the queue moves on.
  If the fact-check rejects a script (a number not found in the video), the row becomes `skipped_factcheck` and nothing is posted.

## Costs
No subscriptions: GitHub (public repo), Apify free credit, Buffer free plan, Microsoft voice fallback are all free.
Paid per use: the Claude API (two calls per reel: Sonnet + Opus). ElevenLabs never goes past the credits your current plan includes.

## Layout
```
calendar/      videos.json (channel videos), calendar.csv (the schedule + status)
prompts/       script_writer.md (house style + rules), example_plan_water_jar.json (reference reel)
pipeline/      run.py (one reel per run), transcript.py, script_writer.py, voice.py, publish.py,
               build_calendar.py, new_videos.py, render/ (Rohan mascot, engine, sound design, fonts)
media/         pre-rendered reels (reel #1, approved)
logs/          runs.csv, plans/ (every script that was posted)
```
