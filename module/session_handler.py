import asyncio

from online_storage import Upload, Download
from playwright.async_api import async_playwright


# ─────────────────────────────────────────────────────────────────────────────
# Configuration Constants
# ─────────────────────────────────────────────────────────────────────────────
STORAGE_PATH = "storage/storage_state.json"                # Persistent session state file
TARGET_URL = "https://socialearning.org/earner/dashboard"  # Dashboard URL target for login/session testing
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36"  # Realistic UA string

BROWSER_ARGS = [
    "--no-sandbox",                      # Required in containerized/CI environments to avoid Chromium sandbox issues
    "--disable-infobars",                # Prevent "Chrome is being controlled by automation" banner
    "--disable-dev-shm-usage",           # Workaround for limited /dev/shm on small containers
    "--disable-blink-features=AutomationControlled"  # Reduce automation fingerprinting
]


async def main():
      async with async_playwright() as p:
            # Launch Chromium (using installed Chrome for realism)
            browser = await p.chromium.launch(
                headless=False,
                args=BROWSER_ARGS,
                channel="chrome",
            )

            # Always try to pull remote session state before creating context
            Download("storage_state.json")

            # Browser context setup with localization, UA, and persisted storage state
            context = await browser.new_context(
                locale="en-US",
                user_agent=USER_AGENT,
                color_scheme="dark",
                storage_state=STORAGE_PATH,
            )

            await start(context, browser)

async def start(context, browser):
      page = await context.new_page()

      # Attempt initial navigation to target for session warmup
      try:
        await page.goto(TARGET_URL, wait_until="domcontentloaded")
        await asyncio.sleep(5)  # simulate idle user (5s)
      except Exception as error:
             print (f"Interaction skipped: {str(error)}")

      # ─────────────────────────────────────────────────────────────────────
      # Main session loop → keeps session alive and syncs state periodically
      # ─────────────────────────────────────────────────────────────────────
      try:
        for index in range(300):  # ~10 minutes (300 × 2s)
            if index % 30 == 0:   # every 60s (30×2s), sync state
               await context.storage_state(path=STORAGE_PATH)
               Upload("storage_state.json")

            await asyncio.sleep(2)

      finally:
          # Always persist state at shutdown regardless of loop termination
          try:
            await context.storage_state(path=STORAGE_PATH)
            Upload("storage_state.json")

            print ("[INFO] Final storage state saved & uploaded successfully")

          except Exception as error:
                 print (f"[WARN] Failed to save final storage state: {str(error)}")

          # Gracefully close resources
          await page.close()
          await context.close()
          await browser.close()

if __name__ == "__main__":
   try:
     asyncio.run(main())
   except Exception as error:
          print (f'session_handler(error): {error}')

