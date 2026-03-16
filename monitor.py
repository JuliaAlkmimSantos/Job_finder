import requests
import hashlib
import json
import os
import smtplib
from email.mime.text import MIMEText
from playwright.sync_api import sync_playwright

import re
from bs4 import BeautifulSoup

def clean_content(html, org):
    """
    Strip dynamic elements and extract only job-relevant content.
    Returns cleaned text for hashing.
    """
    soup = BeautifulSoup(html, "html.parser")

    # Remove elements that change every load
    for tag in soup.find_all("script"):
        tag.decompose()
    for tag in soup.find_all("style"):
        tag.decompose()
    for tag in soup.find_all("noscript"):
        tag.decompose()
    for tag in soup.find_all("iframe"):
        tag.decompose()
    for tag in soup.find_all("meta"):
        tag.decompose()
    for tag in soup.find_all("link"):
        tag.decompose()

    # Get visible text only
    text = soup.get_text(separator=" ", strip=True)

    # Remove common dynamic patterns
    text = re.sub(r'\d{10,}', '', text)                    # unix timestamps
    text = re.sub(r'[a-f0-9]{32,}', '', text)              # session tokens/hashes
    text = re.sub(r'csrf[^"\'>\s]*', '', text, flags=re.I) # CSRF tokens
    text = re.sub(r'\s+', ' ', text).strip()               # normalize whitespace

    return text

TARGETS = {
    "WWF Jobs": "https://careers-wwfus.icims.com/jobs/intro?hashed=-435743484",
    "WWF Internships": "https://careers-wwfus.icims.com/jobs/search?ss=1&searchKeyword=internship",
    "WSC Jobs and Internships": "https://sjobs.brassring.com/TGnewUI/Search/Home/Home?partnerid=25965&siteid=5168#home",
    "Green Jobs board GIS": "https://greenjobs.greenjobsearch.org/?s=GIS&location=&ptype=job_listing&lat=&lng=&radius=0",
    "Green Jobs board Data": "https://greenjobs.greenjobsearch.org/?s=data&location=&ptype=job_listing&lat=&lng=&radius=0",
    "National Wildlife Federation Jobs": "https://recruiting.ultipro.com/NAT1047NWF/JobBoard/1ca8346a-33cc-401d-90d9-d7f752fdfd7d/?q=&o=postedDateDesc",
    "Rainforest Alliance Data jobs": "https://recruiting.ultipro.com/RAI1015FORES/JobBoard/7a1c3d86-f0fa-4e0e-a501-dcfedd4f7d8c/?q=&o=postedDateDesc&f5=SuEojyZwZ0mFPIeDMrpDMQ",
    "Pano AI jobs": "https://jobs.ashbyhq.com/pano-ai",
    "Gridware jobs": "https://api.lever.co/v0/postings/gridware",
    'World Resources Institute Jobs': "https://www.wri.org/careers/jobs",
    'Nature Serve Jobs': "https://www.natureserve.org/careers",
    'EDF jobs': "https://www.edf.org/jobs",
    'Felt jobs': "https://felt.com/careers"}

# These load content via plain HTML or return JSON directly
STATIC_URLS = {"Gridware jobs", "Green Jobs board GIS", "Green Jobs board Data"}

HASH_FILE = "page_hashes.json"

def load_hashes():
    try:
        with open(HASH_FILE) as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_hashes(hashes):
    with open(HASH_FILE, "w") as f:
        json.dump(hashes, f)

def fetch_static(url):
    """Simple HTTP request for static pages and APIs."""
    resp = requests.get(url, timeout=15, headers={
        "User-Agent": "Mozilla/5.0"
    })
    return resp.text

def fetch_dynamic(url, browser):
    """Headless browser for JavaScript-rendered pages."""
    page = browser.new_page()
    try:
        page.goto(url, wait_until="networkidle", timeout=30000)
        content = page.content()
    finally:
        page.close()
    return content

def send_email(changed_orgs):
    sender = os.environ["EMAIL_ADDRESS"]
    password = os.environ["EMAIL_PASSWORD"]
    receiver = sender

    body = "New job posting changes detected:\n\n" + "\n".join(changed_orgs)
    body += "\n\nGo check their careers pages!"

    msg = MIMEText(body)
    msg["Subject"] = "Job Alert: Career page updated"
    msg["From"] = sender
    msg["To"] = receiver

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender, password)
        server.sendmail(sender, receiver, msg.as_string())

    print("Email sent!")

def check_for_changes():
    old_hashes = load_hashes()
    new_hashes = {}
    changed = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        for org, url in TARGETS.items():
            try:
                if org in STATIC_URLS:
                    content = fetch_static(url)
                else:
                    content = fetch_dynamic(url, browser)

                # Clean before hashing
                cleaned = clean_content(content, org)
                current_hash = hashlib.md5(cleaned.encode()).hexdigest()
                new_hashes[org] = current_hash

                if org in old_hashes and old_hashes[org] != current_hash:
                    changed.append(f"{org}: {url}")
                    print(f"CHANGED: {org}")
                else:
                    print(f"No change: {org}")

            except Exception as e:
                print(f"Error checking {org}: {e}")
                if org in old_hashes:
                    new_hashes[org] = old_hashes[org]

        browser.close()

    save_hashes(new_hashes)

    if changed:
        send_email(changed)
    else:
        print("No changes detected.")
if changed:
    send_email(changed)
else:
    print("No changes detected.")


if __name__ == "__main__":
    check_for_changes()
