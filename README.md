# Calories

A calorie and protein tracker for a small group of friends. One static page, no
build step, no framework, no email or password.

**Live:** https://cristianand24.github.io/calories/

- Works out what you burn (Mifflin–St Jeor × activity) and a daily target for
  losing fat, maintaining, or building muscle, at a steady or faster pace.
- Protein is set by body weight (1.8–2.0 g/kg); fat is 30% of calories and
  carbs fill the rest. Targets follow your latest weigh-in.
- Log food from 12,700 USDA foods, by barcode (Open Food Facts), from foods the
  group has added, as a quick number, from recipes you cook and portion, or
  from saved meals.
- Weight trend, calories per day, and vitamins and minerals with an honest note
  of how much of the day's food actually reports them.

## Add it to your iPhone

1. Open the link **in Safari**.
2. Tap Share, then **Add to Home Screen**.
3. Open it from the icon and enter the invite code you were given.

## Who can join

Joining needs an invite code, and the server stops taking people at 10 — both
in `cal_join` in `supabase-setup.sql`. The code is not in this repository.

There is no account. Joining mints a 160-bit key on the phone, and that key is
the account: it is shown under **Me → Data and sync**, can be pasted on a new
phone, and travels inside every backup file. Lose the key along with every
phone and every backup and the server copy cannot be recovered.

## Where the data lives

- **On the phone first.** Everything works offline and syncs when it can.
- **On the server**, per person: profile, goal, recipes, saved meals, and one
  row per day. Two phones that both edited offline merge record by record,
  newest edit winning, and a deletion stays deleted.
- **Foods are shared.** Anything someone scans or types in is searchable by
  the whole group, so each product only needs adding once. Only the person who
  added a food can change it. Diaries are private.
- **Backup file:** Me → Export backup. The only copy that survives the server
  and the free tier going away.

## Server

`supabase-setup.sql` is the whole database: five tables (all prefixed `cal_`)
and six functions. It shares the free Supabase project with Habits and touches
nothing outside `cal_*`. The optional AI features add one Edge Function; see
*AI logging* below.

1. Paste `supabase-setup.sql` into the project's SQL editor and run it.
2. Create the invite code there (not in this repo):
   ```sql
   insert into public.cal_invites (code, max_uses) values ('YOUR_CODE', 10);
   ```
3. `SB_URL` and `SB_KEY` near the sync section of `index.html` point at the
   project. The publishable key is public by design: every table has RLS on
   with no policies, so nothing is reachable over REST, and the functions only
   touch rows for the key they are given.

To see who has joined, open `cal_users` in the Supabase table editor. Deleting
a row there removes that person and everything they synced; give their place
back by lowering `uses` on their invite.

## AI logging

Optional. Without it the app says AI is off and everything else (search,
barcode scanning, quick add, recipes, sync) works exactly the same.

- **Describe** — say or type what you ate ("2 scrambled eggs, a slice of toast
  with butter and a flat white"); it comes back as separate foods with amounts,
  matched to the USDA foods or to your own foods, recipes and saved meals.
  Nothing is saved until you check it.
- **Describe a recipe or a meal** — dictate the ingredients and the recipe or
  saved-meal editor opens already filled in.
- **Read the label** — photograph a nutrition label in the new-food editor and
  the numbers are filled in for you to check.
- **Photo of a plate** — a rough estimate of what is on it, marked as one.

Dictation itself is the iPhone keyboard's microphone, so it is free and private
to the phone. What reaches the AI is the text or the photo, plus, so it can
match them, the names of your recipes, your saved meals and the group's foods
(up to 150 names). A description or a plate photo also sends your local day
and time and the meal you are adding to. A label photo goes on its own.
English, French and Romanian are all expected, mixed or not.

**How it works.** The app calls one Supabase Edge Function,
`supabase/functions/cal-ai/index.ts`, with the person's sync key. The function
checks the key, counts the request in `cal_ai_usage` (`cal_ai_begin` in
`supabase-setup.sql`), asks the AI for structured JSON, clamps every number to
a sane range and replies. The AI is **Google Gemini** (`gemini-3.8-flash`) when
a Gemini key is set, otherwise **Claude** (Haiku 5.5); both get the same
prompts and the same reply checks. The AI key lives only in Supabase's secrets,
never in this repository or the page. A whole request, database and AI
together, is cut off at 27 seconds, so a slow one ends on the server before the
app's own 36-second limit gives up on it.

**What Google may do with it.** On Gemini's free tier, Google may use what is
sent to improve its products, and people at Google may review it: the
description or the photo, the recipe, saved-meal and food names that go with
it, and the day, time and meal. While the server uses Gemini, the Describe and
Read the label screens show a short note saying so. If the group would rather
not, turn on billing for the Gemini project (paid Gemini, under **Cost**):
Google's pricing page says the paid tier is not used to improve its products.
Or switch to Claude (below), which is paid too.

**Limits.** The app's own: 60 requests per person per day and 600 for the
whole group (the constants in `cal_ai_begin`). Days are UTC. A request counts
once it reaches the AI, whether or not the answer is usable, and every reply
from then on, error or not, carries the new count (`used`, `limit`).

Gemini's free tier has limits of its own on top. They apply per Google Cloud
project, so everyone in the group shares one allowance through the one key;
the daily ones reset at midnight Pacific time; and the current numbers are
shown only in Google AI Studio, for your project. When `gemini-3.8-flash` says
its allowance is used up, the function asks `gemini-3.5-flash-lite` once
instead, which has a free allowance of its own. When both have used up their
allowance for the day, the app says "The free AI allowance is used up" and
when it comes back, in the phone's own time (3:00 a.m. in Toronto, 1:00 a.m.
in Calgary). A per-minute limit reads as "The AI is busy. Try again in a
moment." Every attempt still counts towards the person's 60 a day.

**Cost.**
- **Gemini, free tier: $0.** With no billing on the Google project nothing can
  be charged; when the allowance runs out, requests are refused until it
  resets.
- **Paid Gemini: about $2–4 a month for the group** on 3.8 Flash at one or
  two requests per person a day for ten people, about $1–2 on 3.5 Flash-Lite.
  **Claude: under $1.** These rest on an estimate, not a measurement: a
  request taken as about 3,000 tokens in and 1,000 out (thinking included), a
  little more for a photo. That is about 0.6¢ on Gemini 3.8 Flash ($0.75 /
  $3.75 per million tokens in / out, the price through 2026-12-31), about a
  third of a cent on 3.5 Flash-Lite ($0.30 / $2.50), and under a tenth of a
  cent on Claude Haiku 5.5 ($0.10 / $0.50). Confirm them from the `usage` in
  the function log's line for each request after the first real ones.
- **The ceiling.** The group cap of 600 requests a day bounds the bill: about
  $3.60 a day on 3.8 Flash at the estimate above. Paid Gemini means turning on
  billing for the key's project in AI Studio ("Upgrade to Paid"), and it has
  no prepaid hard cap: a Google Cloud budget only sends alerts. With Claude,
  the prepaid credit below is a hard cap as well.

### One-time setup (owner)

1. Run the latest `supabase-setup.sql` in the SQL editor. It is safe to re-run
   and adds `cal_ai_usage`, `cal_ai_status` and `cal_ai_begin`.
2. Supabase → **Edge Functions** → Deploy a new function → Via editor. Name it
   `cal-ai`, paste the whole of `supabase/functions/cal-ai/index.ts`, and turn
   **Enforce JWT verification off** (the app sends no JWT; the function checks
   the person's key itself). Deploy.
3. Get a free Gemini key: [Google AI Studio](https://aistudio.google.com) →
   **Get API key** → create a key. You need to be 18 or over and in a region
   AI Studio serves; Canada is one. No billing is needed for the free tier.
4. Supabase → **Edge Functions → Secrets**: add `GEMINI_API_KEY` with that
   key. No redeploy is needed.
5. Check it, with your own sync key (Me → Data and sync):
   ```bash
   curl -s -X POST https://akiqlzvsaefyxlzsxrjw.supabase.co/functions/v1/cal-ai \
     -d '{"key":"YOUR_SYNC_KEY","task":"status"}'
   ```
   `{"configured":true,"provider":"gemini",…}` means AI is on; `false` means
   step 4 is missing. `not_configured` means step 1 is missing or the database
   refused the function's keys (the function's log names each refused key). A
   `NOT_FOUND` reply means step 2 is missing. A status check never counts.
   In the app, Me → Data and sync shows **AI logging: On (Gemini) · 12 of 60
   today**.

The steps can happen in any order. Until steps 1, 2 and 4 are done, the app
says "AI isn't switched on yet" and everything else works as normal. If the
key is ever revoked or rejected (or, with Claude, the credit runs out), it goes
back to off by itself.

### Using Claude instead

1. At [console.anthropic.com](https://console.anthropic.com), create an API
   key.
2. Supabase → **Edge Functions → Secrets**: add `ANTHROPIC_API_KEY` with that
   key.
3. Anthropic console → **Billing**: buy a small amount of prepaid credit (say
   $5) and leave **auto-reload off**. That is the hard spending cap: when the
   credit runs out, AI stops and the app says so, and nothing else is charged.
4. If `GEMINI_API_KEY` is set too, add the secret `AI_PROVIDER` = `claude`
   (or delete the Gemini key). With both keys set and no `AI_PROVIDER`, Gemini
   is used. `AI_PROVIDER` (`gemini` or `claude`) is ignored when that
   provider's key is missing, so AI never goes off because of it.

The status check then says `"provider":"claude"`, and the app shows
**On (Claude)**. Switching back is the same in reverse; no redeploy either way.

**Optional secrets.** `GEMINI_MODEL` (default `gemini-3.8-flash`) and
`GEMINI_FALLBACK_MODEL` (default `gemini-3.5-flash-lite`) change the Gemini
models without editing the function.

**Database keys.** The function finds its own key to the database; there is
nothing to set. It tries the new secret keys (`SUPABASE_SECRET_KEYS`) first,
then the legacy service-role key, then the publishable ones, and remembers a
key that was refused. Legacy keys stop working at the end of 2026: before
turning them off, make sure the project has new API keys (Settings → API Keys
→ Publishable and secret API keys), which Edge Functions receive
automatically. If every key is refused, the app shows AI as off rather than
busy, and the function log says which keys were refused.

To see usage, open `cal_ai_usage` in the table editor: one row per person per
day. The function logs one line per request (task, status, time, provider,
model, tokens), never the key or what was said.

## Food data

- `foods.json` — USDA FoodData Central, SR Legacy (2018-04) and FNDDS
  (2021–2023), public domain. 12,728 foods, 20 nutrients per 100 g, household
  portions. Rebuild with `tools/build_foods.py` (instructions inside). After
  changing it, bump `CACHE` in `sw.js`.
- Barcodes — [Open Food Facts](https://world.openfoodfacts.org), ODbL, looked
  up live and saved to the group's foods.
- `vendor/zxing-0.21.3.min.js` — the ZXing barcode decoder (Apache 2.0),
  vendored so scanning works offline. Phones with a built-in barcode detector
  use that instead.

## Updating it

Edit and push. The page is network-first, so the installed app picks up the
new version the next time it opens online. If you change `sw.js`, `foods.json`
or anything in `vendor/`, bump `CACHE` in `sw.js`.

## Files

| File | Purpose |
| --- | --- |
| `index.html` | The whole app |
| `foods.json` | Bundled USDA foods |
| `sw.js` | Offline shell and update strategy |
| `supabase-setup.sql` | The server: tables, invite cap, sync functions, AI usage caps |
| `supabase/functions/cal-ai/index.ts` | The AI Edge Function (pasted into Supabase) |
| `manifest.webmanifest`, `*.png` | Home-screen install and icons |
| `vendor/` | ZXing barcode decoder and its licence |
| `tools/build_foods.py` | Rebuilds `foods.json` from USDA downloads |
| `tools/make_icons.py` | Draws the icons |

## Local preview

```bash
python -m http.server 8732
```

Then open http://localhost:8732/. A service worker needs `http://`, not
`file://`.
