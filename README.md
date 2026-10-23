# NightShift IT — private personal job dashboard

A lightweight job-search dashboard for remote after-hours IT work, with browser-local bookmarks and application tracking.

## Run it

Open `index.html` for the dashboard and manual tracking. For live daily results, publish the project with **GitHub Pages** (Settings → Pages → Deploy from a branch → main / root), then go to **Actions → Refresh job matches daily → Run workflow**. The scheduled workflow updates `jobs.json` every day around 13:17 UTC (GitHub scheduled jobs can be delayed). GitHub Pages serves the latest feed after the update. GitHub may disable scheduled workflows on inactive repositories.

The feed currently uses the publicly available Remotive and Arbeitnow endpoints. Their terms and availability may change. The fetcher intentionally shows *possible* after-hours IT matches rather than claiming every job is a confirmed overnight shift. Some results may point to aggregators, so always verify the employer and posting. It does not bypass paywalls, scrape LinkedIn/Indeed, or automatically apply.

**Privacy:** Saved jobs and statuses are stored in your current browser's localStorage, not synced across devices. Export CSV periodically to back up your tracker. GitHub Pages hosting makes the site URL public even though saved data stays in the browser. Do not put sensitive notes into the repository.

To use locally with the feed, serve the directory with `python -m http.server 8000` and visit `http://localhost:8000`. The feed only refreshes when the script runs or the GitHub workflow executes.
