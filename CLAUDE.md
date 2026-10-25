# CLAUDE.md

## Purpose

Personal study and portfolio repository for the Cisco CCNA 200-301 certification.
It holds theory notes, hands-on labs, and projects that demonstrate networking skills to employers.

## Tech Stack

Markdown documentation, Cisco Packet Tracer / GNS3 / CML topology files, Graphviz (`.dot`) diagrams,
and Python for automation labs.

## Structure

- `notes/00-base-knowledge/` — prerequisite theory (OSI/TCP-IP layers) that every domain relies on
- `notes/NN-domain/` — theory, one folder per CCNA exam domain; numbered topic files
- `notes/**/quizzes/` — self-contained HTML/JS multiple-choice quizzes, one per note, linked after each section
- `labs/NNN-name/` — hands-on labs, always created by copying `labs/_template/`
- `projects/` — larger end-to-end builds
- `cheatsheets/` — quick references
- `assets/diagrams/` — shared images
- `connection-map/` — Graphviz maps of how networks connect
- `first-steps/` — private home-network diagnostics (gitignored, never publish)

## Conventions

- All documentation is written in English
- When a lab or note is added, update the index table in its parent README and the progress in `README.md` / `ROADMAP.md`
- Never commit real public IPs, passwords, MAC addresses, or ISP credentials — sanitize configs first
