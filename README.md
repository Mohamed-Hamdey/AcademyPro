# Academy Membership & Attendance System

A local, offline-first membership management and QR-based attendance system for small sports academies. Built with Python, PySide6, and SQLite, it runs on a single Windows PC without requiring a server, internet connection, or cloud storage.

Originally developed for **AL-Abtal Kung Fu Academy**, the application is designed to be reusable across different sports academies.

![Version](https://img.shields.io/badge/version-1.0.0-blue)
![Platform](https://img.shields.io/badge/platform-Windows%2010%2B-lightgrey)
![Python](https://img.shields.io/badge/python-3.12-blue)
![Qt](https://img.shields.io/badge/Qt-PySide6-green)
![Database](https://img.shields.io/badge/database-SQLite-blue)
![Deployment](https://img.shields.io/badge/deployment-offline--first-success)

## Features

### Receptionist

- **QR-code check-in:** Scan player QR codes using a webcam or find players manually by name or ID.
- **Multi-activity enrollment:** Enroll a player in multiple sports or training activities.
- **Session-based subscriptions:** Manage subscriptions with individual training schedules.
- **Instant check-in feedback:** Display player information and attendance results immediately.
- **Live attendance monitoring:** View today's check-ins with automatic refresh, filtering, and undo functionality.

### Manager

- **Dashboard and analytics:** View daily and monthly statistics, revenue, expenses, attendance KPIs, charts, financial reconciliation, and a rolling seven-day summary.
- **Player management:** Maintain player profiles, subscriptions, attendance history, notes, and photos.
- **Activity management:** Manage academy activities, activity-specific training days, and soft deletion.
- **User management:** Manage manager and receptionist accounts with role-based permissions.
- **Expense tracking:** Record categorized expenses and review monthly breakdowns.
- **Audit logging:** Track administrative actions, including who performed them and when.
- **Reports and printing:** Export daily and monthly reports to PDF and print them.
- **Backup and restore:** Create and restore backups through the application menu.

### Shared Features

- **Arabic and English:** Switch languages at runtime, including Arabic right-to-left (RTL) support.
- **Light and dark themes:** Change the interface theme at runtime.
- **Local data storage:** Store operational data on the Windows PC using SQLite.
- **Offline-first operation:** Designed to operate without cloud services or an internet connection.
- **Machine-bound licensing:** Validate per-machine license keys using Ed25519 digital signatures.

## Technology Stack

| Component | Technology |
|---|---|
| Programming language | Python 3.12 |
| Desktop interface | PySide6 via QtPy |
| Database | SQLite |
| QR scanning and image processing | OpenCV, pyzbar |
| Cryptography and licensing | cryptography |
| Executable packaging | PyInstaller |
| Windows installer | Inno Setup 6 |

## Architecture

The application follows a layered architecture that separates data models, database operations, business logic, and the user interface.

```text
academy-system/
├── models/                  # Data models and dataclasses
├── repositories/            # Database access and SQL queries
├── services/                # Business logic and workflows
├── ui/
│   ├── design.py            # Colors, spacing, and typography
│   ├── theme.py             # Theme management and palettes
│   ├── i18n.py              # Translations and t("key") helper
│   ├── components.py        # Reusable UI components
│   ├── shell.py             # Top bar, sidebar, and workspace
│   ├── main_window.py       # Main window and role-based navigation
│   ├── screens/             # Application screens
│   └── dialogs/             # Dialog windows
├── migrations/              # Numbered database migrations
├── license/                 # Licensing tools and public key
├── paths.py                 # Application and data path resolution
├── app_state.py             # Current session and permissions
├── main.py                  # Application entry point
├── academy_system.spec      # PyInstaller configuration
├── installer.iss            # Inno Setup configuration
├── requirements.txt         # Python dependencies
└── README.md
```

### Architectural Principles

- **Models:** Represent application data using dataclasses.
- **Repositories:** Centralize database queries and SQL operations.
- **Services:** Encapsulate business rules and application workflows.
- **User interface:** Separates reusable components, screens, dialogs, themes, and localization.
- **Database migrations:** Apply numbered schema updates automatically at startup.
- **Application state:** Maintains the active session and permission information.
- **Path resolution:** Separates installed program files from writable user data.
- **Access control:** Provides role-based navigation and permission enforcement.

## Requirements

- Windows 10 or later.
- Python 3.12 for running from source.
- Dependencies listed in `requirements.txt`.
- A webcam for QR-code scanning; manual player lookup is available as an alternative.
- Inno Setup 6 to build the Windows installer.

## Installation and Development

### 1. Open the project directory

Open PowerShell and navigate to the project root:

```powershell
cd E:\Downloads\academy-system
```

### 2. Create and activate a virtual environment

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

If PowerShell blocks script execution, activate the environment using Command Prompt:

```bat
venv\Scripts\activate.bat
```

### 3. Install dependencies

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Run the application

```powershell
python main.py
```

## Building the Windows Application

The application uses a **one-folder PyInstaller build**, packaging the executable and its dependencies together.

### 1. Build with PyInstaller

Run this command from the project root:

```powershell
python -m PyInstaller --clean --noconfirm academy_system.spec
```

Expected output:

```text
dist/
└── AcademySystem/
    ├── AcademySystem.exe
    └── ...
```

### 2. Build the Windows installer

Install Inno Setup 6, then run:

```powershell
& "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe" installer.iss
```

Expected output:

```text
dist_installer/
└── AcademySystem_Setup.exe
```

The actual output locations depend on the paths configured in `academy_system.spec` and `installer.iss`.

## Data Storage

The application separates installed program files from writable user data.

| Data | Location |
|---|---|
| Installed application | `C:\Program Files\Academy System\` |
| Application data directory | `%LOCALAPPDATA%\AcademySystem\` |
| SQLite database | `%LOCALAPPDATA%\AcademySystem\academy.db` |
| Application logs | `%LOCALAPPDATA%\AcademySystem\logs\` |
| Backups | `%LOCALAPPDATA%\AcademySystem\backups\` |
| Generated QR codes | `%LOCALAPPDATA%\AcademySystem\assets\qr_codes\` |
| Player photos | `%LOCALAPPDATA%\AcademySystem\assets\photos\` |

The installed program directory is intended for application files, while the local application-data directory stores writable operational data.

### Data Persistence

User data is designed to survive application updates and uninstallation.

**Important:** Uninstalling the application does not necessarily remove its local data. Back up important records regularly and verify that backups can be restored successfully.

## Privacy and Security

The application is designed for local, offline-first operation.

- Operational records are stored in a local SQLite database.
- User authentication uses password hashing.
- Role-based permissions control access to management features.
- Administrative actions are recorded in the audit log.
- License keys use Ed25519 digital signatures.
- Backup and restore functionality supports recovery from data loss.

The application is designed not to depend on cloud storage or external services during normal operation. Actual security and privacy guarantees depend on the implementation, dependencies, operating-system configuration, and deployment environment.

Academy operators are responsible for securing the Windows account and PC, restricting access to player information, safeguarding backups, and complying with applicable data-protection requirements.

## Backup and Recovery

Regular backups help protect against accidental deletion, hardware failure, and database corruption.

Recommended practices:

- Create backups regularly.
- Keep at least one backup on a separate storage device.
- Protect backups because they may contain personal information.
- Test the restore process periodically.
- Close the application before performing manual file-level backups to reduce the risk of inconsistent database copies.

Use the application's backup and restore functionality whenever possible.

## Licensing

This is proprietary software distributed under a per-machine licensing model using Ed25519-signed license keys.

See `LICENSES.txt` for information about third-party components and their licenses.

## Project Status

- **Version:** 1.0.0
- **Status:** Shipped
- **Platform:** Windows 10 and later
- **Deployment:** Single-PC desktop application
- **Storage:** Local SQLite database

The application is designed for small sports academies that need membership management, QR-based attendance, subscription tracking, financial reporting, and administrative controls without maintaining server infrastructure.

---

Developed for **AL-Abtal Sports Academy**.