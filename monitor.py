import requests
import hashlib
import json
import os
import smtplib
from email.mime.text import MIMEText

TARGETS = {
    "WWF Jobs": "https://careers-wwfus.icims.com/jobs/intro?hashed=-435743484",
    "WWF Internships": "https://careers-wwfus.icims.com/jobs/search?ss=1&searchKeyword=internship"}

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

def send_email(changed_orgs):
    sender = os.environ["EMAIL_ADDRESS"]
    password = os.environ["EMAIL_PASSWORD"]
    receiver = sender  # send to yourself

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

    for org, url in TARGETS.items():
        try:
            resp = requests.get(url, timeout=15, headers={
                "User-Agent": "Mozilla/5.0"
            })
            current_hash = hashlib.md5(resp.text.encode()).hexdigest()
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

    save_hashes(new_hashes)

    if changed:
        send_email(changed)
    else:
        print("No changes detected.")

if __name__ == "__main__":
    check_for_changes()
```

**`requirements.txt`**:
```
requests