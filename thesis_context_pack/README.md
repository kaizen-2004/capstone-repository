# Thesis Context Pack (Chapters 1–5)

This folder contains the working Markdown thesis pack for your project, organized into **one Markdown file per section** wherever practical.

## Current status (updated 2026-04-18)

- The pack now covers **Chapters 1 to 5**.
- The wording has been synchronized to the **currently implemented system behavior** while keeping deployment language flexible for the final manuscript.
- The system scope remains **two monitored areas**:
  - **Living Room**
  - **Door Entrance Area**
- The implementation reflected in this pack includes:
  - local dashboard, logging, and alert management
  - HTTP sensor-event ingestion through `POST /api/sensors/event`
  - camera-based face recognition and fire-related visual confirmation
  - smoke-first fire detection logic
  - optional remote/mobile notification and access features
- **Raspberry Pi 2** is retained in the thesis narrative as an **optional deployment component for local edge hosting**.

## Folder structure

- Each chapter has its own folder.
- Inside each chapter folder are section `.md` files.
- Chapter 2 and Chapter 3 include subfolders for sub-sections (e.g., Related Literatures topics; Data Gathering Instruments; Statistical Treatment).
- Chapter 4 includes scaffolded result sections, Markdown tables, and sample narrative text.
- Chapter 5 includes thesis-ready summary, conclusions, and recommendations drafts.

## How to use in new AI sessions

Upload the whole folder (or the `.zip` version) and tell the AI to use it as context.  
If you only need a specific part, upload the relevant chapter folder or section file.

> Note: Diagram-heavy sections use Markdown-friendly text layouts and ASCII illustrations so the pack remains portable and easy to revise.



---

See `REVISION_NOTES.md` for the summarized thesis-pack alignment notes.
