# 🎧 rekord2plex

**Sync your curated Rekordbox library metadata into Plex — automatically.**  
Make your DJ collection streamable, searchable, and familiar — everywhere.

---

## 🚨 The Problem

Rekordbox is the gold standard for managing DJ libraries — but its curated metadata (title, artist, album, playlists) **doesn’t carry over cleanly into Plex**. Especially with:

- **WAV files** (no embedded ID3 tags)
- **Misparsed metadata** (Plex guessing wrong artist/title)
- **Large libraries** (hard to casually explore your own collection)

Plex is great for streaming via Plexamp, but unreliable as a **mirror of your DJ library**.

---

## ✅ The Solution

`rekord2plex` reads your **Rekordbox metadata** and uses the **Plex API** to overwrite incorrect or missing track metadata. This means:

- Your Plex library shows the *actual titles, artists, and albums* from Rekordbox.
- You can stream your DJ collection on-the-go with Plexamp and *actually find what you're looking for*.
- WAV files and other non-tagged formats are fully supported.

Rekordbox stays your **source of truth**. Plex becomes your **streamable mirror**.

---

## ✨ Features

- 🔁 Sync Rekordbox track metadata into Plex via HTTP API
- 🎵 Correct titles, artists, albums even for WAVs
- 🔎 Match tracks using full file paths (no guesswork)
- ⚙️ Designed for automation (Deno/TS CLI-friendly)
- 📦 Optional playlist sync (planned)
- 🧠 One-way sync: Rekordbox → Plex (never the other way around)

---

## 📂 Data Flow

Rekordbox (XML or DB)
↓
rekord2plex (script)
↓
Plex API
↓
Plex Library (fixed!)

yaml
Copy
Edit

---

## 🚀 Coming Soon

- 📝 Playlist mirroring
- 🗂 Smart section overrides (genres, crates)
- 🌐 Cross-platform CLI with config support
- 🔐 Rekordbox `master.db` support (with optional key)

---

## 💻 Requirements

- Deno runtime (https://deno.land)
- Rekordbox XML export *(or decryption key for DB access)*
- Plex server with local library access and valid token

---

## 🧪 Project Status

This project is **actively in development** and will be open-sourced on GitHub.  
Follow along or contribute once it’s live!

---

## 🤘 Built for DJs

Whether you're prepping a set, digging into your 3000-track archive, or just vibing on the go —  
**rekord2plex helps you stay connected to your music.**

---
