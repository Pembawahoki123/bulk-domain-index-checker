import os
import time
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

import requests
from flask import Flask, jsonify, request, send_from_directory
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__, static_folder="static", static_url_path="")

SERPER_API_KEYS = list(dict.fromkeys(
    key.strip()
    for key in [
        os.getenv("SERPER_API_KEY", ""),
        os.getenv("SERPER_API_KEY_1", ""),
        os.getenv("SERPER_API_KEY_2", ""),
        os.getenv("SERPER_API_KEY_3", ""),
    ]
    if key.strip()
))
API_KEY_LOCK = Lock()
API_KEY_CURSOR = 0
SERPER_ENDPOINT = "https://google.serper.dev/search"

MAX_DOMAINS = int(os.getenv("MAX_DOMAINS", "1000"))
WORKERS = max(1, min(int(os.getenv("WORKERS", "5")), 15))
REQUEST_DELAY = max(0.0, float(os.getenv("REQUEST_DELAY", "0.25")))
REQUEST_TIMEOUT = max(5, int(os.getenv("REQUEST_TIMEOUT", "20")))

DOMAIN_RE = re.compile(
    r"^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$",
    re.I,
)

def normalize_domain(raw: str) -> str:
    value = (raw or "").strip().lower()
    value = re.sub(r"^https?://", "", value)
    value = value.split("/")[0].split("?")[0].split("#")[0]
    if value.startswith("www."):
        value = value[4:]
    value = value.rstrip(".")
    return value

def valid_domain(domain: str) -> bool:
    return bool(DOMAIN_RE.match(domain)) and len(domain) <= 253

def next_api_key() -> str:
    global API_KEY_CURSOR
    with API_KEY_LOCK:
        key = SERPER_API_KEYS[API_KEY_CURSOR % len(SERPER_API_KEYS)]
        API_KEY_CURSOR += 1
    return key

def check_one(domain: str):
    if not SERPER_API_KEYS:
        return {
            "domain": domain,
            "status": "ERROR",
            "title": "SERPER_API_KEY belum diisi",
            "url": "",
            "total_index": 0,
        }

    # Pengguna cukup memasukkan domain. Query "site:" dibentuk otomatis di backend.
    payload = {
        "q": f"site:{domain}",
        "num": 10,
        "gl": "id",
        "hl": "id",
    }
    last_error = None
    for attempt in range(4):
        headers = {
            "X-API-KEY": next_api_key(),
            "Content-Type": "application/json",
        }
        try:
            resp = requests.post(
                SERPER_ENDPOINT,
                headers=headers,
                json=payload,
                timeout=REQUEST_TIMEOUT,
            )

            if resp.status_code == 429:
                wait = 1.5 * (2 ** attempt)
                time.sleep(wait)
                last_error = "Rate limit API"
                continue

            resp.raise_for_status()
            data = resp.json()

            organic = data.get("organic") or []
            # Serper kadang menyediakan searchInformation.totalResults.
            search_info = data.get("searchInformation") or {}
            raw_total = search_info.get("totalResults")

            total_index = 0
            if raw_total is not None:
                try:
                    total_index = int(str(raw_total).replace(",", "").replace(".", ""))
                except Exception:
                    total_index = len(organic)
            else:
                total_index = len(organic)

            if organic:
                first = organic[0] or {}
                return {
                    "domain": domain,
                    "status": "INDEX",
                    "title": first.get("title") or "(tanpa judul)",
                    "url": first.get("link") or "",
                    "total_index": total_index if total_index > 0 else len(organic),
                }

            return {
                "domain": domain,
                "status": "NOT INDEX",
                "title": "-",
                "url": "",
                "total_index": 0,
            }

        except requests.RequestException as exc:
            last_error = str(exc)
            time.sleep(0.8 * (attempt + 1))
        except Exception as exc:
            last_error = str(exc)
            break

    return {
        "domain": domain,
        "status": "ERROR",
        "title": last_error or "Unknown error",
        "url": "",
        "total_index": 0,
    }


@app.get("/")
def home():
    return send_from_directory(app.static_folder, "index.html")


@app.get("/health")
def health():
    return jsonify({
        "ok": True,
        "api_key": bool(SERPER_API_KEYS),
        "api_key_count": len(SERPER_API_KEYS),
        "max_domains": MAX_DOMAINS,
        "workers": WORKERS,
    })


@app.post("/api/check")
def bulk_check():
    body = request.get_json(silent=True) or {}
    raw_domains = body.get("domains", [])

    if not isinstance(raw_domains, list):
        return jsonify({"error": "Field domains harus berupa array."}), 400

    cleaned = []
    seen = set()
    invalid = []

    for raw in raw_domains:
        domain = normalize_domain(str(raw))
        if not domain:
            continue
        if not valid_domain(domain):
            invalid.append(domain)
            continue
        if domain not in seen:
            seen.add(domain)
            cleaned.append(domain)

    if len(cleaned) > MAX_DOMAINS:
        return jsonify({
            "error": f"Maksimal {MAX_DOMAINS} domain per batch.",
            "received": len(cleaned)
        }), 400

    if not cleaned:
        return jsonify({
            "results": [],
            "invalid": invalid,
            "total": 0,
        })

    results = [None] * len(cleaned)

    def task(index, domain):
        if REQUEST_DELAY:
            time.sleep((index % WORKERS) * REQUEST_DELAY)
        return index, check_one(domain)

    with ThreadPoolExecutor(max_workers=WORKERS) as executor:
        futures = [
            executor.submit(task, i, domain)
            for i, domain in enumerate(cleaned)
        ]

        for future in as_completed(futures):
            idx, result = future.result()
            results[idx] = result

    return jsonify({
        "results": results,
        "invalid": invalid,
        "total": len(cleaned),
    })


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=False)
