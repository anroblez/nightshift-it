# 🌙 The Night Desk

**Your after-hours tech job radar.**

The Night Desk is a job discovery and tracking website designed to help
people find remote technology opportunities, including potential evening,
overnight, weekend, and flexible roles.

## ✨ Features

- **Daily job feed:** Collects potential matches from job feeds and selected
  employer career boards.
- **Search and filters:** Search by job title, company, or keyword and filter
  by shift type.
- **Saved jobs:** Bookmark listings you want to revisit.
- **Application tracker:** Track jobs as saved, applied, interview, offer,
  or rejected.
- **CSV export:** Download your saved jobs and application statuses.
- **Manual entry:** Add a job you found somewhere else.
- **Quick searches:** Explore additional opportunities through career searches.

## 🌐 Visit the Website

[Open The Night Desk](https://anroblez.github.io/nightshift-it/)

## 🛠️ Built With

- HTML, CSS, and JavaScript
- Python
- GitHub Actions
- GitHub Pages

## 🔄 How the Job Feed Works

A GitHub Actions workflow runs the Python script in `scripts/fetch_jobs.py`
to collect potential matches. The script searches selected sources and
employer boards listed in `scripts/approved_employers.json`, then writes
the results to `jobs.json`.

The website reads `jobs.json` and displays the results in the discovery feed.
The workflow is scheduled to run daily and can also be started manually.

## 💾 Saving Jobs

Saved jobs are stored in your browser on your device. They aren't shared with
other visitors, and they don't automatically transfer to another browser or
device. Use **Export saved CSV** to back them up.

## 🔎 Before You Apply

Listings are **potential matches**, not guaranteed overnight positions.
Before applying, check:

- The actual work schedule and time zone.
- Whether the position is remote in your state.
- The employer and application link.
- Any experience, certification, or clearance requirements.
- Whether the position is still open.

## 🌙 About the Project

I created The Night Desk to practice building a website, using GitHub Actions,
and working with Python and data feeds while exploring opportunities in tech.

Inspired by cozy late nights, starry skies, and a little bit of magic. ✨
