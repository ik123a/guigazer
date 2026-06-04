import asyncio
from loguru import logger

from agent.core import GuiGazerAgent
from agent.controller import PlaywrightController
from agent.reasoner import VisionReasoner
from detector.model import GUIDetector

async def main():
    logger.info("Starting GuiGazer Demo...")
    
    # Initialize components
    detector = GUIDetector()
    reasoner = VisionReasoner()
    controller = PlaywrightController()
    
    agent = GuiGazerAgent(detector=detector, reasoner=reasoner, controller=controller)
    
    # Run an accessibility audit to test detection + screenshotting
    logger.info("Running Accessibility Audit on https://example.com...")
    result = await agent.run_accessibility_audit(url="https://example.com")
    
    logger.info(f"Audit completed! Found {result['summary'].get('total_elements', 0)} elements.")
    logger.info(f"Annotated screenshot saved to: {result['screenshot_path']}")
    
    # Cleanup Playwright
    await controller.cleanup()
    logger.info("Demo complete. Check the screenshots folder!")

if __name__ == "__main__":
    asyncio.run(main())
