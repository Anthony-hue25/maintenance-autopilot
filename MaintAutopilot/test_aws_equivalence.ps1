$ErrorActionPreference = "Stop"

$gt = Import-Csv "..\data\ground_truth.csv"
$pred = Import-Csv "..\data\v2_5_regression_predictions.csv"

$outcomes = @(
    "ACT",
    "ASK",
    "AWAITING",
    "ESCALATE",
    "ACT+ESCALATE",
    "CLOSE"
)

$testCases = foreach ($outcome in $outcomes) {

    $frozen = $pred |
        Where-Object PolicyOutcome -eq $outcome |
        Select-Object -First 1

    $source = $gt |
        Where-Object Case_ID -eq $frozen.Case_ID |
        Select-Object -First 1

    [PSCustomObject]@{
        Case_ID       = $frozen.Case_ID
        Unit          = $source.Unit
        Request       = $source.Request
        Clarification = $source.Clarification_Response
        FrozenOutcome = $frozen.PolicyOutcome
        FrozenRule    = $frozen.PolicyRule
    }
}

foreach ($case in $testCases) {

    Write-Host ""
    Write-Host "========================================"
    Write-Host "CASE: $($case.Case_ID)"
    Write-Host "EXPECTED: $($case.FrozenOutcome)"
    Write-Host "RULE: $($case.FrozenRule)"
    Write-Host "========================================"

    $payload = @{
        request       = $case.Request
        unit          = $case.Unit
        clarification = $case.Clarification
        case_id       = "AWS-$($case.Case_ID)"
    } | ConvertTo-Json -Compress

    $payload | Set-Content ".\aws-test-payload.json" -Encoding ascii

    agentcore invoke `
        --runtime MaintAutopilot `
        --prompt-file ".\aws-test-payload.json"
}
