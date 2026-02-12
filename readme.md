fully vibecoded chrome extension

# Features

- **PC Time Tracking**: Displays logtime statistics for each computer in the 42 matrix
- **Timer Notifications**: Monitors upcoming evaluations (scale_teams) and sends system notifications when they're about to start

# Installation

1: go in the intra -> settings -> api -> register a new app

2: name of the app, image of your choice, description, application type: 42 Pedagogical Project

Redirect Uri
https://profile.intra.42.fr/

click submit
copy the client id and secret
in app.py

put your login in the .js

go in chrome extensions, activate devlopper mode at the top right, click load unpacked and select the folder of the project

## Install Dependencies

```bash
pip install -r requirements.txt
```

Or manually:
```bash
pip install flask flask-cors python-dateutil requests plyer
```

start the server ( app.py )

all done

# Timer Notifications

The application now includes a background monitoring feature that:
- Automatically starts when you first access the `/logtime/<login>` endpoint
- Checks for upcoming evaluations (scale_teams) every 60 seconds
- Sends a system notification when an evaluation is starting within 5 minutes
- Handles the case where `plyer` is not installed gracefully (notifications will be logged to console instead)

**Note:** Only one user can be monitored at a time. If the endpoint is called with a different login, the monitored user will be updated to the new login.
