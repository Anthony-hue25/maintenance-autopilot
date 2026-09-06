# Maintenance Autopilot competition frontend

This is a dependency-free static web application. The browser sends only
`{"report":"..."}` to the public API.

Before hosting the frontend separately from the API, set
`window.MAINTENANCE_API_URL` in `config.js` to the deployed CDK `ApiUrl` output
without a trailing slash. Deploy the API with the frontend's exact HTTPS origin
as the `AllowedOrigin` CloudFormation parameter.

For a local static preview:

```powershell
python -m http.server 8000 --directory web
```

Local history is stored only in the current browser's `localStorage`. It is not
evidence that work was dispatched or completed.
