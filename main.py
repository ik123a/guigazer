"""
GuiGazer — FastAPI Server & WebSocket Hub
==========================================
Main entry point. Serves the dashboard UI at `/`, provides REST
endpoints for one-off operations, and a WebSocket `/ws` endpoint
for the live agent-action feed.
"""

from __future__ import annotations

import asyncio
import base64
import io
import json
import os
import traceback
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger

from config import settings

# ---------------------------------------------------------------------------
# Lifespan — initialize heavy resources once
# ---------------------------------------------------------------------------

detector_instance = None
reasoner_instance = None
controller_instance = None
agent_instance = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Warm up models and browser on startup."""
    global detector_instance, reasoner_instance, controller_instance, agent_instance

    logger.info("🚀 GuiGazer starting up...")

    # Lazy imports so the app can still start even if some deps are missing
    try:
        from detector.model import GUIDetector
        detector_instance = GUIDetector()
        logger.info("✅ YOLOv8 detector loaded")
    except Exception as e:
        logger.warning(f"⚠️  Detector not loaded (will use mock): {e}")

    try:
        from agent.reasoner import VisionReasoner
        reasoner_instance = VisionReasoner()
        logger.info("✅ Vision reasoner initialized")
    except Exception as e:
        logger.warning(f"⚠️  Reasoner not loaded: {e}")

    try:
        from agent.controller import PlaywrightController
        controller_instance = PlaywrightController()
        logger.info("✅ Playwright controller ready")
    except Exception as e:
        logger.warning(f"⚠️  Controller not loaded: {e}")

    # Create screenshots directory
    Path("screenshots").mkdir(exist_ok=True)

    yield

    # Cleanup
    if controller_instance:
        try:
            await controller_instance.cleanup()
        except Exception:
            pass
    logger.info("👋 GuiGazer shutting down")


# ---------------------------------------------------------------------------
# FastAPI App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="GuiGazer",
    description="AI-powered GUI Automation Agent with Visual Detection & Reasoning",
    version="1.0.0",
    lifespan=lifespan,
)

# Mount static frontend
app.mount("/static", StaticFiles(directory="frontend"), name="static")


@app.get("/")
async def serve_ui():
    """Serve the dashboard."""
    return FileResponse("frontend/index.html")


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "detector_loaded": detector_instance is not None,
        "reasoner_loaded": reasoner_instance is not None,
        "controller_loaded": controller_instance is not None,
    }


# ---------------------------------------------------------------------------
# WebSocket — Live Agent Feed
# ---------------------------------------------------------------------------

active_connections: list[WebSocket] = []


async def broadcast(data: dict):
    """Send a message to all connected WebSocket clients."""
    text = json.dumps(data)
    disconnected = []
    for ws in active_connections:
        try:
            await ws.send_text(text)
        except Exception:
            disconnected.append(ws)
    for ws in disconnected:
        active_connections.remove(ws)


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    """
    WebSocket handler for live agent interaction.
    Receives commands: start_task, run_audit.
    Sends back: status updates, step results, completion, errors.
    """
    await ws.accept()
    active_connections.append(ws)
    logger.info(f"🔗 WebSocket client connected ({len(active_connections)} total)")

    try:
        while True:
            raw = await ws.receive_text()
            msg = json.loads(raw)
            msg_type = msg.get("type")

            if msg_type == "start_task":
                asyncio.create_task(
                    _handle_task(ws, msg.get("task", ""), msg.get("url", ""))
                )
            elif msg_type == "run_audit":
                asyncio.create_task(
                    _handle_audit(ws, msg.get("url", ""))
                )
            else:
                await ws.send_text(json.dumps({"type": "error", "message": f"Unknown command: {msg_type}"}))

    except WebSocketDisconnect:
        active_connections.remove(ws)
        logger.info(f"🔌 WebSocket client disconnected ({len(active_connections)} remaining)")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        if ws in active_connections:
            active_connections.remove(ws)


async def _handle_task(ws: WebSocket, task: str, url: str):
    """Run a full agent task and stream step updates via WebSocket."""
    if not task:
        await ws.send_text(json.dumps({"type": "error", "message": "Task description is required"}))
        return

    await ws.send_text(json.dumps({"type": "status", "status": "running", "task": task}))

    try:
        from agent.core import GuiGazerAgent

        agent = GuiGazerAgent(
            detector=detector_instance,
            reasoner=reasoner_instance,
            controller=controller_instance,
        )

        async def step_callback(step_data: dict):
            """Called after each agent step to stream progress."""
            # Convert screenshot to base64 for the frontend
            if "screenshot" in step_data and step_data["screenshot"] is not None:
                buffered = io.BytesIO()
                step_data["screenshot"].save(buffered, format="PNG")
                step_data["screenshot_b64"] = base64.b64encode(buffered.getvalue()).decode("utf-8")
                del step_data["screenshot"]

            await ws.send_text(json.dumps({"type": "step", **step_data}))

        result = await agent.run_task(task=task, url=url, callback=step_callback)

        await ws.send_text(json.dumps({
            "type": "complete",
            "task": task,
            "steps_taken": result.get("steps_taken", 0),
            "completed": result.get("completed", False),
        }))

    except Exception as e:
        logger.error(f"Task error: {traceback.format_exc()}")
        await ws.send_text(json.dumps({"type": "error", "message": str(e)}))

    finally:
        await ws.send_text(json.dumps({"type": "status", "status": "idle"}))


async def _handle_audit(ws: WebSocket, url: str):
    """Run accessibility audit and return results."""
    await ws.send_text(json.dumps({"type": "status", "status": "auditing"}))

    try:
        from agent.core import GuiGazerAgent
        from audit.report import generate_html_report

        agent = GuiGazerAgent(
            detector=detector_instance,
            reasoner=reasoner_instance,
            controller=controller_instance,
        )

        audit_result = await agent.run_accessibility_audit(url=url)
        html_report = generate_html_report(audit_result)

        await ws.send_text(json.dumps({
            "type": "audit_result",
            "summary": audit_result.get("summary", {}),
            "report_html": html_report,
        }))

    except Exception as e:
        logger.error(f"Audit error: {traceback.format_exc()}")
        await ws.send_text(json.dumps({"type": "error", "message": str(e)}))

    finally:
        await ws.send_text(json.dumps({"type": "status", "status": "idle"}))


# ---------------------------------------------------------------------------
# Run with: uvicorn main:app --host 0.0.0.0 --port 8001 --reload
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level,
        reload=True,
    )
