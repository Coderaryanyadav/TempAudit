# Deployment & Operations Guide

FinAuditPro is designed primarily as a **100% Offline-First Desktop / Local Workstation** software application for Chartered Accountants and audit teams. It can also be deployed via local Docker containers for firm internal servers.

---

## 1. Standalone Workstation Deployment (Recommended)

### macOS Setup
1. Clone the repository to the local workstation:
   ```bash
   git clone https://github.com/Coderaryanyadav/TempAudit.git
   cd TempAudit
   ```
2. Run installation script:
   ```bash
   ./initialize/setup_mac.sh
   ```
3. Launch daily audit operations:
   ```bash
   ./initialize/start_mac.sh
   ```

### Windows Setup
1. Clone the repository:
   ```cmd
   git clone https://github.com/Coderaryanyadav/TempAudit.git
   cd TempAudit
   ```
2. Run installation script:
   ```cmd
   initialize\setup_windows.bat
   ```
3. Launch daily audit operations:
   ```cmd
   initialize\start_windows.bat
   ```

---

## 2. Docker Containerized Deployment

FinAuditPro includes standard container definitions for isolated internal local deployment.

### Using Docker Compose
```bash
# Build and start container in detached mode
docker compose up --build -d

# Check container status
docker compose ps

# View application logs
docker compose logs -f

# Stop container
docker compose down
```

The containerized service exposes the application at `http://127.0.0.1:8000`.

---

## 3. Data Backup & Recovery Operations

All persistent application data resides in `backend/`:
- Database: `backend/finauditpro.db`
- Backups: `backend/backups/`
- Audit Evidence: `backend/uploaded_files/`

### Automated Backup Creation
Backups can be triggered directly through the UI (**Administration > Assistant Settings > Create Backup**) or programmatically using the backup service:
```python
from backend.app.services.backup_service import create_backup
backup_info = create_backup(user_id=1)
print(f"Created backup: {backup_info['filename']} with HMAC signature")
```

### Signature Verification on Restore
FinAuditPro enforces strict HMAC-SHA256 signature verification on all restored backups. If a backup file is modified externally or tampered with, the restore engine rejects it immediately to prevent corrupted ledger injection.
