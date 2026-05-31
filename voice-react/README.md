# Speech Cleaner React App

React frontend for the Flask sentence correction API.

## Local HTTP

```powershell
npm.cmd install
npm.cmd run dev
```

Open:

```text
http://localhost:5173
```

## HTTPS Over WiFi

Keep the Flask backend running on port `5000`, then:

```powershell
npm.cmd run dev:https
```

Open on the phone:

```text
https://192.168.0.101:5174
```

The phone may show a self-signed certificate warning. Continue past it, then allow microphone permission.
