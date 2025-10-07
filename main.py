
import httpx
import logging
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

# ------------------- Config -------------------
API_SERVERS = [
    "https://without-proxy.vercel.app",
    "https://without-proxy1.vercel.app",
    "https://without-proxy2.vercel.app",
]

current_server_index = 0
fail_counter = 0
MAX_FAILS = 3

TELEGRAM_BOT_TOKEN = "7652042264:AAGc6DQ-OkJ8PaBKJnc_NkcCseIwmfbHD-c"
TELEGRAM_CHAT_ID = "5029478739"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("main-api")

# ------------------- FastAPI Setup -------------------
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

# ------------------- Telegram Notify -------------------
async def notify_telegram(message: str):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
        async with httpx.AsyncClient() as client:
            await client.post(url, data=payload)
    except Exception as e:
        logger.error(f"Telegram notify failed: {e}")

# ------------------- Helpers -------------------
def get_current_server():
    return API_SERVERS[current_server_index]

async def switch_server():
    global current_server_index, fail_counter
    old_server = get_current_server()
    current_server_index = (current_server_index + 1) % len(API_SERVERS)
    new_server = get_current_server()
    fail_counter = 0

    msg = f"⚠️ API Switched\n🔁 From: {old_server}\n✅ To: {new_server}"
    logger.warning(msg)
    await notify_telegram(msg)

# ------------------- Main Logic -------------------
@app.get("/scrape/{username}")
async def scrape_user(username: str):
    global fail_counter

    for attempt in range(len(API_SERVERS)):
        server = get_current_server()
        url = f"{server}/scrape/{username}"

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(url)

            # ✅ If working response
            if res.status_code == 200:
                fail_counter = 0
                return res.json()

            # ⚠️ If Instagram says user not found (404) → don't switch
            elif res.status_code == 404:
                fail_counter = 0
                return {"error": "User not found", "from": server}

            # ❌ Any other response = API issue
            else:
                logger.warning(f"⚠️ Failed from {server}: {res.status_code}")
                fail_counter += 1
                if fail_counter >= MAX_FAILS:
                    await switch_server()

        except Exception as e:
            logger.warning(f"❌ Error from {server}: {e}")
            fail_counter += 1
            if fail_counter >= MAX_FAILS:
                await switch_server()

    raise HTTPException(status_code=502, detail="All servers failed")

@app.get("/health")
async def health():
    return {"status": "ok", "current_server": get_current_server()}
