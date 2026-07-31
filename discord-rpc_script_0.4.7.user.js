// ==UserScript==
// @name         DiscordRPC Tool Connection Script
// @namespace    https://github.com/discord-rich-presence
// @version      0.4.7
// @description  Sends currently-watched content data to the local Discord Rich Presence server
// @author       Discord RP Manager
// @match        https://www.youtube.com/*
// @match        https://youtube.com/*
// @match        https://www.cda.pl/*
// @match        https://cda.pl/*
// @match        https://rumble.com/*
// @match        https://www.rumble.com/*
// @match        https://www.twitch.tv/*
// @match        https://twitch.tv/*
// @match        https://www.netflix.com/*
// @match        https://netflix.com/*
// @match        https://shinden.pl/*
// @match        https://www.shinden.pl/*
// @match        https://ogladajanime.pl/*
// @match        https://www.ogladajanime.pl/*
// @grant        GM_xmlhttpRequest
// @grant        GM_registerMenuCommand
// @connect      127.0.0.1
// @run-at       document-idle
// ==/UserScript==

(function () {
    'use strict';

    // ── Config ──────────────────────────────────────────────────────────────
    const SERVER   = 'http://127.0.0.1:7591/presence';
    const STATUS   = 'http://127.0.0.1:7591/status';
    const INTERVAL = 1000;  // ms

    // ── Tampermonkey menu ────────────────────────────────────────────────────
    GM_registerMenuCommand('Check server connection', () => {
        GM_xmlhttpRequest({
            method: 'GET', url: STATUS, timeout: 2000,
            onload(r) {
                try {
                    const d = JSON.parse(r.responseText);
                    const site = Object.entries(d.sites || {})
                        .map(([k, v]) => `${k}: enabled=${v.enabled} active=${v.active}`)
                        .join('\n');
                    alert(`Server: OK\nRPC Discord: ${d.rpc_connected ? 'connected' : 'disconnected'}\n\n${site}`);
                } catch {
                    alert('Server responded but returned unexpected data.');
                }
            },
            onerror:   () => alert('Server not responding. Run presence_server.py'),
            ontimeout: () => alert('Timeout – server not responding.'),
        });
    });

    // ── Helpers ──────────────────────────────────────────────────────────────
    function send(data) {
        GM_xmlhttpRequest({
            method: 'POST', url: SERVER,
            headers: { 'Content-Type': 'application/json' },
            data: JSON.stringify(data),
            timeout: 3000,
            onerror:   () => {},
            ontimeout: () => {},
        });
    }

    function parseTimeStr(txt) {
        if (!txt) return null;
        const parts = txt.trim().split(':').map(Number);
        if (parts.some(isNaN)) return null;
        if (parts.length === 2) return parts[0] * 60 + parts[1];
        if (parts.length === 3) return parts[0] * 3600 + parts[1] * 60 + parts[2];
        return null;
    }

    function videoTimes(sel = 'video') {
        const v = document.querySelector(sel);
        if (!v || isNaN(v.duration)) return { current: null, total: null, paused: true };
        return {
            current: Math.floor(v.currentTime),
            total:   Math.floor(v.duration),
            paused:  v.paused,
        };
    }

    // ╔══════════════════════════════════════════════════════════╗
    // ║                     SCRAPERS                            ║
    // ╚══════════════════════════════════════════════════════════╝

    // ── YouTube ──────────────────────────────────────────────────────────────
    function scrapeYouTube() {
        if (!location.pathname.startsWith('/watch')) return null;

        const params   = new URLSearchParams(location.search);
        const video_id = params.get('v') || '';

        const titleEl =
            document.querySelector('h1.ytd-watch-metadata yt-formatted-string') ||
            document.querySelector('#title h1') ||
            document.querySelector('h1.title');
        const title = titleEl
            ? titleEl.textContent.trim()
            : document.title.replace(' - YouTube', '').trim();

        const { current, total, paused } = videoTimes();

        const channelEl = document.querySelector(
            '#channel-name a, #owner-name a, ytd-channel-name a');
        const channel = channelEl ? channelEl.textContent.trim() : '';

        return { site: 'youtube', title, channel, video_id,
                 current_time: current, total_time: total, paused };
    }

    // ── CDA.pl ────────────────────────────────────────────────────────────────
    function scrapeCDA() {
        const titleEl =
            document.querySelector('h1') ||
            document.querySelector('[class*="title"]');
        const title = titleEl
            ? titleEl.textContent.trim()
            : document.title.replace(/\s*[-–|]\s*cda\.?pl?\s*/i, '').trim();

        let { current, total, paused } = videoTimes();

        if (current === null && typeof window.CDPlayer !== 'undefined') {
            try {
                const pl = window.CDPlayer;
                current = Math.floor(pl.getCurrentTime?.() ?? 0);
                total   = Math.floor(pl.getDuration?.()    ?? 0);
                paused  = !(pl.isPlaying?.());
            } catch (_) {}
        }

        return { site: 'cda', title, current_time: current, total_time: total, paused };
    }

    // ── Rumble ────────────────────────────────────────────────────────────────
    function scrapeRumble() {
        const titleEl =
            document.querySelector('h1.title, .video-title, h1') ||
            document.querySelector('[class*="Title"]');
        const title = titleEl
            ? titleEl.textContent.trim()
            : document.title.replace(' - Rumble', '').trim();

        const { current, total, paused } = videoTimes();
        const channelEl = document.querySelector('.channel-name a');
        const channel   = channelEl ? channelEl.textContent.trim() : '';

        return { site: 'rumble', title, channel, current_time: current, total_time: total, paused };
    }

    // ── Twitch ────────────────────────────────────────────────────────────────
    function scrapeTwitch() {
        const pathParts = location.pathname.split('/').filter(Boolean);
        const streamer  = pathParts[0] || '';
        const isVOD     = location.pathname.startsWith('/videos/');

        const titleEl =
            document.querySelector('[data-a-target="stream-title"]') ||
            document.querySelector('.channel-info-content h2') ||
            document.querySelector('h1');
        const title = titleEl ? titleEl.textContent.trim() : '';

        const gameEl = document.querySelector(
            '[data-a-target="stream-game-link"] a, a[href^="/directory/game/"]');
        const game = gameEl ? gameEl.textContent.trim() : '';

        const { current, total, paused } = isVOD ? videoTimes() : { current: null, total: null, paused: false };

        return { site: 'twitch', streamer, title, game, is_vod: isVOD,
                 current_time: current, total_time: total, paused };
    }

    // ── Netflix ───────────────────────────────────────────────────────────────
    function scrapeNetflix() {
        if (!location.pathname.startsWith('/watch')) return null;
        const { current, total, paused } = videoTimes();

        const titleEl =
            document.querySelector('.watch-title, [class*="VideoTitle"], .ellipsize-text') ||
            document.querySelector('[class*="episodeTitle"]');
        let title = titleEl ? titleEl.textContent.trim() : '';
        if (!title)
            title = document.title.replace('Netflix', '').replace(/[-–|]/g, '').trim();

        const epEl    = document.querySelector('[class*="episodeTitle"]');
        const episode = epEl ? epEl.textContent.trim() : '';

        return { site: 'netflix', title, episode, current_time: current, total_time: total, paused };
    }

    // ── Shinden.pl ────────────────────────────────────────────────────────────
    function scrapeShinden() {
        let title   = '';
        let episode = '';

        // ── Anime title ───────────────────────────────────────────────────────
        // Shinden breadcrumb structure: Home > Anime > [Anime Title] > [Episode label]
        // The anime title sits at breadcrumb index -2; episode label at -1.
        const bc = document.querySelector('ol.breadcrumb, ul.breadcrumb, .breadcrumb');
        if (bc) {
            const items = [...bc.querySelectorAll('li')].map(li => li.textContent.trim()).filter(Boolean);
            // Last item is current page (episode), second-to-last is anime title
            if (items.length >= 2) {
                title = items[items.length - 2];
                const lastItem = items[items.length - 1];
                // Extract episode number: "Odcinek 5", "Epizod 5", "Episode 5"
                const epMatch = lastItem.match(/(?:odcinek|epizod|episode|odc\.?|ep\.?)\s*(\d+)/i);
                if (epMatch) episode = epMatch[1];
            }
        }

        // Fallback title from h1 (may include episode name — use only if breadcrumb failed)
        if (!title) {
            const h1 = document.querySelector('h1');
            if (h1) title = h1.textContent.trim();
        }

        // Fallback title from <title> tag — format: "Anime Title - Odcinek X | Shinden"
        if (!title) {
            const parts = document.title.split(/[-–|]/);
            title = (parts[0] || '').trim();
        }

        // Fallback episode from <title>: "... - Odcinek 5 | Shinden"
        if (!episode) {
            const m = document.title.match(/(?:odcinek|epizod|episode|odc\.?|ep\.?)\s*(\d+)/i);
            if (m) episode = m[1];
        }

        // Clean site-name suffix from title
        title = cleanAnimeTitle(title);

        // NOTE: Do NOT use the URL /episode/<id> — that is a DB record id, not episode number.

        let { current, total, paused } = videoTimes();
        if (current === null && typeof window.jwplayer === 'function') {
            try {
                const jw = window.jwplayer();
                current = Math.floor(jw.getPosition());
                total   = Math.floor(jw.getDuration());
                paused  = jw.getState() !== 'playing';
            } catch (_) {}
        }

        // Cover from page (poster image)
        const imgEl = document.querySelector(
            '.poster img, .cover img, [class*="cover"] img, [class*="poster"] img, img[alt*="poster"], img[alt*="cover"]');
        const cover_url = imgEl ? (imgEl.src || imgEl.dataset.src || '') : '';

        return { site: 'shinden', title, episode,
                 current_time: current, total_time: total, paused,
                 cover_url };
    }

    // ── OgladajAnime.pl ───────────────────────────────────────────────────────
    function scrapeOgladajAnime() {
        let title   = '';
        let episode = '';

        // ── Anime title ───────────────────────────────────────────────────────
        // OgladajAnime page structure varies: episode pages have the anime title
        // in a link/heading above the episode title. We try multiple strategies
        // in order of reliability.

        // Strategy 1: dedicated anime-title element
        const animeTitleEl =
            document.querySelector('.anime-title, [class*="anime-title"]') ||
            document.querySelector('.series-title, [class*="series-title"]') ||
            document.querySelector('[class*="title-anime"], [class*="animeTitle"]');
        if (animeTitleEl) title = animeTitleEl.textContent.trim();

        // Strategy 2: breadcrumb — second-to-last item is usually the anime name
        if (!title) {
            const bc = document.querySelector('.breadcrumb, nav[aria-label="breadcrumb"], ol.breadcrumbs');
            if (bc) {
                const items = [...bc.querySelectorAll('li, a')]
                    .map(el => el.textContent.trim())
                    .filter(t => t && t !== '›' && t !== '/' && t !== 'Home' && t !== 'Strona główna');
                // last item is current page (episode), second-to-last is anime title
                if (items.length >= 2) title = items[items.length - 2];
            }
        }

        // Strategy 3: <title> tag — format often "Anime Name Odcinek X | OgladajAnime"
        if (!title) {
            const raw = document.title.replace(/\|.*$/, '').trim();
            // strip trailing episode info
            title = raw.replace(/\s*[-–]\s*(?:odcinek|episode|odc\.?|ep\.?)\s*\d+.*$/i, '').trim();
        }

        // Strategy 4: h1 as last resort (may be episode title on some pages)
        if (!title) {
            const h1 = document.querySelector('h1');
            if (h1) title = h1.textContent.trim();
        }
        // Strip site-name suffix from whatever source we got the title from
        title = cleanAnimeTitle(title);

        // ── Episode number ────────────────────────────────────────────────────
        // Priority 1: breadcrumb or page elements with explicit keyword
        const bc2 = document.querySelector('.breadcrumb, nav[aria-label="breadcrumb"], ol.breadcrumbs');
        if (bc2) {
            bc2.querySelectorAll('li, a').forEach(el => {
                const m = el.textContent.match(/(?:odcinek|episode|odc\.?|ep\.?)\s*(\d+)/i);
                if (m) episode = m[1];
            });
        }
        // Priority 2: document title
        if (!episode) {
            const m = document.title.match(/(?:odcinek|episode|odc\.?|ep\.?)\s*(\d+)/i);
            if (m) episode = m[1];
        }
        // Priority 3: URL — short numeric segment only
        if (!episode) {
            const segs = location.pathname.split('/').filter(Boolean);
            const epSeg = segs.slice().reverse().find(s => /^\d{1,4}$/.test(s));
            if (epSeg) episode = epSeg;
        }

        // ── Video times ───────────────────────────────────────────────────────
        let { current, total, paused } = videoTimes();
        if (current === null && typeof window.jwplayer === 'function') {
            try {
                const jw = window.jwplayer();
                current = Math.floor(jw.getPosition());
                total   = Math.floor(jw.getDuration());
                paused  = jw.getState() !== 'playing';
            } catch (_) {}
        }

        // ── Cover image ───────────────────────────────────────────────────────
        // OgladajAnime uses lozad lazy loading. The cover image HTML looks like:
        //   <img class="img-fluid lozad rounded float-right"
        //        data-srcset="https://cdn.ogladajanime.pl/images/anime_new/72884/2.webp?..."
        //        srcset="https://cdn.ogladajanime.pl/images/anime_new/72884/2.webp?..."
        //        src="..." alt="Anime Title">
        // Priority: data-srcset / srcset (CDN WebP) > data-src > src
        function extractCoverUrl(el) {
            if (!el) return '';
            // data-srcset and srcset can be "url w h, url2 w h" — take first entry
            const srcset = (el.dataset.srcset || el.getAttribute('srcset') || '').trim();
            if (srcset) {
                const first = srcset.split(',')[0].trim().split(/\s+/)[0];
                if (first.startsWith('http')) return first;
            }
            return (el.dataset.src || el.src || '').trim();
        }

        // 1. Primary: lozad image matching CDN domain
        let coverEl =
            document.querySelector('img.lozad[data-srcset*="cdn.ogladajanime"]') ||
            document.querySelector('img.lozad[srcset*="cdn.ogladajanime"]') ||
            document.querySelector('img.lozad.float-right, img.lozad.rounded.float-right') ||
            // 2. Any image with the CDN URL
            document.querySelector('img[data-srcset*="cdn.ogladajanime"]') ||
            document.querySelector('img[srcset*="cdn.ogladajanime"]') ||
            // 3. Fallback selectors
            document.querySelector('img.img-fluid.rounded[alt]') ||
            document.querySelector('img[alt="' + title + '"]');

        const cover_url = extractCoverUrl(coverEl);

        return { site: 'ogladajanime', title, episode,
                 current_time: current, total_time: total, paused,
                 cover_url };
    }


    // ╔══════════════════════════════════════════════════════════╗
    // ║                      ROUTER                             ║
    // ╚══════════════════════════════════════════════════════════╝

    function scrapeCurrentPage() {
        const host = location.hostname.replace(/^www\./, '');
        if (host === 'youtube.com')       return scrapeYouTube();
        if (host === 'cda.pl')            return scrapeCDA();
        if (host === 'rumble.com')        return scrapeRumble();
        if (host === 'twitch.tv')         return scrapeTwitch();
        if (host === 'netflix.com')       return scrapeNetflix();
        if (host === 'shinden.pl')        return scrapeShinden();
        if (host === 'ogladajanime.pl')   return scrapeOgladajAnime();
        return null;
    }

    // ╔══════════════════════════════════════════════════════════╗
    // ║                   SEND LOOP                             ║
    // ╚══════════════════════════════════════════════════════════╝

    let lastKey = '';

    function tick() {
        const data = scrapeCurrentPage();
        if (!data) return;

        // Dedup key: site + title + paused + time bucket (6s resolution)
        const key = JSON.stringify({
            site:   data.site,
            title:  data.title || data.streamer || '',
            bucket: Math.floor((data.current_time || 0) / 6),
            paused: data.paused,
        });
        if (key === lastKey) return;
        lastKey = key;

        send(data);
    }

    setTimeout(() => {
        tick();
        setInterval(tick, INTERVAL);
    }, 2500);

    // SPA navigation detection
    let lastUrl = location.href;
    new MutationObserver(() => {
        if (location.href !== lastUrl) {
            lastUrl = location.href;
            lastKey = '';
            setTimeout(tick, 1800);
        }
    }).observe(document.documentElement, { subtree: true, childList: true });

})();
