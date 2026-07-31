# 🎮 Discord RPC Tool

A lightweight desktop application paired with a browser userscript that dynamically updates your **Discord Rich Presence** based on what you are currently watching or listening to in your web browser.

---

## 🌟 Features

* **Multi-Platform Support:** Works seamlessly with popular video and audio platforms:
  * **Video:** YouTube, CDA.pl, Rumble, Netflix, Twitch
  * **Music:** YouTube Music, Spotify
* **Privacy & Incognito Controls:**
  * Toggle Rich Presence globally or per-site.
  * Enable **Incognito Mode** to hide specific details (such as titles, channel names, or timestamps) while still broadcasting general activity.
* **Customization:** Configurable Discord Application IDs, display names, and individual icon tooltips for supported sites.
* **Minimalist UI & Performance:**
  * Clean dark theme UI.
  * Minimizes to the Windows system tray.
  * Runs a lightweight local HTTP server (`127.0.0.1:7591`) for fast communication with the browser script.
* **Anime Site Integration:** Dedicated support for Polish anime streaming platforms **Shinden.pl** and **OgladajAnime.pl**.
* **Automatic Cover Art:** Automatically fetches high-resolution anime cover art using the **AniList GraphQL API** (with Jikan fallback).

---

## 🚀 Installation & Setup

### 1. Browser Userscript
1. Install a userscript manager in your browser (e.g., [Tampermonkey](https://www.tampermonkey.net/)).
2. Add the provided `discord-rpc_script_0.4.6.user.js` file to Tampermonkey and ensure it is enabled.

### 2. Desktop Application
1. Download or build the latest release of the **Discord RPC Tool**.
2. Run the application before or while browsing your preferred media sites.
3. Make sure Discord is running on your desktop.

---

## ⚙️ How It Works

1. The **Tampermonkey userscript** detects active media playing on supported websites.
2. It sends real-time metadata (title, episode/track, duration, cover art requests) to the local backend server running on `127.0.0.1:7591`.
3. The **desktop app** receives the payload, processes metadata (fetching anime cover art via AniList if applicable), and updates your Discord status via the local Discord RPC socket.

---

## 🛠️ Supported Platforms

| Platform | Type | Status | Language |
| :--- | :--- | :--- | :--- |
| **YouTube** | Video-Streaming | Working | Global |
| **Twitch** | Live-Streaming | Working | Global |
| **Netflix** | Video-Streaming | Not Tested | Global |
| **Rumble** | Video-Streaming | Broken | Global |
| **CDA.pl** | Video-Streaming | Working | Polish |
| **Shinden.pl** | Anime | Working | Polish |
| **OgladajAnime.pl** | Anime | Working | Polish |

---

## 📝 License

Distributed under the MIT License. See `LICENSE` for more information.
