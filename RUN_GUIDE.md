# Travel Planner Agent - Windows 11 Run Guide
PyCharm + PowerShell instructions for this project. Run commands from the project root. The path contains spaces, so quote it.
## Runtime architecture
- **CLI mode** is a one-shot command-line program and does not start a server.
- **Website mode** starts a local FastAPI/Uvicorn server on `127.0.0.1:8000`.
- Open the website at **http://localhost:8000** while that server is running.
- DeepSeek communication uses **outbound HTTPS to `api.deepseek.com` port 443**.
- Port 8000 is the local website server; port 443 is the remote DeepSeek API port.
## Daily startup and shutdown
### Website
Start from the project root:

```powershell
Set-Location -LiteralPath 'C:\Users\demch\PycharmProjects\Travel Planner Agent'
.\.venv\Scripts\Activate.ps1
python -m travel_agent.web
```

Open **http://localhost:8000** in a browser. The page starts in **Offline demo** mode; after `.env` is configured, select **DeepSeek live**. Leave this terminal running while using the site. Press `Ctrl+C` in the terminal to stop the server, then:

```powershell
deactivate
```

### CLI
Offline CLI mode, no API key required:

```powershell
python -m travel_agent --offline --request ".\examples\paris_vegetarian.json"
```

For live CLI mode, remove `--offline` after configuring `.env`:

```powershell
python -m travel_agent --request ".\examples\paris_vegetarian.json"
```

The CLI exits by itself after one plan. Press `Ctrl+C` only to interrupt it, then run `deactivate`.

## Initial setup (once)
### 1. Open the project and select the interpreter
In PyCharm, use **File > Open** and select `C:\Users\demch\PycharmProjects\Travel Planner Agent`. Open the terminal with `Alt+F12`. Under **File > Settings > Project: Travel Planner Agent > Python Interpreter**, select `.venv\Scripts\python.exe`.

```powershell
Set-Location -LiteralPath 'C:\Users\demch\PycharmProjects\Travel Planner Agent'
.\.venv\Scripts\python.exe --version
```

Expected: `Python 3.13.1` (3.11 or newer is required).

### 2. Create the virtual environment if missing and activate it

```powershell
if (-not (Test-Path -LiteralPath ".\.venv\Scripts\python.exe")) {
    py -m venv .venv
}
.\.venv\Scripts\Activate.ps1
```

The prompt should begin with `(.venv)`. If activation is blocked:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```powershell
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

### 4. Create and configure `.env`
This checkout already has `.env`; do not overwrite existing configuration.

```powershell
if (-not (Test-Path -LiteralPath ".\.env")) {
    Copy-Item -LiteralPath ".\.env.example" -Destination ".\.env"
}
notepad.exe ".\.env"
```

Set the key without quotes or spaces:

```dotenv
DEEPSEEK_API_KEY=your-deepseek-api-key-here
DEEPSEEK_MODEL=deepseek-flash
DEEPSEEK_BASE_URL=https://api.deepseek.com
```

Verify without printing the key:

```powershell
python -c "from dotenv import load_dotenv; import os; load_dotenv(); print('DEEPSEEK_API_KEY configured:', bool(os.getenv('DEEPSEEK_API_KEY')))"
```

Expected: `DEEPSEEK_API_KEY configured: True`. If it is `False`, confirm you are in the project root and the file is exactly `.env`, not `.env.txt`.

## Running the application
### Website

```powershell
python -m travel_agent.web
```

Open **http://localhost:8000**. Use the form and click **Generate Itinerary**. The browser UI shows flights, accommodation, weather, daily activities, budget breakdown, and the trace path. Offline mode needs no key; **DeepSeek live** uses `.env`. FastAPI API docs are at **http://localhost:8000/docs**.

### CLI

Offline interactive and example requests:

```powershell
python -m travel_agent --offline
python -m travel_agent --offline --request ".\examples\paris_vegetarian.json"
python -m travel_agent --offline --request ".\examples\prague_vegan.json"
```

Live DeepSeek CLI modes (valid key required; API charges may apply):

```powershell
python -m travel_agent
python -m travel_agent --request ".\examples\paris_vegetarian.json"
```

CLI success signs: the `[Mode]` banner, `[Agent] Final itinerary validated.`, a `Trace written to:` line, and exit code `0`. Exit codes are `1` for planning failure, `2` for configuration/input error, and `130` for cancellation.

## Stopping the application
**Website:** click the terminal running `python -m travel_agent.web` and press `Ctrl+C`. The server stops and the terminal returns to the prompt.

**CLI:** the CLI exits by itself after one plan. Press `Ctrl+C` only to interrupt it.

Traces are flushed as events are written. A cancelled run may lack `final_output` or `run_finished`, but existing JSONL lines remain readable. A forced kill can leave an incomplete trace. There is no resume feature; start a new run.

```powershell
deactivate
```

Use `exit` to close the terminal after the application has stopped.

## Tests

```powershell
python -m pytest -q
```

Verified result: `91 passed` (one third-party TestClient deprecation warning may appear). Tests are offline and require no API key.

## Traces
Regenerate the two offline demo traces, or use `--live` for DeepSeek:

```powershell
python .\scripts\generate_traces.py
python .\scripts\generate_traces.py --live
```

Inspect the traces:

```powershell
Get-ChildItem -LiteralPath ".\traces" | Select-Object Name, Length
$events = Get-Content -LiteralPath ".\traces\run_1.jsonl" -Encoding UTF8 | ForEach-Object { $_ | ConvertFrom-Json }
$events | Group-Object event | Select-Object Name, Count
($events | Select-Object -Last 1) | Select-Object event, status, iterations_used
```

Website runs create additional `traces\web_*.jsonl` files. Their mode is `web_offline_simulated` or `web_deepseek_live`.

## Essential troubleshooting
**Activation blocked**

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

**Missing packages, wrong interpreter, or `ModuleNotFoundError`**

```powershell
python -c "import sys; print(sys.executable)"
python -m pip install -e ".[dev]"
python -m pip check
python -c "import travel_agent; print(travel_agent.__file__)"
```

The interpreter should be inside `.venv`, and the package file should be under `src\travel_agent`.

**Missing or invalid key**

- Missing: `DEEPSEEK_API_KEY is not configured...`
- Invalid: `DeepSeek authentication failed. Check that DEEPSEEK_API_KEY is valid.`
- Fix `.env` and rerun the non-secret key check. Never print the key.

**Network error**

```powershell
Test-NetConnection -ComputerName api.deepseek.com -Port 443
```

`TcpTestSucceeded : True` confirms outbound HTTPS. If it is `False`, check internet, VPN, proxy, and firewall settings. Port 443 is the remote DeepSeek port; the website listens locally on **8000**. Offline mode can confirm that the application itself works.

**Website will not open or port 8000 is busy**

```powershell
Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | Select-Object LocalAddress,State,OwningProcess
```

If an old server is using the port, stop it with `Ctrl+C` in its terminal. Then start `python -m travel_agent.web` again and open **http://localhost:8000**. If the terminal does not show the Uvicorn startup line, rerun the command in the project root and check for a missing FastAPI package:

```powershell
python -m pip install -e ".[dev]"
```

**Wrong directory or paths with spaces**

```powershell
Get-Location
Test-Path -LiteralPath ".\.env"
Test-Path -LiteralPath ".\src\travel_agent"
Set-Location -LiteralPath 'C:\Users\demch\PycharmProjects\Travel Planner Agent'
```

For direct execution without activation:

```powershell
& ".\.venv\Scripts\python.exe" -m travel_agent --offline --request ".\examples\paris_vegetarian.json"
```

## API key security
- Keep the real key only in `.env`; `.gitignore` excludes `.env` and `.env.*`.
- `.env.example` was inspected: `DEEPSEEK_API_KEY=` is empty, so it contains no real secret.
- Never print, screenshot, paste into chat, or commit the real key.
- Traces contain request and tool data, but not the API key.
- If a key is exposed, revoke it at <https://platform.deepseek.com/api_keys> and create a new one.
