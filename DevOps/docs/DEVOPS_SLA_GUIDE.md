# DevOps SLA Tasks 2026 — TempAudit / FinAuditPro

**Project:** TempAudit (FinAuditPro Audit Management Application)  
**Repository:** https://github.com/Coderaryanyadav/TempAudit  
**Practical scope:** Git operations, Jenkins CI, Selenium testing, Docker + database persistence, and Ansible provisioning.

> Replace the student/college fields in the final report. Add your own screenshots where noted. Do not claim a task is complete until its verification step succeeds.

## 1. Project summary and environment

TempAudit is a Python application with a FastAPI backend and an HTML/CSS/JavaScript frontend. The app serves its main page at `http://127.0.0.1:8000`; `/api/health` returns a small JSON health result. The authentication API is under `/api/auth/`. Its database module opens SQLite and creates/migrates application tables.

For the five practicals, use the following components:

| Task | Tool | Proof of completion |
|---|---|---|
| 1. Git push/pop | Git CLI or Git GUI | Commit pushed to GitHub; stash push/pop shown |
| 2. Jenkins on Windows | Jenkins LTS + supported Java | Successful Jenkins build log and TempAudit homepage |
| 3. Automated browser test | Python + Selenium + pytest | Test results with pass count and browser evidence |
| 4. Container image + DB | Docker Engine + Compose | Image, running container, homepage, SQLite-backed setup/login flow |
| 5. Software provisioning | Ansible on Linux/macOS control node | Successful play recap showing hosts/tasks changed or OK |

### Safe demonstration data

Use only synthetic company records and demo credentials. Do not use real audit-client financial data, firm secrets, or personal passwords in screenshots, Git commits, Docker images, or public repositories.

---

## Task 1 — Git operations: push, stash push, and stash pop

### Aim

To maintain project source code in GitHub and demonstrate version control operations, including pushing a commit and temporarily saving/restoring uncommitted changes with `git stash push` and `git stash pop`.

### Procedure

Open Terminal (macOS/Linux) or PowerShell/Git Bash (Windows):

```bash
git clone https://github.com/Coderaryanyadav/TempAudit.git
cd TempAudit
git status
git branch --show-current
git log -5 --oneline
```

Create a small documentation change specifically for the practical:

```bash
mkdir -p docs/devops-evidence
printf '# DevOps SLA 2026\n\nGit and release evidence for TempAudit.\n' > docs/devops-evidence/README.md
git add docs/devops-evidence/README.md
git commit -m "docs: add DevOps SLA practical evidence folder"
git push origin main
```

If your current working branch is not `main`, push your branch name instead of changing branches blindly:

```bash
git push -u origin "$(git branch --show-current)"
```

To demonstrate stash push/pop, edit a tracked file locally without committing it (use an innocuous documentation file):

```bash
printf '\nTemporary local note for stash demonstration.\n' >> docs/devops-evidence/README.md
git status
git stash push -m "SLA demonstration: temporary note"
git stash list
git status
git stash pop
git diff -- docs/devops-evidence/README.md
```

`git stash pop` restores the saved working changes and removes that stash entry if application succeeds. If Git reports a conflict, resolve it before proceeding. To clean up the temporary local note after capturing evidence, remove that one line and do not commit it.

If by “pop” the instructor means stack pop in the Git GUI rather than stash pop, ask them; in Git terminology the standard operation matching push/pop is `git stash push` / `git stash pop`.

### Verification

- GitHub repository shows the new documentation file and commit.
- `git stash list` shows the stash before pop.
- After successful pop, the change is back in the working tree and that stash entry is no longer listed.

### Screenshot evidence

- **T1-S1:** `git status` and branch name before the change.
- **T1-S2:** commit/push output and the commit visible on GitHub.
- **T1-S3:** `git stash push` + `git stash list`.
- **T1-S4:** `git stash pop`, `git diff`, and restored change.

---

## Task 2 — Install Jenkins on Windows and show the application homepage

### Aim

To configure a Jenkins job that checks out TempAudit and builds/tests it, then demonstrates the application homepage.

### Prerequisites

This task must be done on a Windows machine or Windows VM (Windows 10/11). Use the current Jenkins LTS Windows MSI and a supported Java runtime. Check Jenkins's official Windows installation guide before installing: https://www.jenkins.io/doc/book/installing/windows/ . Jenkins documentation lists Java 21 or later as a prerequisite for current installations.

### Install

1. Install a supported Java runtime (JDK 21 or later, following Jenkins requirements).
2. Download the Jenkins LTS Windows installer from the official Jenkins download page.
3. Run the MSI installer, select an available port (normally `8080`), and complete setup. Prefer a dedicated local service account over LocalSystem where practical.
4. Open `http://localhost:8080`.
5. Unlock Jenkins using the password in the `initialAdminPassword` file under the Jenkins home directory; follow the install wizard and create a unique administrator account.
6. Install suggested plugins. Ensure Git and Pipeline/Freestyle functionality are available.
7. Confirm the Jenkins Windows service is running in `services.msc`.

### Run a simple project job

1. In Jenkins, choose **New Item** → `TempAudit-SLA-Build` → **Freestyle project**.
2. In **Source Code Management**, select **Git** and enter `https://github.com/Coderaryanyadav/TempAudit.git`.
3. Under **Build Environment / Build Steps**, add **Execute Windows batch command**.
4. Use a Windows build step like below. This command verifies Python/dependencies and runs a safe smoke check. It does not automatically initialize a production database or create an admin.

```bat
@echo on
python --version
python -m venv venv
call venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
python -c "import fastapi, uvicorn, sqlite3; print('Dependencies import successfully')"
```

5. Click **Save** → **Build Now** → open build number → **Console Output**. If the environment blocks network access, dependency installation may fail; use an approved pre-cached wheelhouse or fix connectivity and rerun.
6. For the required homepage demonstration, start the app on the Windows workstation using a separate terminal after dependencies are installed:

```bat
call venv\Scripts\activate.bat
python run.py
```

Open `http://127.0.0.1:8000` and show TempAudit loading. Do not start two servers on port 8000 at the same time. Keep credentials out of Jenkins console logs.

**Optional improvement:** Add a second Jenkins build step with a short Python smoke script or run pytest after checking the test suite's own fixture/database expectations. Do not run the entire test suite inside a persistent demo database without reviewing fixtures and reset behavior.

### Verification

- Jenkins service is running.
- The build appears as **Success** and its console shows dependency verification completed.
- TempAudit homepage opens at `http://127.0.0.1:8000`.

### Screenshot evidence

- **T2-S1:** Jenkins service or installation success.
- **T2-S2:** Jenkins dashboard and the job.
- **T2-S3:** Successful console output.
- **T2-S4:** TempAudit homepage in browser, with URL bar visible.

---

## Task 3 — Test TempAudit using Selenium

### Aim

To automate browser smoke tests of the actual web application and check API readiness.

### Why Selenium

TempAudit is a browser-based web application, so Selenium WebDriver is appropriate. Appium is intended for mobile-native or mobile-focused automation; it is not necessary for this web project practical.

### Prepare environment

From the repository root:

**Windows PowerShell**

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -r tempaudit_devops_pack\selenium\requirements-test.txt
```

**macOS/Linux**

```bash
python3 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -r tempaudit_devops_pack/selenium/requirements-test.txt
```

Start the server in a separate terminal:

```bash
python run.py
```

In another terminal, run the supplied tests:

```bash
python -m pytest tempaudit_devops_pack/selenium/test_smoke.py -v
```

The smoke suite tests:

1. `/api/health` returns HTTP 200 and `status=healthy`.
2. The homepage renders non-empty content.
3. `/api/auth/setup-status` returns one of the expected installation states.

Selenium 4 uses Selenium Manager in common configurations to resolve browser drivers; install Chrome or Edge and allow driver downloads if needed. Official install: https://www.selenium.dev/documentation/webdriver/getting_started/install_library/ .

### Test actual authentication (manual + API)

For a fresh demo database, navigate to the homepage and use the first-run setup wizard to create a throwaway demo administrator. Then inspect the `/api/auth/login` request/response in browser developer tools or call the endpoint with synthetic demo credentials. Example API request (replace the username/password with the account you just created):

```bash
curl -i -X POST http://127.0.0.1:8000/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"YOUR_DEMO_USERNAME","password":"YOUR_DEMO_PASSWORD"}'
```

Expected: successful HTTP response and an access token for correct credentials. A deliberately incorrect password should produce an authentication failure. Avoid repeating failed-login tests too often because the app includes rate limiting. Never put the real demo password in a report or screenshot.

### Verification

- Homepage opens in Chrome.
- Pytest reports all included smoke tests passed.
- The API login can be demonstrated using a temporary account you created, with secrets masked in evidence.

### Screenshot evidence

- **T3-S1:** App running.
- **T3-S2:** Selenium browser window showing homepage.
- **T3-S3:** Terminal with pytest pass results.
- **T3-S4:** Successful login response or UI transition, with access token/password obscured.

---

## Task 4 — Build a Docker image and demonstrate database connectivity

### Aim

To build a Docker image for TempAudit, run it in a container, and demonstrate that the application's login/registration workflow stores data in the application's database.

### Application/database design

The supplied Dockerfile packages the FastAPI application. The Compose file attaches named volumes and sets `FINAUDIT_DB_PATH=/data/finauditpro.db`, so the SQLite database persists outside the container's writable layer. This is consistent with the existing code in `backend/app/database.py`. It does **not** introduce a MySQL service, because the application does not currently use a MySQL client.

### Set up the pack inside the repository

Copy the `tempaudit_devops_pack` directory into the root of the cloned repository, then run the commands below from the repository root. If you saved the pack elsewhere, copy the Docker files into a local `tempaudit_devops_pack/docker` folder or adjust `compose.yaml` build paths accordingly.

The Dockerfile copies only the required application directories (backend, frontend and run.py), not the entire repository. A Dockerfile-specific ignore file also excludes local environment files/database files from the build context. Create a local environment file:

```bash
cp tempaudit_devops_pack/docker/.env.example tempaudit_devops_pack/docker/.env
```

Replace `FINAUDIT_SECRET_KEY` in that `.env` file with a unique high-entropy random secret. For a throwaway local demo, generate a value with:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Do not commit `.env`. Confirm it is ignored by Git before adding files to a public repository.

Build and start:

```bash
docker compose -f tempaudit_devops_pack/docker/compose.yaml --env-file tempaudit_devops_pack/docker/.env build
docker compose -f tempaudit_devops_pack/docker/compose.yaml --env-file tempaudit_devops_pack/docker/.env up -d
docker image ls tempaudit-sla
docker ps
curl -i http://127.0.0.1:8000/api/health
```

Open `http://127.0.0.1:8000` in the browser. Complete the first-run setup with a temporary demo admin. The DB file is stored in the `tempaudit_data` named volume. To inspect running logs:

```bash
docker compose -f tempaudit_devops_pack/docker/compose.yaml --env-file tempaudit_devops_pack/docker/.env logs --tail=100 tempaudit
```

### Demonstrate database persistence

1. Before creating the demo admin, use `GET /api/auth/setup-status` and note `user_count: 0` / `state: UNINITIALIZED` if the volume is fresh.
2. Create the temporary administrator through the actual first-run setup UI.
3. Recheck `GET /api/auth/setup-status`; expected state should change and the user count should be greater than zero.
4. Restart the application container without deleting volumes:

```bash
docker compose -f tempaudit_devops_pack/docker/compose.yaml --env-file tempaudit_devops_pack/docker/.env restart tempaudit
```

5. Recheck `GET /api/auth/setup-status`. The user record and initialized state should remain, demonstrating persistence through the volume. You can also show that valid login works and invalid login is rejected.

Do not run `docker compose down -v` before the demo: this would delete the named volumes and the SQLite database. `docker compose down` stops/removes the container and network but preserves named volumes by default.

### If faculty specifically requires MySQL

The current repository uses SQLite. A MySQL-based demo would require a deliberate application migration/configuration change, not simply adding a MySQL container. Explain the existing SQLite implementation to the evaluator; use the phrase “database connectivity and persistence via SQLite” unless your assignment explicitly demands MySQL/PostgreSQL.

### Verification

- `docker image ls` shows `tempaudit-sla:2026`.
- `docker ps` shows the container running and port `8000` mapped.
- `/api/health` succeeds.
- Creating the administrator changes setup status, and the state remains after container restart.

### Screenshot evidence

- **T4-S1:** Docker image list.
- **T4-S2:** Running container and port mapping.
- **T4-S3:** Homepage inside the browser.
- **T4-S4:** Setup status before and after creating the demo admin.
- **T4-S5:** Successful login or persisted state after restarting container.

---

## Task 5 — Install required software using Ansible

### Aim

To automate preparation of a target machine with the software needed to run TempAudit.

### Important platform note

Ansible typically runs from a Linux/macOS control node, and its standard modules manage Linux hosts over SSH. For this practical, use your Mac/Linux environment as the control node and target a Linux VM (Ubuntu is a good lab choice). If you only have Windows, use WSL2 or a Linux VM to run Ansible. The supplied playbook installs Python 3, venv, pip, Git and curl on Ubuntu/Debian; creates a dedicated `tempaudit` user; clones/updates the repository; installs `requirements.txt` into an isolated virtual environment; installs a systemd service; and verifies `/api/health`.

Official install guidance: https://docs.ansible.com/ansible/latest/installation_guide/intro_installation.html .

### Install Ansible on a Mac control node

Use a dedicated Python environment or the system-recommended package manager. One option documented by Ansible is `pipx`:

```bash
brew install pipx
pipx ensurepath
pipx install --include-deps ansible
ansible --version
```

If `pipx` is not available on your host, follow the official Ansible install guide.

### Local rehearsal (safe)

From the pack directory, run the included playbook against the local machine only for a quick syntax/behavior check. Note: package installation uses `apt`, so the local target must be Debian-family Linux; do not run that playbook on macOS itself.

On an Ubuntu target where you have sudo access:

```bash
cd tempaudit_devops_pack/ansible
ansible-playbook -i inventory-local.ini tempaudit_setup.yml --ask-become-pass
```

### Remote Linux VM

Edit `inventory.ini` and add your VM IP and SSH username, for example:

```ini
[tempaudit_hosts]
192.168.56.10 ansible_user=ubuntu

[tempaudit_hosts:vars]
ansible_python_interpreter=/usr/bin/python3
```

Then verify connectivity and run the playbook:

```bash
ansible -i inventory.ini tempaudit_hosts -m ping
ansible-playbook -i inventory.ini tempaudit_setup.yml --ask-become-pass
```

Expected output ends with a recap like `ok=N changed=N failed=0`. The exact change count depends on whether packages and files already existed. The final URI task verifies HTTP 200. The playbook deploys and starts the application on the target. Its service binds to `127.0.0.1:8000` for a safer local demonstration.

### Verification

- `ansible --version` displays an installed version.
- `ansible ... -m ping` returns `pong` for the remote target.
- Play recap shows `failed=0`.
- On the Linux target, `python3 --version`, `git --version`, `systemctl status tempaudit --no-pager`, `ls -ld /opt/tempaudit`, and `curl http://127.0.0.1:8000/api/health` work.

### Screenshot evidence

- **T5-S1:** `ansible --version`.
- **T5-S2:** Ansible ping response.
- **T5-S3:** Playbook tasks executing.
- **T5-S4:** Final play recap with `failed=0` and target directory.

---

## Final screenshot checklist and report format

Create a folder `submission_screenshots/` and store named evidence files using the IDs above. Capture full application windows with enough context to show command output/URL and avoid cropping the verification details. For any credential/token, blur it before including the screenshot.

Recommended final report order:

1. Cover page: college, subject, name, roll number, academic year 2026.
2. Abstract/objective and TempAudit project overview.
3. Software/hardware requirements.
4. Task 1 through Task 5: Aim, tools, theory, procedure, commands/configuration, actual output, screenshots, result.
5. Combined conclusion and learning outcomes.
6. References: TempAudit GitHub repository; official Jenkins, Selenium, Docker and Ansible documentation.

### Suggested result wording (fill in after execution)

“Git operations, Jenkins build, Selenium tests, Docker image/container with SQLite persistence, and Ansible provisioning were demonstrated for TempAudit. Successful results are evidenced by the attached screenshots and command outputs. Any failed/incomplete step is explicitly recorded rather than marked as successful.”

## Official references

- TempAudit repository: https://github.com/Coderaryanyadav/TempAudit
- Jenkins on Windows: https://www.jenkins.io/doc/book/installing/windows/
- Selenium library installation: https://www.selenium.dev/documentation/webdriver/getting_started/install_library/
- Docker Compose: https://docs.docker.com/compose/
- Ansible installation: https://docs.ansible.com/ansible/latest/installation_guide/intro_installation.html
