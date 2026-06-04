<div align="center">
  
# 👁️ GuiGazer

**An on-device GUI automation agent using fine-tuned YOLOv8 visual grounding and multimodal LLM reasoning (NVIDIA NIM / GPT-4V).**

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg?logo=fastapi)](https://fastapi.tiangolo.com)
[![YOLOv8](https://img.shields.io/badge/YOLO-v8-FF9900.svg)](https://ultralytics.com)
[![Playwright](https://img.shields.io/badge/Playwright-1.44-2EAD33.svg?logo=playwright)](https://playwright.dev)

![GuiGazer Dashboard](dashboard_screenshot.png)

</div>

GuiGazer is an intelligent computer-use agent that automates tasks on websites and native apps. By combining **Computer Vision (YOLOv8)** for precise UI element detection with the reasoning capabilities of **Vision Language Models**, it parses unstructured interfaces into actionable steps.

## 🚀 Key Features

* **Set-of-Mark Grounding:** Uses a fine-tuned YOLOv8 model to detect UI elements (buttons, inputs, dropdowns) and overlays numbered markers on the screenshot before sending it to the VLM, ensuring highly accurate coordinate prediction.
* **Automated Accessibility Auditing:** Automatically evaluates web pages for WCAG 2.1 compliance (contrast ratios, minimum touch targets, missing labels) using computer vision.
* **NVIDIA NIM Integration:** First-class support for NVIDIA's lightning-fast Vision models (like Llama-3.2-90B-Vision).
* **Premium Dashboard:** A beautiful glassmorphism web UI for streaming the agent's step-by-step reasoning and viewing annotated screens live.

---

## ⚡ 1-Click Quickstart

1. **Clone & Setup:**
   ```bash
   pip install -r requirements.txt
   playwright install chromium
   ```

2. **Configure API Key:**
   Rename `.env.example` to `.env` and add your NVIDIA API Key (or OpenAI key).
   ```env
   NVIDIA_API_KEY=nvapi-your-key-here
   ```

3. **Launch the Dashboard:**
   Run the `start.bat` file (or `python main.py` directly).
   Open [http://localhost:8001](http://localhost:8001) in your browser!

---

## 🧠 How It Works

1. **Capture:** Playwright takes a full-page screenshot of the target application.
2. **Detect:** YOLOv8 (fine-tuned on the RICO dataset) identifies 12 distinct classes of UI elements.
3. **Annotate:** The system draws numbered Set-of-Mark (SoM) bounding boxes over the image.
4. **Reason:** The Vision LLM receives the annotated image and user prompt, and decides which element ID to interact with.
5. **Act:** The Playwright controller translates the element ID back to `(x, y)` coordinates and executes the click/type action.

---

## 📊 Training the Detector

To improve detection accuracy on your own UI components, you can fine-tune the YOLOv8 model:

```bash
# Generate synthetic dataset and train for 50 epochs
python -m detector.train --epochs 50
```

The best weights are automatically saved to `detector/checkpoints/guigazer_yolov8n.pt`.

## 🛡️ License
MIT License
