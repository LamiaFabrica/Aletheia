# Medusa - AI-Powered Security Analysis Tool

---
## Session Log (2024-08-05)

**Current State:**
- Crawler (`collect_training_data.py`) now respects robots.txt, implements politeness delay, and uses a configurable user-agent string.
- Crawler outputs to JSON and skips URLs disallowed by robots.txt, logging these events.
- Crawler settings are user-configurable via the web UI and persist in `config.json`.
- Import script (`import_kali_knowledge.py`) continues to load data into the knowledge base.
- Knowledge base UI will display crawled tool data after import.

**Recent Progress:**
- Added robots.txt parsing and politeness delay to crawler.
- Added configurable user-agent to crawler requests.
- Added a dedicated crawler settings section to the UI, with backend API and config integration.
- Planning and design for a card-based, modular crawler dashboard and settings page, following a CPanel-style UX.
- Favicon and 404 error handling improved for a cleaner dev experience.

**Next Steps / Uncompleted Tasks:**
- [ ] **Phase 1: Crawler Dashboard Core**
    - [ ] Add prominent statistics/status card (system status, current/last crawl stats, historical summary)
    - [ ] Add operational controls (Start, Stop, Pause, Resume, Restart)
    - [ ] Add real-time activity log card with log level filtering
    - [ ] (Optional) Add queue overview card
    - [ ] Add error summary card (with actionable context and log links)
- [ ] **Phase 2: Crawler Settings Page (Iterative Rollout)**
    - [ ] Implement core settings first (user-agent, delay, scope/depth, basic filters)
    - [ ] Progressive rollout of advanced settings (per-domain politeness, proxy, resource allocation, advanced GIGO, scheduling, etc.)
    - [ ] For each setting, provide immediate feedback if applied on-the-fly, or clearly indicate if a restart is required ("Save and Restart Crawler" option)
- [ ] **Phase 3: Source & Campaign Management**
    - [ ] Card-based source management (add/edit/remove/enable/disable, per-source overrides)
    - [ ] Crawl campaign definition and management
- [ ] **Phase 4: Crawl Job History & Reporting**
    - [ ] List and detail view for all crawl jobs
    - [ ] Force re-crawl option
- [ ] **Phase 5: Knowledge Base Interaction**
    - [ ] Staging area for operator review of new data (bulk actions, diffs, easy tag/metadata editing)
    - [ ] Manual KB refresh controls
- [ ] **Phase 6: AI & Learning Integration**
    - [ ] Crawler suggestion review UI
    - [ ] Relevance feedback interface
- [ ] **Future Enhancement:**
    - [ ] Visualize crawler impact on the Knowledge Base (e.g., new items, trends, types of knowledge added)
- [ ] Continue regular README/session log updates for resilience and recovery

**Design & Implementation Principles:**
- **Iterative rollout:** Prioritize core settings and features for early usability, add advanced options incrementally.
- **On-the-fly feedback:** UI should confirm which settings are applied immediately and which require a restart, with clear messaging and options.
- **Operator roles & permissions:** Enforce operator-only controls for critical actions/settings; stats/logs can be more widely visible.
- **Actionable error reporting:** Error cards and logs should provide context, possible causes, and direct links to full logs or documentation.
- **Efficient staging workflow:** Staging area supports bulk actions, diffs, and easy metadata/tag editing before KB import.
- **Visual feedback:** Show the impact of crawler activity on the KB in dashboard/visualization sections.
- **Card-based, modular interface:** All major sections (status, controls, settings, logs, queue, errors, etc.) are presented as cards for clarity and consistency.
- **Real-time, actionable feedback:** Key stats, logs, and controls update live or on-demand.
- **Separation of concerns:** Dashboard for live/active operations, dedicated settings/configuration page, and clear job/source/campaign management.

---

Medusa is an intelligent security analysis system with a modern web dashboard, AI core, and PostgreSQL backend. It combines web crawling, machine learning, and natural language processing to provide comprehensive security insights and operator control.

## Features

- **Web Dashboard (Flask + SocketIO)**: Real-time, responsive dashboard for monitoring, control, and configuration
- **Web Documentation Crawler**: Automatically collects and learns from security documentation
- **Natural Language Interface**: Interact with the tool using plain English
- **AI-Powered Analysis**: Uses machine learning for risk assessment and anomaly detection
- **Knowledge Base**: Builds and maintains a security knowledge database
- **Real-Time Resource Monitoring**: Live CPU, memory, GPU, and per-process stats
- **Secure PostgreSQL Backend**: All sensitive data is encrypted (AES-256/Fernet)
- **Persistent Sessions**: Fixed Flask secret key ensures stable logins and dashboard operation
- **Operator Controls**: Start/Stop/Restart backend, manage AI models, and configure system settings
- **Extensible Architecture**: Designed for long-term growth, new features, and advanced AI/ML integration

## Development Features

### Enhanced Logging System
Medusa includes a comprehensive logging system for development and debugging:

- **Log Files**:
  - `medusa_verbose.log`: General application logs
  - `medusa_error.log`: Detailed error logs with stack traces
  - `medusa_performance.log`: Performance metrics
  - `medusa_page_tracking.log`: Page load tracking

- **Log Analysis**:
  ```bash
  python logs/view_logs.py
  ```
  This script provides:
  - Error summaries and patterns
  - Performance bottlenecks
  - Page load statistics
  - Recommendations for improvements

- **Log Management**:
  - Automatic log rotation (10MB files, 5 backups)
  - Midnight reset capability
  - Clear logs function
  - API endpoints for log access

### Environment Variables
```bash
# Enable/disable verbose logging
set MEDUSA_VERBOSE_LOGGING=1  # Windows
export MEDUSA_VERBOSE_LOGGING=1  # Linux/Mac

# Enable/disable error logging
set MEDUSA_ERROR_LOGGING=1  # Windows
export MEDUSA_ERROR_LOGGING=1  # Linux/Mac
```

### API Endpoints
- `GET /api/system/logs`: View recent logs (admin only)
- `POST /api/system/logs/clear`: Clear all logs (admin only)

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/medusa.git
cd medusa
```

2. Create a virtual environment (recommended):
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. (Optional) Set environment variables for production:
- `MEDUSA_SECRET_KEY`: Flask session key (default is set in code for dev)
- `MEDUSA_AES_KEY`: Encryption key for sensitive data

## Usage

### Web Dashboard

Start the web server:
```bash
python run.py
```
- The dashboard will open automatically at [http://localhost:5000](http://localhost:5000)
- Log in with your credentials (default admin: `Roylepython`)
- All dashboard features are available from a single browser tab

#### Dashboard Features
- **System Status**: See current backend state and operator controls
- **System Resources**: Live CPU, memory, GPU, and per-core stats
- **Learning Progress**: Track AI training sessions and model accuracy
- **Knowledge Base**: View and manage security knowledge
- **Processing Queue**: Monitor active and queued tasks
- **Configuration**: Set database, security, and AI model settings
- **Ollama Model Integration**: Select and manage LLMs for Medusa

### Interactive CLI (Legacy)

Start the interactive interface:
```bash
python src/interface.py --interactive
```

Example commands:
```
Medusa> learn from kali docs
Medusa> what do you know?
Medusa> check my scan results.xml
Medusa> train the system
```

### Command Line Mode

Run single commands:
```bash
python src/interface.py crawl kali docs
python src/interface.py analyze scan_results.xml
python src/interface.py train models
```

## Security & Session Management
- **Persistent Sessions**: The Flask `secret_key` is now fixed for reliable logins and session persistence
- **Encrypted Data**: All sensitive settings and results are encrypted with Fernet (AES-256)
- **Operator-Only Controls**: Only authorized users can start/stop/restart the backend

## Project Structure

```
medusa/
├── src/
│   ├── web_server.py      # Flask web server & dashboard
│   ├── interface.py       # User interface (CLI)
│   ├── nmap_analyzer.py   # Nmap analysis
│   ├── ai_models.py       # AI models
│   └── database.py        # Database management
├── templates/             # Jinja2 HTML templates for dashboard
├── static/                # Static files (JS, CSS)
├── scripts/
│   └── collect_training_data.py  # Web crawler
├── training_data/         # Collected knowledge
└── requirements.txt       # Dependencies
```

## Long-Term Vision & Extensibility
Medusa is designed as a long-term, extensible platform for security intelligence, AI/ML research, and operator-driven control. The architecture supports:
- Modular AI model integration (Ollama, LLMs, custom models)
- Real-time system monitoring and control
- Secure, encrypted data storage
- Future features: self-taught learning, advanced visualization, and more

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Seeding the Vulnerabilities Table with CVE Data

To seed the vulnerabilities table with the full CVE dataset and assign a unique MDE_ identifier to each entry:

1. Place your `cvelistV5-main.zip` file in the project root.
2. Run the seeding script:
   ```bash
   python medusa/scripts/seed_cve.py
   ```

- Each vulnerability will be assigned a unique 7-character identifier prefixed with `MDE_` (e.g., `MDE_ABC1234`) in the `mde_id` column.
- The script will automatically add the `mde_id` column to the `vulnerabilities` table if it does not exist.
- All data is encrypted at rest using AES-256 (Fernet) as per project policy.

This process ensures the AI has a comprehensive, uniquely indexed vulnerability database to learn from and support advanced reporting and wargaming features. 

## Session Log (2024-08-05, continued)

### Major UI/UX Overhaul ("Purple Tech" Mission Control)
- Sidebar refactored for a vertical, left-aligned layout with modern icons and text, purple accent, and Medusa logo (static/images/logo.png) at the top.
- Modular, card-based dashboard layout with consistent padding, border radius, and subtle depth (box-shadow, gradients).
- All cards and controls themed for dark mode, with purple as the primary accent and cyan/yellow/red for status highlights.
- Micro-animations and transitions for sidebar, cards, and buttons for a modern, "tech enthusiast" feel.
- Typography updated to modern sans-serif (Inter, Segoe UI, Roboto) and monospaced font for logs/IDs.

### Crawler Dashboard Core
- Crawler Status Card: Real-time state, key metrics, and visual indicators (icons, color, subtle glow).
- Operator Controls: Color-coded, animated buttons for Start (purple), Pause (yellow), Resume (cyan), Stop (red), Restart (gray), with modern icons and immediate feedback.
- All controls and status card fully wired to backend via SocketIO and REST, with real-time updates and state sync.
- Activity Log: Enhanced with filter/search bar, severity/event type/job_id filters, color-coding, and real-time event streaming from backend.

### Backend & Frontend Integration
- SocketIO event contract defined and implemented for log events and status updates.
- log_event helper function added to backend for structured, consistent event emission (event_type, severity, message, job_id, etc.).
- Activity Log now receives and displays all major crawler actions and errors in real time.
- In-memory activity_log capped for memory safety.
- Crawler settings persist in config.json; backend endpoints for settings management.

### File Changes
- `medusa/src/templates/base.html`: Sidebar, card, and theme overhaul; logo integration; micro-animations.
- `medusa/src/templates/crawler.html`: Status card and operator controls restyled and fully integrated; Activity Log UI enhanced.
- `medusa/src/static/images/logo.png`: Medusa logo added for sidebar branding.
- `medusa/src/web_server.py`: log_event helper, SocketIO event emission, real-time backend integration, capped activity_log, settings persistence.
- (Other files: minor updates for theme, icons, and config as needed.)

### Database/Config Changes
- Crawler settings (user-agent, politeness delay, etc.) now persist in config.json.
- No destructive changes to the vulnerabilities table; all data integrity maintained.

### Next Steps
- Finalize full real-time integration for operator controls and status card.
- Polish micro-UX for smooth, accessible, and engaging experience.
- Implement Crawler Settings UI (grouped, interactive, with tooltips and feedback).
- Build out Active Crawls List (real-time, actionable, visually consistent). 