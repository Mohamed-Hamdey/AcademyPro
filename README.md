# AcademyPro — Sports Academy Management System

**AcademyPro** is a local, offline-first membership management and QR-based attendance application built for small sports academies. Developed with Python, PySide6, and SQLite, it runs on a single Windows PC without requiring a server, internet connection, or cloud storage.

Originally developed for **AL-Abtal Kung Fu Academy**, AcademyPro is designed to be reusable across different sports academies and training centers.

![Version](https://img.shields.io/badge/version-4.0.0-blue)
![Platform](https://img.shields.io/badge/platform-Windows%2010%2B-lightgrey)
![Python](https://img.shields.io/badge/python-3.12-blue)
![Qt](https://img.shields.io/badge/Qt-PySide6-green)
![Database](https://img.shields.io/badge/database-SQLite-blue)
![Deployment](https://img.shields.io/badge/deployment-offline--first-success)

## Table of Contents

- [Features](#features)
- [Technology Stack](#technology-stack)
- [Architecture](#architecture)
- [System Requirements](#system-requirements)
- [Installation and Development](#installation-and-development)
- [Building the Windows Application](#building-the-windows-application)
- [Data Storage](#data-storage)
- [Privacy and Security](#privacy-and-security)
- [Backup and Recovery](#backup-and-recovery)
- [Licensing](#licensing)
- [Project Status](#project-status)

## Features

### Receptionist

- **QR-code check-in:** Scan player QR codes using a webcam or locate players manually by name or ID.
- **Multi-activity enrollment:** Enroll players in multiple sports or training activities.
- **Session-based subscriptions:** Manage subscriptions with individual training schedules.
- **Instant check-in feedback:** Display player information and attendance results immediately.
- **Live attendance monitoring:** View, filter, and refresh today's attendance records, with support for undoing check-ins.

### Manager

- **Dashboard and analytics:** View daily and monthly statistics, revenue, expenses, attendance KPIs, charts, financial reconciliation, and a rolling seven-day summary.
- **Player management:** Maintain player profiles, subscriptions, attendance history, notes, and photos.
- **Belt and weight tracking:** Record belt ranks and weight measurements over time, view historical trends, and configure belt requirements by activity.
- **Session time preferences:** Assign preferred training times using presets or custom values, and filter the player list by session time.
- **Activity management:** Manage academy activities, configure activity-specific training days, and soft-delete activities.
- **User management:** Manage manager and receptionist accounts with role-based permissions.
- **Expense tracking:** Record categorized expenses and review monthly breakdowns.
- **Audit logging:** Track administrative actions, including the responsible user and timestamp.
- **Reports and printing:** Generate, export, and print daily and monthly PDF reports.
- **Backup and restore:** Create and restore backups through the application menu.

### Shared Features

- **Arabic and English:** Switch languages at runtime, including right-to-left (RTL) support for Arabic.
- **Light and dark themes:** Switch interface themes at runtime.
- **Local data storage:** Store operational data in a local SQLite database on the Windows PC.
- **Offline-first operation:** Operate without cloud services or an internet connection during normal use.
- **Machine-bound licensing:** Validate per-machine license keys using Ed25519 digital signatures.

## Technology Stack

| Component | Technology |
|---|---|
| Programming language | Python 3.12 |
| Desktop UI | PySide6 via QtPy |
| Database | SQLite |
| QR scanning and image processing | OpenCV, pyzbar |
| Cryptography and licensing | `cryptography` |
| Executable packaging | PyInstaller |
| Windows installer | Inno Setup 6 |

## Architecture

AcademyPro follows a layered architecture that separates data models, database access, business logic, and the user interface.

### Project Structure

```text
academy-system/
├── models/                    # Data models and dataclasses
├── repositories/              # Database access and SQL queries
├── services/                  # Business logic and workflows
├── ui/
│   ├── design.py              # Colors, spacing, and typography
│   ├── theme.py               # Theme management and palettes
│   ├── i18n.py                # Translations and t("key") helper
│   ├── components.py          # Reusable UI components
│   ├── shell.py               # Top bar, sidebar, and workspace
│   ├── main_window.py         # Main window and role-based navigation
│   ├── screens/               # Application screens
│   └── dialogs/               # Dialog windows
├── migrations/                # Numbered database migrations
├── license/                   # Licensing tools and public key
├── paths.py                   # Application and data path resolution
├── app_state.py               # Active session and permissions
├── main.py                    # Application entry point
├── academy_system.spec        # PyInstaller configuration
├── installer.iss              # Inno Setup configuration
├── requirements.txt           # Python dependencies
└── README.md
```

### Architectural Principles

- **Models:** Represent application data using dataclasses.
- **Repositories:** Centralize database access and SQL queries.
- **Services:** Encapsulate business rules and application workflows.
- **User interface:** Separate reusable components, screens, dialogs, themes, and localization.
- **Database migrations:** Apply numbered schema updates automatically at startup.
- **Application state:** Maintain the active session and permission information.
- **Path resolution:** Separate installed application files from writable user data.
- **Access control:** Support role-based navigation and permission enforcement.

## System Requirements

### Runtime

- Windows 10 or later.
- The packaged application and its dependencies, or Python 3.12 and the required dependencies when running from source.
- A webcam for QR-code scanning. Manual player lookup is available as an alternative.

### Development and Packaging

- Python 3.12.
- Dependencies listed in `requirements.txt`.
- Inno Setup 6 to build the Windows installer.
- The project source files, including `academy_system.spec` and `installer.iss`.

## Installation and Development

The following instructions assume that the project is located at `E:\Downloads\academy-system`. Replace this path with your actual project directory if necessary.

### 1. Open the Project Directory

Open PowerShell and navigate to the project root:

```powershell
cd E:\Downloads\academy-system
```

### 2. Create a Virtual Environment

```powershell
python -m venv venv
```

Activate the virtual environment:

```powershell
.\venv\Scripts\Activate.ps1
```

If PowerShell blocks script execution, activate the environment using Command Prompt instead:

```bat
venv\Scripts\activate.bat
```

### 3. Install Dependencies

Upgrade `pip` and install the project dependencies:

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 4. Run the Application

Start AcademyPro from the project root:

```powershell
python main.py
```

## Building the Windows Application

AcademyPro uses a one-folder PyInstaller build, which packages the executable and its dependencies into a directory.

### 1. Build with PyInstaller

From the project root, run:

```powershell
python -m PyInstaller --clean --noconfirm academy_system.spec
```

The expected output structure is:

```text
dist/
└── AcademyPro/
    ├── AcademyPro.exe
    └── ...
```

The actual output directory and executable name depend on the settings in `academy_system.spec`.

### 2. Build the Windows Installer

Install Inno Setup 6 and ensure that `installer.iss` references the correct application build directory.

If Inno Setup is installed in the default per-user location, run:

```powershell
& "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe" installer.iss
```

If `ISCC.exe` is installed elsewhere, update the command to match its actual location.

The expected installer output is:

```text
dist_installer/
└── AcademyPro_Setup_v4.0.0.exe
```

The actual output location and filename depend on the settings in `installer.iss`.

**Before distributing a release**, test the packaged application and installer on a clean Windows environment. Verify that startup, database creation, QR scanning, file access, backup and restore, and any required runtime dependencies work as expected.

## Data Storage

AcademyPro separates installed program files from writable application data.

| Data | Default location |
|---|---|
| Installed application | `C:\Program Files\AcademyPro\` |
| Application data directory | `%LOCALAPPDATA%\AcademySystem\` |
| SQLite database | `%LOCALAPPDATA%\AcademySystem\academy.db` |
| Application logs | `%LOCALAPPDATA%\AcademySystem\logs\` |
| Backups | `%LOCALAPPDATA%\AcademySystem\backups\` |
| Generated QR codes | `%LOCALAPPDATA%\AcademySystem\assets\qr_codes\` |
| Player photos | `%LOCALAPPDATA%\AcademySystem\assets\photos\` |

These paths describe the intended default layout. Actual locations depend on the application's path-resolution logic and configuration.

The installation directory is intended for application files, while the local application-data directory stores writable operational data.

### Data Persistence

Player records, attendance history, subscriptions, and other operational data are intended to survive application updates and uninstallation.

**Important:** Uninstalling AcademyPro does not necessarily remove its local data. Before uninstalling, reinstalling, or moving the application to another PC, create a backup and verify that it can be restored successfully.

## Privacy and Security

AcademyPro is designed for local, offline-first operation.

Its intended security features include:

- Local storage of operational records in SQLite.
- Password hashing for user authentication.
- Role-based permissions for management features.
- Audit logging of administrative actions.
- Ed25519 digital signatures for license keys.
- Backup and restore functionality for data recovery.

The application is designed not to depend on cloud storage or external services during normal operation. However, offline operation alone does not guarantee security, privacy, or protection against data loss.

Actual security depends on the implementation, dependencies, Windows configuration, and deployment environment.

Academy operators are responsible for:

- Securing the Windows user account and PC.
- Restricting access to player records, photos, and financial information.
- Protecting backup files against unauthorized access.
- Keeping the operating system and relevant dependencies maintained.
- Complying with applicable data-protection requirements.

## Backup and Recovery

Regular backups help protect against accidental deletion, hardware failure, and database corruption.

Recommended practices:

1. Create backups regularly using the application's backup functionality.
2. Keep at least one additional backup on a separate storage device.
3. Protect backups because they may contain personal and financial information.
4. Test the restore process periodically.
5. Close the application before performing manual file-level backups to reduce the risk of inconsistent database copies.
6. Verify the restored data before relying on a backup for recovery.

Whenever possible, use the application's built-in backup and restore functionality rather than manually copying database files.

## Licensing

AcademyPro is proprietary software distributed under a per-machine licensing model.

License keys use Ed25519 digital signatures for validation.

For information about third-party components and their licenses, see `LICENSES.txt`.

## Project Status

| Property | Value |
|---|---|
| Application | AcademyPro |
| Version | 4.0.0 |
| Status | Shipped |
| Platform | Windows 10 and later |
| Deployment model | Single-PC desktop application |
| Database | Local SQLite |
| Operating model | Offline-first |
| License model | Per-machine |

## Summary

AcademyPro provides small sports academies with a desktop solution for membership management, QR-based attendance, subscription tracking, player development records, financial reporting, and administrative controls.

Its local database, offline-first design, and single-PC deployment model allow academies to manage day-to-day operations without maintaining server infrastructure or relying on cloud services.

