# Paisa Decode — automated Instagram Reels

Three Hindi reels a day, made from the @PaisaDecodeHQ YouTube channel and posted to Instagram with no one touching anything.

```
calendar slot ─▶ YouTube transcript ─▶ Claude writes script + scene plan ─▶ fact-check every number
   (Apify)                               (prompts/script_writer.md)          (stops if anything is invented)
        ─▶ ElevenLabs "Rohan" voice + word timings ─▶ render Rohan mascot reel ─▶ sound design + mix ─▶ post to Instagram
                                                     (pipeline/render)                                (Graph API)
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

All keys go into **GitHub → this repo → Settings → Secrets and variables → Actions → New repository secret**.
Never paste them into chat or commit them.

### 1. Claude API — writes the scripts
console.anthropic.com → API keys → create key → secret **`ANTHROPIC_API_KEY`**.

### 2. ElevenLabs — Rohan's voice
elevenlabs.io → profile → API keys → create key (same workspace as the "Rohan" voice) → secret **`ELEVENLABS_API_KEY`**.
Each reel uses ~1,100 credits → ~100,000 credits/month at 3 reels a day. The **Pro** plan (500k) gives comfortable headroom;
Creator (100k) is just enough.

### 3. Apify — YouTube transcripts and new-upload detection
console.apify.com → Settings → API & Integrations → copy the personal token → secret **`APIFY_TOKEN`**. (Costs cents per month.)

### 4. Instagram — posting
Uses the official Instagram API with Facebook Login, with a System User token that **never expires**.

1. In the Instagram app: Settings → Account type → switch to **Professional (Creator or Business)**, and link it to a **Facebook Page**.
2. Go to **business.facebook.com** → create a Business portfolio (if you don't have one) → *Accounts* → add your Facebook Page and your Instagram account.
3. Go to **developers.facebook.com** → *Create app* → type **Business** → connect it to that Business portfolio →
   add the product **Instagram** → choose *API setup with Facebook login*.
4. Back in **business.facebook.com → Settings → Users → System users** → *Add* (role: Admin).
   - *Assign assets*: your Page (full control) and your Instagram account (full control). *Add assets* → *Apps* → your new app.
   - *Generate token* → pick your app → expiry **Never** → tick `instagram_basic`, `instagram_content_publish`,
     `pages_read_engagement`, `pages_show_list` → copy it → secret **`IG_ACCESS_TOKEN`**.
5. Find your Instagram account ID: open **developers.facebook.com/tools/explorer**, paste the token, and run
   `me/accounts?fields=name,instagram_business_account` → copy `instagram_business_account.id` → secret **`IG_USER_ID`**.

### 5. Test, then go live
- **Actions → Make & post reel → Run workflow** with *dry_run* ticked. When it finishes, download the reel from the run's *Artifacts*.
- Happy with it? Run once more with *dry_run* unticked to post for real. From then on the schedule runs by itself.
- Optional repo **variables** (Settings → Secrets and variables → Variables): `CLAUDE_MODEL` (default `claude-sonnet-5-5`),
  `ELEVENLABS_VOICE_ID` (default: Rohan), `DRY_RUN=true` to pause posting without turning anything off.

---

## Everyday controls
- **Pause everything:** Actions → *Make & post reel* → ⋯ → *Disable workflow*.
- **Change what posts next:** edit `calendar/calendar.csv` on GitHub — put `1` in the `priority` column of a row, or change `status` to `skip`.
- **Post a specific video soon:** add it to `calendar/videos.json`, then run *Add new YouTube uploads to the calendar*.
- **Change tone or structure of scripts:** edit `prompts/script_writer.md` (plain English).
- **Something failed:** the run shows red in Actions; the calendar row gets a note. A reel that fails twice is marked `failed` and the queue moves on.
  If the fact-check rejects a script (a number not found in the video), the row becomes `skipped_factcheck` and nothing is posted.

## Costs (approx., per month at 90 reels)
GitHub Actions: free for this usage (~12–15 min per run) · Claude API: a few dollars · ElevenLabs: Creator/Pro plan · Apify: < $1.
Instagram allows up to 100 API posts per 24 hours, so 3 a day is far inside the limit.

## Layout
```
calendar/      videos.json (channel videos), calendar.csv (the schedule + status)
prompts/       script_writer.md (house style + rules), example_plan_water_jar.json (reference reel)
pipeline/      run.py (one reel per run), transcript.py, script_writer.py, voice.py, publish.py,
               build_calendar.py, new_videos.py, render/ (Rohan mascot, engine, sound design, fonts)
media/         pre-rendered reels (reel #1, approved)
logs/          runs.csv, plans/ (every script that was posted)
```
