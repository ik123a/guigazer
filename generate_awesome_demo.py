import asyncio
from playwright.async_api import async_playwright
from agent.annotator import annotate_screenshot
from detector.model import Detection
import io
from PIL import Image
import os

html_content = """
<!DOCTYPE html>
<html>
<head><style>
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background: #f0f2f5; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
.card { background: white; padding: 40px; border-radius: 12px; box-shadow: 0 10px 25px rgba(0,0,0,0.05); width: 400px; }
h2 { margin-top: 0; color: #111; font-weight: 600; margin-bottom: 24px; }
input { width: 100%; padding: 14px; margin-bottom: 20px; border: 1px solid #ddd; border-radius: 6px; box-sizing: border-box; font-size: 15px; }
button { width: 100%; padding: 14px; background: #8b5cf6; color: white; border: none; border-radius: 6px; cursor: pointer; font-size: 16px; font-weight: 600; }
a { color: #8b5cf6; text-decoration: none; font-size: 14px; display: block; text-align: center; margin-top: 20px; }
</style></head>
<body>
<div class="card" id="card">
  <h2 id="title">Welcome Back</h2>
  <input type="email" placeholder="name@company.com" id="email">
  <input type="password" placeholder="Password" id="pwd">
  <button id="btn">Sign In</button>
  <a href="#" id="link">Forgot your password?</a>
</div>
</body>
</html>
"""

async def main():
    os.makedirs("screenshots", exist_ok=True)
    with open("dummy_form.html", "w") as f:
        f.write(html_content)
        
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1280, "height": 800})
        # Use absolute path for Windows compatibility
        file_url = f"file:///{os.path.abspath('dummy_form.html').replace(chr(92), '/')}"
        await page.goto(file_url)
        await asyncio.sleep(1)
        
        # Get exact bounding boxes
        box_email = await page.locator("#email").bounding_box()
        box_pwd = await page.locator("#pwd").bounding_box()
        box_btn = await page.locator("#btn").bounding_box()
        box_link = await page.locator("#link").bounding_box()
        box_title = await page.locator("#title").bounding_box()
        box_card = await page.locator("#card").bounding_box()
        
        raw = await page.screenshot(type="png")
        await browser.close()
        
    image = Image.open(io.BytesIO(raw)).convert("RGB")
    
    def to_bbox(b):
        return (int(b["x"]), int(b["y"]), int(b["x"] + b["width"]), int(b["y"] + b["height"]))
    
    detections = [
        Detection(bbox=to_bbox(box_card), class_name="Card", confidence=0.98, element_id=0),
        Detection(bbox=to_bbox(box_title), class_name="Text Block", confidence=0.95, element_id=1),
        Detection(bbox=to_bbox(box_email), class_name="Text Input", confidence=0.91, element_id=2),
        Detection(bbox=to_bbox(box_pwd), class_name="Text Input", confidence=0.92, element_id=3),
        Detection(bbox=to_bbox(box_btn), class_name="Button", confidence=0.99, element_id=4),
        Detection(bbox=to_bbox(box_link), class_name="Link", confidence=0.88, element_id=5),
    ]
    
    annotated = annotate_screenshot(image, detections)
    annotated.save("screenshots/audit.png")
    print("Generated perfect demo screenshot at screenshots/audit.png")

if __name__ == "__main__":
    asyncio.run(main())
