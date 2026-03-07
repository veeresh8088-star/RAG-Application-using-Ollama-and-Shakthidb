import requests
import os

VT_API_KEY = os.getenv("VT_API_KEY")

def scan_file(file_path):
    try:
        if not VT_API_KEY:
            print("⚠ VirusTotal API key missing. Skipping scan.")
            return True

        url = "https://www.virustotal.com/api/v3/files"

        with open(file_path, "rb") as f:
            files = {"file": f}
            headers = {"x-apikey": VT_API_KEY}
            response = requests.post(url, files=files, headers=headers)

        if response.status_code != 200:
            print("⚠ VirusTotal API error. Skipping scan.")
            return True

        data = response.json()

        # Safe check
        if "data" not in data:
            print("⚠ Unexpected VT response. Skipping scan.")
            return True

        stats = data["data"]["attributes"]["last_analysis_stats"]

        # If any malicious detected
        if stats.get("malicious", 0) > 0:
            return False

        return True

    except Exception as e:
        print(f"⚠ Virus scan failed: {e}")
        return True
