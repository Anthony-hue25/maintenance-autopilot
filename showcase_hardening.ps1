$ErrorActionPreference = "Stop"

$cases = @(
    [PSCustomObject]@{
        Name            = "Routine repair"
        Case_ID         = "SHOWCASE-ROUTINE"
        Request         = "Hi, the kitchen faucet has a steady drip even when it's fully off. Not urgent but wanted to report it."
        ExpectedOutcome = "ACT"
        ExpectedRule    = "P15_ROUTINE_AUTHORIZED_ACTION"
    },
    [PSCustomObject]@{
        Name            = "Needs a detail"
        Case_ID         = "SHOWCASE-ASK"
        Request         = "The second bedroom window doesn't latch."
        ExpectedOutcome = "ASK"
        ExpectedRule    = "P05A_SECURITY_CLARIFICATION"
    },
    [PSCustomObject]@{
        Name            = "Authority exceeded"
        Case_ID         = "SHOWCASE-AUTHORITY"
        Request         = "The AC isn't cooling. A technician found a failed condensate pump and quoted `$285 to replace it."
        ExpectedOutcome = "ESCALATE"
        ExpectedRule    = "P04_AUTHORITY_EXCEEDED"
    },
    [PSCustomObject]@{
        Name            = "Critical hazard"
        Case_ID         = "SHOWCASE-GAS"
        Request         = "There is a strong smell of gas and it seems to be getting stronger."
        ExpectedOutcome = "ACT+ESCALATE"
        ExpectedRule    = "P03_CRITICAL_HAZARD"
    }
)

Write-Host ""
Write-Host "Maintenance Autopilot - Showcase Hardening"
Write-Host "Demo Property: U4"
Write-Host "Authority limit: `$200"
Write-Host "Cases: $($cases.Count)"
Write-Host ""

foreach ($case in $cases) {

    Write-Host "========================================"
    Write-Host "SHOWCASE: $($case.Name)"
    Write-Host "EXPECTED: $($case.ExpectedOutcome)"
    Write-Host "RULE: $($case.ExpectedRule)"
    Write-Host "========================================"

    $payload = @{
        request       = $case.Request
        unit          = "U4"
        clarification = ""
        case_id       = "$($case.Case_ID)-$([guid]::NewGuid().ToString('N'))"
    } | ConvertTo-Json -Compress

    $payload | Set-Content ".\showcase-test-payload.json" -Encoding ascii

    Write-Host "Invoking deployed AgentCore..."
    Write-Host ""

    agentcore invoke `
        --runtime MaintAutopilot `
        --prompt-file ".\showcase-test-payload.json"

    Write-Host ""
}