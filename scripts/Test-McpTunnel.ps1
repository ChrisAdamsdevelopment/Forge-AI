# Read-only Windows diagnostic for a protected MCP endpoint exposed via ngrok.
# Does not start ngrok, read a token, or modify the workstation.
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$NgrokExe,

    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$PublicUrl,

    [ValidateRange(1, 65535)]
    [int]$LocalPort = 8766,

    [string]$InspectorUrl = 'http://127.0.0.1:4040/api/tunnels'
)

$ErrorActionPreference = 'Stop'

function Get-StatusCode {
    param(
        [Parameter(Mandatory = $true)][string]$Uri,
        [hashtable]$Headers = @{}
    )
    try {
        $response = Invoke-WebRequest -Uri $Uri -UseBasicParsing -Headers $Headers -TimeoutSec 15 -ErrorAction Stop
        return [int]$response.StatusCode
    }
    catch {
        if ($null -ne $_.Exception.Response) {
            return [int]$_.Exception.Response.StatusCode
        }
        throw "Could not reach $Uri : $($_.Exception.Message)"
    }
}

try {
    if (-not (Test-Path -LiteralPath $NgrokExe -PathType Leaf)) {
        throw "ngrok.exe not found at '$NgrokExe'. Specify the exact verified binary."
    }

    $exe = (Resolve-Path -LiteralPath $NgrokExe).Path
    $rawVersion = (& $exe version | Out-String).Trim()
    if ($LASTEXITCODE -ne 0) {
        throw "ngrok exited with code $LASTEXITCODE during version check."
    }

    $match = [regex]::Match($rawVersion, 'ngrok version (\d+\.\d+\.\d+)')
    if (-not $match.Success) {
        throw "Unexpected ngrok version output: $rawVersion"
    }

    $version = [version]$match.Groups[1].Value
    if ($version -lt [version]'3.29.0') {
        throw "ngrok $version is too old; a version >= 3.29.0 is required."
    }
    Write-Host "[PASS] Verified executable: $exe ($version)"

    $baseUrl = $PublicUrl.Trim().TrimEnd('/')
    $parsed = $null
    if (-not [Uri]::TryCreate($baseUrl, [UriKind]::Absolute, [ref]$parsed) -or
        $parsed.Scheme -ne 'https' -or
        $parsed.AbsolutePath -ne '/') {
        throw 'PublicUrl must be an HTTPS ngrok origin without a path (for example https://example.ngrok-free.dev).'
    }

    $localEndpoint = "http://127.0.0.1:$LocalPort/mcp"
    $remoteEndpoint = "$baseUrl/mcp"

    $localStatus = Get-StatusCode -Uri $localEndpoint
    if ($localStatus -ne 401) {
        throw "Local MCP returned HTTP $localStatus instead of 401. The endpoint may be missing or unprotected."
    }
    Write-Host "[PASS] Local MCP refuses anonymous access: HTTP 401"

    $inspection = Invoke-RestMethod -Uri $InspectorUrl -TimeoutSec 10
    $tunnel = @($inspection.tunnels | Where-Object { $_.public_url -eq $baseUrl })
    if ($tunnel.Count -ne 1) {
        throw "Expected exactly one active ngrok tunnel for $baseUrl in $InspectorUrl; found $($tunnel.Count)."
    }

    $forward = [string]$tunnel[0].config.addr
    if ($forward -notmatch (':{0}(?:/|$)' -f $LocalPort)) {
        throw "ngrok is forwarding to '$forward' instead of port $LocalPort."
    }
    Write-Host "[PASS] ngrok inspector confirms forwarding: $forward"

    $remoteStatus = Get-StatusCode -Uri $remoteEndpoint -Headers @{ 'ngrok-skip-browser-warning' = 'true' }
    if ($remoteStatus -ne 401) {
        throw "Remote MCP returned HTTP $remoteStatus instead of 401. Do not send a bearer token."
    }
    Write-Host "[PASS] Remote MCP refuses anonymous access: HTTP 401"
    Write-Host '[PASS] Network and protection checks completed.'
    Write-Host 'NOTE: This does NOT confirm MCP tool registration in any AI client.'
    exit 0
}
catch {
    Write-Error "[FAIL] $($_.Exception.Message)"
    exit 1
}
