# Networking Prep — CCNA 200-301

My path to the Cisco CCNA certification: study notes, hands-on labs, and real network builds.

## About

This repository documents everything I learn about networking, from fundamentals to automation.
Theory lives in `notes/`; proof of practical skills lives in `labs/` and `projects/`.

## Progress

| Domain | Exam weight | Status |
|--------|-------------|--------|
| 0. Base Knowledge (OSI / TCP/IP layers) | — | ✅ Done |
| 1. Network Fundamentals | 20% | 🚧 In progress |
| 2. Network Access | 20% | ⬜ Not started |
| 3. IP Connectivity | 25% | ⬜ Not started |
| 4. IP Services | 10% | ⬜ Not started |
| 5. Security Fundamentals | 15% | ⬜ Not started |
| 6. Automation and Programmability | 10% | ⬜ Not started |

Status legend: ⬜ Not started · 🚧 In progress · ✅ Done

Detailed checklist: [ROADMAP.md](ROADMAP.md)

## Featured Labs

| # | Lab | Topics |
|---|-----|--------|
| — | _Coming soon_ | — |

## Repository Structure

```
notes/          Theory, one folder per CCNA exam domain
labs/           Hands-on labs (start from labs/_template)
projects/       Larger end-to-end network builds and automation scripts
cheatsheets/    Quick references: IOS commands, subnetting, ports
assets/         Shared diagrams and images
connection-map/ Visual maps of how networks connect (Graphviz)
```

## Prerequisites

- [Cisco Packet Tracer](https://www.netacad.com/) (free with a Networking Academy account)
- GNS3 or Cisco Modeling Labs (CML) for advanced labs
- [Wireshark](https://www.wireshark.org/)
- Python 3 for the automation labs (Netmiko, Requests)

## Usage

- Study: start with `notes/00-base-knowledge/`, then read the notes per domain in `notes/`
- Self-test: open the HTML quiz linked after each section of a note in a browser
- Practice: copy `labs/_template/` to `labs/NNN-short-name/` and fill it in
- Track progress: tick items in [ROADMAP.md](ROADMAP.md) and update the table above
