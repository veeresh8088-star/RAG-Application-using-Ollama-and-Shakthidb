import os
import time
import hashlib
import requests

VT_API_KEY = os.getenv("VT_API_KEY")
VT_URL = "https://www.virustotal.com/api/v3"

if not VT_API_KEY:
    raise RuntimeError("VT_API_KEY not set")

HEADERS = {
    "x-apikey": VT_API_KEY
}

# ---------- HASH ----------
def sha256_of_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------- CHECK BY HASH ----------
def check_hash(file_hash):
    r = requests.get(
        f"{VT_URL}/files/{file_hash}",
        headers=HEADERS
    )
    if r.status_code == 200:
        stats = r.json()["data"]["attributes"]["last_analysis_stats"]
        return stats
    return None


# ---------- FULL SCAN ----------
def upload_and_scan(file_path):
    with open(file_path, "rb") as f:
        r = requests.post(
            f"{VT_URL}/files",
            headers=HEADERS,
            files={"file": f}
        )

    if r.status_code != 200:
        raise Exception("VirusTotal upload failed")

    analysis_id = r.json()["data"]["id"]

    # Wait longer (FREE API NEEDS THIS)
    for _ in range(15):   # ~45 seconds
        time.sleep(3)
        report = requests.get(
            f"{VT_URL}/analyses/{analysis_id}",
            headers=HEADERS
        ).json()

        status = report["data"]["attributes"]["status"]
        if status == "completed":
            return report["data"]["attributes"]["stats"]

    raise Exception("VirusTotal scan timeout")


# ---------- MAIN ----------
def scan_file(file_path):
    file_hash = sha256_of_file(file_path)

    # Step 1: hash lookup (FAST)
    stats = check_hash(file_hash)
    if stats:
        return stats

    # Step 2: full scan (SLOW)
    return upload_and_scan(file_path)
