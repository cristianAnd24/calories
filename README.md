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
to the phone. Only the text, or the photo, is sent.

**How it works.** The app calls one Supabase Edge Function,
`supabase/functions/cal-ai/index.ts`, with the person's sync key. The function
checks the key, counts the request in `cal_ai_usage` (`cal_ai_begin` in
`supabase-setup.sql`), asks Claude Haiku 5.5 for structured JSON, clamps every
number to a sane range and replies. The Anthropic key lives only in Supabase's
secrets, never in this repository or the page. A whole request, database and
Claude together, is cut off at 27 seconds, so a slow one ends on the server
before the app's own 30-second limit gives up on it.

**Limits.** 60 requests per person per day and 600 for the whole group (the
constants in `cal_ai_begin`). Days are UTC. A request counts once it reaches
Claude, whether or not the answer is usable, and every reply from then on,
error or not, carries the new count (`used`, `limit`).

**Cost.** A request is under a tenth of a cent at Haiku 5.5 prices ($0.10 per
million input tokens, $0.50 per million output): roughly 3,000 tokens in and
under 1,000 out, a little more for a photo. Ten people logging a few times a
day comes to about **$1 a month**. If everyone hit the cap every day, the group
limit holds it to typically under 60 cents a day, and at most about $2.80 a
day if all 600 requests were the largest possible (150 own foods, a photo, and
a full 8,192-token answer). The prepaid credit below is the hard cap.

### One-time setup (owner)

1. Run the latest `supabase-setup.sql` in the SQL editor. It is safe to re-run
   and adds `cal_ai_usage`, `cal_ai_status` and `cal_ai_begin`.
2. Supabase → **Edge Functions** → Deploy a new function → Via editor. Name it
   `cal-ai`, paste the whole of `supabase/functions/cal-ai/index.ts`, and turn
   **Enforce JWT verification off** (the app sends no JWT; the function checks
   the person's key itself). Deploy.
3. At [console.anthropic.com](https://console.anthropic.com), create an API
   key.
4. Supabase → **Edge Functions → Secrets**: add `ANTHROPIC_API_KEY` with that
   key. No redeploy is needed.
5. Anthropic console → **Billing**: buy a small amount of prepaid credit (say
   $5) and leave **auto-reload off**. That is the hard spending cap: when the
   credit runs out, AI stops and the app says so, and nothing else is charged.
6. Check it, with your own sync key (Me → Data and sync):
   ```bash
   curl -s -X POST https://akiqlzvsaefyxlzsxrjw.supabase.co/functions/v1/cal-ai \
     -d '{"key":"YOUR_SYNC_KEY","task":"status"}'
   ```
   `{"configured":true,…}` means AI is on; `false` means step 4 is missing.
   `not_configured` means step 1 is missing or the database refused the
   function's keys (the function's log names each refused key). A
   `NOT_FOUND` reply means step 2 is missing. A status check never counts.

The steps can happen in any order. Until steps 1, 2 and 4 are done, the app
says "AI isn't switched on yet" and everything else works as normal. If the key is ever
revoked or the credit runs out, it goes back to off by itself.

**Database keys.** The function finds its own key to the database; there is
nothing to set. It tries the new secret keys (`SUPABASE_SECRET_KEYS`) first,
then the legacy service-role key, then the publishable ones, and remembers a
key that was refused. Legacy keys stop working at the end of 2026: before
turning them off, make sure the project has new API keys (Settings → API Keys
→ Publishable and secret API keys), which Edge Functions receive
automatically. If every key is refused, the app shows AI as off rather than
busy, and the function log says which keys were refused.

To see usage, open `cal_ai_usage` in the table editor: one row per person per
day. The function logs one line per request (task, status, time, tokens),
never the key or what was said.

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
