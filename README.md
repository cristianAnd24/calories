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

`supabase-setup.sql` is the whole backend: four tables (all prefixed `cal_`)
and four functions. It shares the free Supabase project with Habits and touches
nothing outside `cal_*`.

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
| `supabase-setup.sql` | The server: tables, invite cap, sync functions |
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
