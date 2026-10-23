# PropMadeEasy

**Real Estate Intelligence & Statutory Delivery Platform**

PropMadeEasy is an enterprise real estate delivery platform designed for both homebuyers and real estate developers. It bridges the gap between homebuyer journeys and developer statutory compliance under RERA regulations.

---

## 🌟 Key Features

### 🏢 Developer Mode (Command Desk)
- **9-Stage Statutory Developer Journey**:
  1. Land & rights (Title, JDA & NALA)
  2. Approvals (HMDA, Fire, EIA)
  3. RERA Registration (Escrow & QPR Form 1-3)
  4. Funding (Bank APF & Capital)
  5. Selling & booking (Portfolio pipeline, SLA & unit allocations)
  6. Build & collect (Gantt, Escrow milestone certificates & labor tracking)
  7. Completion & OC (Joint inspection, Fire & CEIG NOCs)
  8. Handover & deed (SRO slot booking & deed registration)
  9. After handover (RWA corpus transfer & 5-year defect liability warranty)
- **Interactive Sales Pipeline Kanban Board**:
  - Live drag-and-drop lead stage management (New Inbound, Qualifying, Price Sent, Visit Booked, Token Advance / Booking).
  - Search, quick temperature filters (Hot, Warm, Needs Person), and direct WhatsApp engagement.
- **Enterprise Project Portfolio Table**:
  - Active development overview with TG-RERA numbers, stage lozenges, and inventory sold metrics.
  - Drill-down into individual project records without cluttering the global pipeline.
- **Human-in-the-Loop SLA Guard**:
  - Halts and escalates unauthorized pricing discounts or contract date shifts to designated executive approvers.

### 🏡 Homebuyer Mode (Lifecycle Portal)
- **8-Stage Buyer Journey**:
  - Stage 1: Need & research (RERA verification & builder trust proof)
  - Stage 2: Shortlist & visit (3D Architectural plan, morning/sunset/night balcony lake views, double-height living room renders)
  - Stage 3: Decide & book (Home Customizer Studio with live unit price delta calculation)
  - Stage 4: Loan & paperwork (Bank APF status & document vault)
  - Stage 5: Pay in stages (70% RERA escrow matching schedule)
  - Stage 6: Wait & track (Construction CCTV & tower milestone progress)
  - Stage 7: Possession (4-step onboarding checklist & SRO conveyance)
  - Stage 8: Live & fix defects (5-year statutory defect care ticketing)

---

## 🏗️ Architecture

```
Tilda/
├── agents/             # Autonomous agent modules (orchestrator, sales_closer, money_desk, site_watcher)
├── api/                # FastAPI application & endpoints
│   ├── server.py       # API server routing
│   └── static/         # Frontend web application (index.html, styles, JS, photographic renders)
├── config/             # Facts sheets, RERA rules, inventory pricing data
├── connectors/         # WhatsApp and third-party CRM connectors
├── core/               # Facts engine, validator, audit logger, models
├── n8n/                # n8n workflow integration & automation blueprints
├── simulation/         # Automated buyer journey simulations
└── tests/              # Test suite
```

---

## 🚀 Getting Started

### 1. Prerequisites
- Python 3.10+
- pip / virtualenv

### 2. Setup
```bash
# Clone the repository
git clone https://github.com/bishwajeet0206pal/PropMadeEasy.git
cd PropMadeEasy

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Run the Server
```bash
uvicorn api.server:app --reload --port 8000
```
Open [http://localhost:8000](http://localhost:8000) in your browser.

---

## 📜 License
Proprietary & Confidential - Built for modern real estate operations.
