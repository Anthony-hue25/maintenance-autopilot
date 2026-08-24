# Judge Testing Guide

## Prerequisites
1. Python 3.10+
2. `pip install -r requirements.txt`
3. AWS credentials for an account with Bedrock model access
4. `aws sts get-caller-identity` succeeds

No AWS credentials are stored in this repository.

## Run the curated sample

Windows PowerShell:

```powershell
python -u -m app.v2_agent --input data\sample_cases.csv --output data\sample_predictions.csv
```

macOS/Linux:

```bash
python -u -m app.v2_agent --input data/sample_cases.csv --output data/sample_predictions.csv
```

Open `data/sample_predictions.csv`.

The sample is designed to exercise:
1. Routine maintenance -> `ACT`
2. Missing decision-changing information -> `ASK`
3. Non-safety silence -> `AWAITING`
4. Repeat failure -> `ESCALATE`
5. Critical hazard -> `ACT+ESCALATE`
6. Secure-but-broken door hardware -> `ACT`

## Troubleshooting

If AWS authentication expires:

```bash
aws login
aws sts get-caller-identity
```

If PowerShell blocks activation:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```
