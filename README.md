# Discord RPC Tool

A lightweight desktop application paired with a browser userscript that dynamically updates your **Discord Rich Presence** based on what you are currently watching or listening to in your web browser.

---

## Features

* **Platform Support:** Works with popular streaming platforms:
  * **Global:** YouTube, Twitch, Rumble, Netflix
  * **Polish:** CDA.pl, OgladajAnime.pl, Shinden.pl
    
* **Flexible Privacy Controls:**
  * Toggle Rich Presence globally or per-site.
  * Enable **Incognito Mode** to hide specific details (such as titles, channel names, or timestamps) while still broadcasting general activity.
    
* **Customization:** Configurable Discord Application IDs, display names, and individual icon tooltips for supported sites.
* **Minimalist UI & Performance:**
  * Clean dark theme UI.
  * Minimizes to the Windows system tray.
  * Runs a lightweight local HTTP server (`127.0.0.1:7591`) for fast communication with the browser script.
    
* **Automatic Cover Art:** Automatically fetches high-resolution youtube thumbnail or anime cover art using the **AniList GraphQL API** (with Jikan fallback).
  
* **Anime Site Integration:** Dedicated support for Polish anime streaming platforms **OgladajAnime.pl** and **Shinden.pl**.

---

## Installation & Setup

### Using executable version, you can freely skip first step.

### 1. Install Dependencies
1. Install Python 3.10+
2. Open windows terminal and install dependencies using: `pip install pypresence, pystray, pillow, requests`

### 2. Desktop Application
1. Download or build the latest release of the **Discord RPC Tool**.
2. Run the `DiscordRPC.exe` or `presence_server.py`.
3. Make sure Discord is running on your desktop.

### 3. Browser Userscript
1. Install [Tampermonkey](https://www.tampermonkey.net/) in your browser.
2. Add the provided `discordrpc_script_latest.user.js` file to Tampermonkey and ensure it is enabled.
3. In webbrowser make sure is "allow user scripts" are enabled in the settings of the Tampermonkey.

### Browser tabs must be reloaded if they were opened before launching DiscordRPC. 

---

## How It Works

1. The **Tampermonkey userscript** detects active media playing on supported websites.
2. It sends real-time metadata (title, episode/track, duration, cover art requests) to the local backend server running on `127.0.0.1:7591`.
3. The **desktop app** receives the payload, processes metadata (fetching anime cover art via AniList if applicable), and updates your Discord status via the local Discord RPC socket.

---

## Supported Platforms

| Platform | Type | Language | Status |
| :--- | :--- | :--- | :--- |
| **YouTube** | Streaming | Global | Working |
| **Twitch** | Streaming | Global | Working |
| **Rumble** | Streaming | Global | Working |
| **Netflix** | Streaming | Global | Not Tested |
| **CDA.pl** | Streaming | Polish | Working |
| **Shinden.pl** | Anime | Polish | Working |
| **OgladajAnime.pl** | Anime | Polish | Working |

---

## Issues and Bugs

If you encounter any bugs or issues, please report them in the [GitHub Issues section](https://github.com/Arikizu/DiscordRPC/issues).  
Got ideas or want to help improve the project? Feel free to open an issue or submit a pull request. Your contributions and suggestions are always welcome!

## Support:

[![buycoffee.to](https://buycoffee.to/img/brand/bc-logo.svg)](https://buycoffee.to/arikizu)

## License

Distributed under the Creative Commons Attribution-NonCommercial 4.0 International License (CC BY-NC 4.0). See `LICENSE` for more information.
