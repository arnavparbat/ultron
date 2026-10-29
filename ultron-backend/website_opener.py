"""
Ultron Website Opener & URL Normalizer
Handles spoken domains, phonetic normalization, and direct reliable browser navigation.
"""
import re
import os
import subprocess
import webbrowser
from typing import Tuple

COMMON_WEBSITES = {
    "youtube": "https://www.youtube.com",
    "google": "https://www.google.com",
    "chatgpt": "https://chatgpt.com",
    "chat gpt": "https://chatgpt.com",
    "github": "https://github.com",
    "reddit": "https://www.reddit.com",
    "twitter": "https://x.com",
    "x": "https://x.com",
    "gmail": "https://mail.google.com",
    "netflix": "https://www.netflix.com",
    "twitch": "https://www.twitch.tv",
    "amazon": "https://www.amazon.com",
    "wikipedia": "https://www.wikipedia.org",
    "instagram": "https://www.instagram.com",
    "linkedin": "https://www.linkedin.com",
    "spotify web": "https://open.spotify.com",
    "facebook": "https://www.facebook.com",
    "fb": "https://www.facebook.com",
    "whatsapp": "https://web.whatsapp.com",
    "whatsapp web": "https://web.whatsapp.com",
    "canva": "https://www.canva.com",
    "leetcode": "https://leetcode.com",
    "claude": "https://claude.ai",
    "claude ai": "https://claude.ai",
    "gemini": "https://gemini.google.com",
    "google gemini": "https://gemini.google.com",
    "stackoverflow": "https://stackoverflow.com",
    "stack overflow": "https://stackoverflow.com",
    "pinterest": "https://www.pinterest.com",
    "flipkart": "https://www.flipkart.com",
    "hotstar": "https://www.hotstar.com",
    "disney hotstar": "https://www.hotstar.com",
    "disney plus": "https://www.disneyplus.com",
    "prime video": "https://www.primevideo.com",
    "amazon prime": "https://www.primevideo.com",
    "google maps": "https://maps.google.com",
    "maps": "https://maps.google.com",
    "google drive": "https://drive.google.com",
    "drive": "https://drive.google.com",
    "google docs": "https://docs.google.com",
    "docs": "https://docs.google.com",
    "google sheets": "https://sheets.google.com",
    "sheets": "https://sheets.google.com",
    "quora": "https://www.quora.com",
    "medium": "https://medium.com",
    "yahoo": "https://www.yahoo.com",
    "bing": "https://www.bing.com",
    "duckduckgo": "https://duckduckgo.com",
    "hugging face": "https://huggingface.co",
    "huggingface": "https://huggingface.co",
    "kaggle": "https://www.kaggle.com",
    "coursera": "https://www.coursera.org",
    "udemy": "https://www.udemy.com"
}

TLD_LIST = [
    "com", "org", "net", "ai", "in", "io", "co", "dev", "app", "edu", "gov", 
    "tech", "me", "online", "xyz", "info", "biz", "tv", "gg", "uk", "us", "ca",
    "de", "jp", "fr", "au", "ru", "live", "site", "store", "link", "club"
]

class WebsiteOpener:
    def __init__(self):
        pass

    def normalize_spoken_url(self, text: str) -> Tuple[bool, str]:
        """
        Parses spoken phrases like:
        - "open youtube"
        - "open youtube in chrome"
        - "chatgpt.com"
        - "youtube dot com"
        - "open leetcode"
        - "my startup dot ai"
        - "open reddit"
        Returns (is_url, normalized_url)
        """
        raw = text.lower().strip()

        # 1. Clean polite & launch prefixes
        prefix_pattern = r"^(?:can you\s+|could you\s+|please\s+|will you\s+)*(?:open\s+up|open|visit|go\s+to|browse\s+to|browse|launch|start|run|bring\s+up)?(?:\s+(?:the\s+)?(?:website|site|web|page))?\s*"
        cleaned = re.sub(prefix_pattern, "", raw).strip()

        # 2. Clean trailing browser, website, and filler suffixes
        suffix_pattern = r"(?:\s+(?:in\s+(?:google\s+)?chrome|on\s+(?:google\s+)?chrome|in\s+(?:the\s+)?browser|on\s+(?:the\s+)?browser|in\s+edge|in\s+brave|in\s+firefox|website|site|web|page|for\s+me|please))+$"
        cleaned = re.sub(suffix_pattern, "", cleaned).strip()

        if not cleaned:
            return False, ""

        # Check common shortcut dictionary first
        if cleaned in COMMON_WEBSITES:
            return True, COMMON_WEBSITES[cleaned]

        # Convert spoken phrases to domain characters
        domain_str = cleaned.replace(" dot ", ".").replace("dot ", ".").replace(" dot", ".")
        domain_str = domain_str.replace(" slash ", "/").replace("slash ", "/").replace(" slash", "/")
        domain_str = domain_str.replace(" hyphen ", "-").replace(" dash ", "-")
        domain_str = domain_str.replace(" ", "")  # Remove spaces within domain

        # Check standard URL
        if domain_str.startswith("http://") or domain_str.startswith("https://"):
            return True, domain_str

        # Check for www. prefix
        if domain_str.startswith("www."):
            return True, "https://" + domain_str

        # Check for domain regex
        tld_pattern = r"(?:[a-zA-Z0-9\-]+\.)+(" + "|".join(TLD_LIST) + r")(?::\d+)?(/.*)?"
        match = re.search(tld_pattern, domain_str)
        if match:
            url_part = match.group(0)
            return True, "https://" + url_part

        # If user explicitly specified website intent (e.g. "open website flipkart" or "open leetcode in chrome")
        if any(k in raw for k in ["website", "site", "web", "in chrome", "on chrome", "browser"]):
            word = re.sub(r"[^a-zA-Z0-9\-]", "", cleaned)
            if word and len(word) > 1 and word not in ["chrome", "browser", "edge", "firefox"]:
                return True, f"https://www.{word}.com"

        return False, ""

    def open_url(self, url: str, simulate_typing: bool = False) -> Tuple[bool, str]:
        """
        Opens the URL in Chrome or default browser.
        Direct navigation ensures reliable, instant tab loading without blank pages or focus issues.
        """
        clean_url = url.strip()
        if not clean_url.startswith("http://") and not clean_url.startswith("https://"):
            clean_url = "https://" + clean_url

        try:
            # Locate Chrome executable on Windows
            chrome_paths = [
                os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
                os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
                os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe")
            ]
            chrome_exe = None
            for p in chrome_paths:
                if os.path.exists(p):
                    chrome_exe = p
                    break

            if chrome_exe:
                # Direct navigation passing the URL directly to Chrome
                subprocess.Popen([chrome_exe, clean_url])
            else:
                webbrowser.open(clean_url)

            return True, f"Navigated to {clean_url}"

        except Exception as e:
            # Fallback to standard webbrowser
            try:
                webbrowser.open(clean_url)
                return True, f"Navigated to {clean_url} (fallback)"
            except Exception as e2:
                return False, f"Failed to open {clean_url}: {e2}"
