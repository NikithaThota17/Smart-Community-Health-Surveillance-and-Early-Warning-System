# Smart Community Health Monitoring & Early Warning System

A Django-based major project for community-level public health surveillance.  
The platform collects citizen and health-worker reports, computes area risk (Low/Medium/High), triggers alerts, and supports coordinated admin-to-field response.

## Project Objective
Build an early warning and response workflow at district/mandal/village level by combining:
- Structured complaint reporting
- Risk scoring
- Alert generation
- Admin action tracking
- Health worker follow-up

## Core Features
- Role-based login: Citizen, Health Worker, Admin
- Citizen symptom/environment complaint submission
- Health worker field reporting and visit completion
- Location hierarchy support (State -> District -> Mandal -> Village)
- Risk analysis engine (logistic-style probability scoring)
- Medium/High risk alert generation
- Admin action flow (assignment and advisory workflows)
- Notification system for citizen, worker, and admin updates
- Dashboard views and exports

## Tech Stack
- Python 3.x
- Django 5.x
- SQLite (default) / PostgreSQL (deployment option)
- HTML/CSS/JavaScript, Chart.js
- NumPy
- AWS-ready deployment workflow

## Project Structure
- `accounts/` - authentication, roles, profile
- `locations/` - geographic hierarchy models and import commands
- `complaints/` - citizen/worker reporting workflows
- `analytics/` - risk logic and analytics
- `notifications/` - alert and notification flows
- `dashboard/` - role-specific dashboards

## Local Setup (Windows PowerShell)
```powershell
cd Smart-Health-Surveillance-and-Early-Warning-System
python -m venv myvenv
.\myvenv\Scripts\Activate.ps1
pip install -r req.txt
python manage.py migrate
python manage.py runserver
```

Open: `http://127.0.0.1:8000/`

## Location Data
Location data is imported via Django management commands (not auto-loaded at startup).

Example:
```powershell
python manage.py import_location_master locations/location_master_sample.csv
```

For AP LGD import, use the command implemented in:
`locations/management/commands/import_ap_lgd_xls.py`

## Workflow Summary
Citizen report -> Validation -> Risk calculation -> Alert (if Medium/High) ->  
Admin action -> Worker assignment/follow-up -> Visit completion -> Updated status and notifications.

## Deployment Notes
- Set production configuration: `DEBUG=False`, `ALLOWED_HOSTS`, environment variables
- Run migrations on server
- Configure static/media handling
- Use PostgreSQL in production (recommended)

## Future Scope
- SMS/WhatsApp alert integration
- GIS heatmap visualization
- SLA-based escalation tracking
- Advanced predictive modeling with larger datasets.
