import asyncio
import os
import uvicorn
from multiprocessing import Process
import time
from playwright.async_api import async_playwright

def run_server():
    uvicorn.run("main:app", host="127.0.0.1", port=8001, log_level="error")

async def capture():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1400, "height": 900})
        await page.goto("http://127.0.0.1:8001")
        # Wait for the UI to fully render
        await asyncio.sleep(2)
        await page.screenshot(path="dashboard_screenshot.png", full_page=True)
        await browser.close()
        print("Successfully saved dashboard_screenshot.png!")

if __name__ == "__main__":
    server_process = Process(target=run_server)
    server_process.start()
    
    # Wait for server to start (YOLOv8 loading takes a few seconds)
    time.sleep(15)
    
    try:
        asyncio.run(capture())
    finally:
        server_process.terminate()
        server_process.join()
