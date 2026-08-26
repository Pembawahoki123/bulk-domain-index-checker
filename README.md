# Bulk Domain Index Checker

UI bulk checker seperti contoh: pengguna cukup paste domain biasa, tanpa mengetik `site:`.

Contoh input:

```text
domain1.com
domain2.net
domain3.org
```

Backend otomatis membentuk query pencarian untuk tiap domain dan mengambil hasil melalui Serper API.

## Fitur

- Maksimal 1000 domain per batch
- Otomatis normalisasi `http://`, `https://`, `www.`
- Deduplicate domain
- INDEX / NOT INDEX / ERROR
- Menampilkan title, URL hasil pertama, dan estimasi total hasil
- Copy All
- Download TXT
- Worker concurrency + retry saat rate-limit
- Dark neon UI responsive

## Instalasi Windows PowerShell

Masuk ke folder project:

```powershell
cd .\bulk-domain-index-checker
```

Buat virtual environment:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install:

```powershell
pip install -r requirements.txt
```

Copy file environment:

```powershell
Copy-Item .env.example .env
notepad .env
```

Isi:

```text
SERPER_API_KEY=API_KEY_KAMU
```

Jalankan:

```powershell
python server.py
```

Lalu buka:

```text
http://127.0.0.1:5000
```

## Instalasi Ubuntu / VPS

```bash
cd bulk-domain-index-checker
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
nano .env
python server.py
```

Buka port 5000 jika memang ingin diakses langsung dari luar. Untuk production lebih baik reverse-proxy melalui Nginx dan jalankan Flask di localhost.

## Catatan penting

Tool ini tidak scraping halaman Google secara langsung. Ia memakai Search API sehingga lebih stabil dibanding browser scraping/CAPTCHA.

`TOTAL INDEX` adalah angka yang dilaporkan oleh search provider dan dapat berupa estimasi, bukan angka absolut Google Search Console.

Untuk 1000 domain, konsumsi API juga sekitar 1000 query. Pastikan quota/credit API cukup.
