# Smart E-Mobility Hub – MVP Starter

This is the initial project scaffold for the CO3001 Software Engineering final MVP.

## Agreed implementation approach

- Python 3.11
- Streamlit for the web UI and Python application runtime
- One application, organized into six SUB modules (modular monolith)
- Shared in-memory state for the local demonstration
- No database server, REST API, microservices, message broker, real IoT hardware, GPS integration or cloud deployment in this MVP

The assignment brief permits hard-coded data and does not require a backend database for the MVP demonstration.

## Important data limitation

`shared/state.py` stores demo data in one process-wide Python object. Browser sessions connected to the same app process share that data. Data is lost when the app process restarts, and multiple server workers would have separate copies. This is intentionally a lightweight demo-only approach, not production persistence.

`shared/auth.py` currently provides a temporary role selector for development. M2 is responsible for replacing it with the agreed Sign Up / Sign In / Sign Out demo flows.

## Run the demo on Windows PowerShell

Open PowerShell in the project directory. If the project already has a `.venv`
folder, run Streamlit through that environment's Python executable:

```powershell
Set-Location D:\MinhHuy\CNPM\smart-e-mobility-hub
.\.venv\Scripts\python.exe -m streamlit run app.py
```

This command does not require activating the virtual environment or adding the
`streamlit` command to the global PATH. In the current local setup, `.venv`
contains Python 3.10.11 and Streamlit 1.65.0. The project specification calls
for Python 3.11; use the setup below when creating a fresh team environment.

When Streamlit starts, choose **Operator** in the sidebar and open
**SUB-06 · What-if Simulation**. Select a scenario, Hub and time window, set
the assumptions, then capture the snapshot and run the simulation.

### Create a fresh Python 3.11 environment

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --no-cache-dir -r requirements.txt
python -m streamlit run app.py
```

Open the local URL printed by Streamlit in the terminal.

Keep `.venv` inside the project folder so the dependencies stay with the
checkout. If the project is on D:, this also keeps the installed packages off
the nearly full C: drive.

## SUB-06 What-if Simulation demo

Run the same application command above, choose the **Operator** demo role, then
open **SUB-06 · What-if Simulation** from the sidebar. The demo currently
supports three agreed scenarios:

- Metro Hub demand surge
- Hub near capacity or vehicle shortage
- Charging demand surge or charging point failure

The Operator selects a Hub and time window, confirms a copied network snapshot,
and runs the scenario. Demand values that are not part of the shared seed data
are entered as explicit scenario assumptions. Results compare before/after
metrics and offer suggestions; they never execute dispatch or change live
operational records. Two additional scenario choices from UC-15 remain to be
confirmed by the team before implementation.

## Initial demo data

- 5 Mobility Hubs
- 50 shared electric vehicles (10 per Hub)
- 100 private parking spaces (20 per Hub)
- 20 charging points (4 per Hub)

Names and sample resource states are illustrative seed data. Members may refine sample values, but must not change shared status names without team agreement.

## Project structure

```text
app.py
shared/
  auth.py       # temporary role selector; M2 replaces with Authentication UCs
  enums.py      # canonical shared status values
  state.py      # process-wide in-memory demo data
modules/
  sub01/        # M1 owns working initial implementation
  sub02/        # M2 implements UC-04 and UC-05
  sub03/        # M3 implements UC-06-01 to UC-07-02
  sub04/        # M4 implements UC-08 to UC-10
  sub05/        # M5 implements UC-11 to UC-14
  sub06/        # M6 implements UC-15 to UC-17
```

## Team rules

1. Each member edits their own `modules/subXX/` directory. Shared files are changed only after team agreement.
2. Only the owning SUB changes its records. Other SUBs call the owner's service function.
3. SUB-01 owns shared vehicle reservations; SUB-02 owns shared vehicle trip/lifecycle state.
4. SUB-03 owns parking and charging requests; SUB-04 owns charging schedules and resource allocations.
5. SUB-05 reads operational resource data and performs dispatch through owning SUB services.
6. SUB-06 runs on a copied snapshot and never changes live operational state.
7. Run the application after every integration change. Do not wait until the final day to merge.

## Current status

- Initial project structure: created
- Shared demo data: created
- Temporary role selector: created
- SUB-01 Hub discovery, vehicle search and reservation foundation: implemented
- SUB-02 through SUB-05: starter placeholders awaiting their owners
- SUB-06: three-scenario What-if Simulation demo implemented; additional UC-15 scenarios pending team confirmation
