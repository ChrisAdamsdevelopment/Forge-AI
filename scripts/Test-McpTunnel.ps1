# Read-only diagnostic for a protected local MCP server exposed through ngrok.
# Windows PowerShell 5.1+. Never reads or prints bearer tokens.
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

    [ValidateNotNullOrEmpty()]
    [string]$ServerCommandMarker = 'local-workspace-mcp'
)

$ErrorActionPreference = 'Stop'
$inspectorUrl = 'http://127.0.0.1:4040/api/tunnels'

function Get-StatusCode {
    param(
        [Parameter(Mandatory = $true)][string]$Uri,
        [ValidateSet('Get', 'Post')][string]$Method = 'Get',
        [hashtable]$Headers = @{}
    )

    $request = @{
        Uri                = $Uri
        Method             = $Method
        Headers            = $Headers
        UseBasicParsing    = $true
        TimeoutSec         = 15
        MaximumRedirection = 0
        ErrorAction        = 'Stop'
    }
    if ($Method -eq 'Post') {
        # MCP initialize is a protocol handshake, not a file or tool operation.
        $request.ContentType = 'application/json'
        $request.Body = '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"mcp-tunnel-probe","version":"1.0"}}}'
        $request.Headers = @{} + $Headers
        $request.Headers['Accept'] = 'application/json, text/event-stream'
    }

    try {
        $response = Invoke-WebRequest @request
        return [int]$response.StatusCode
    }
    catch {
        if ($null -ne $_.Exception.Response) {
            return [int]$_.Exception.Response.StatusCode
        }
        throw "Request to $Uri failed without an HTTP status: $($_.Exception.Message)"
    }
}

function Assert-AnonymousRejected {
    param(
        [Parameter(Mandatory = $true)][string]$Endpoint,
        [hashtable]$Headers = @{},
        [Parameter(Mandatory = $true)][string]$Description
    )

    foreach ($method in @('Get', 'Post')) {
        $status = Get-StatusCode -Uri $Endpoint -Method $method -Headers $Headers
        if ($status -ne 401) {
            throw "$Description $method returned HTTP $status, not 401. Authentication is not verified."
        }
    }
    Write-Host "[PASS] $Description rejects anonymous GET and MCP initialize POST (401)."
}

function Get-VerifiedForward {
    param([Parameter(Mandatory = $true)][string]$ExpectedOrigin)

    # The ngrok inspection API is intentionally fixed to loopback.
    $inspection = Invoke-RestMethod -Uri $inspectorUrl -TimeoutSec 10 -MaximumRedirection 0
    $matchingTunnels = @($inspection.tunnels | Where-Object { $_.public_url -eq $ExpectedOrigin })
    if ($matchingTunnels.Count -ne 1) {
        throw "Expected exactly one ngrok tunnel for $ExpectedOrigin, found $($matchingTunnels.Count)."
    }

    $address = [string]$matchingTunnels[0].config.addr
    $forwardUri = $null
    if (-not [Uri]::TryCreate($address, [UriKind]::Absolute, [ref]$forwardUri) -or
        $forwardUri.Scheme -ne 'http' -or
        $forwardUri.Host -notin @('localhost', '127.0.0.1', '::1') -or
        $forwardUri.Port -ne $LocalPort -or
        $forwardUri.AbsolutePath -ne '/') {
        throw "ngrok forward target is not loopback HTTP on port $LocalPort."
    }
    return $forwardUri.AbsoluteUri
}

try {
    if (-not (Test-Path -LiteralPath $NgrokExe -PathType Leaf)) {
        throw "ngrok.exe not found at the specified path. Do not use ambiguous PATH shims."
    }
    $exe = (Resolve-Path -LiteralPath $NgrokExe).Path
    $rawVersion = (& $exe version | Out-String).Trim()
    if ($LASTEXITCODE -ne 0) { throw 'ngrok version command failed.' }
    $versionMatch = [regex]::Match($rawVersion, 'ngrok version (\d+\.\d+\.\d+)')
    if (-not $versionMatch.Success -or
        [version]$versionMatch.Groups[1].Value -lt [version]'3.29.0') {
        throw "ngrok version unsupported: $rawVersion"
    }
    Write-Host "[PASS] Verified ngrok executable and version: $($versionMatch.Groups[1].Value)"

    # Only ngrok-managed HTTPS origin hostnames; no credentials, port, path, query or fragment.
    $origin = $PublicUrl.Trim().TrimEnd('/').ToLowerInvariant()
    if ($origin -notmatch '^https://[a-z0-9-]+(?:\.[a-z0-9-]+)*\.(ngrok-free\.dev|ngrok-free\.app|ngrok\.dev|ngrok\.app)$') {
        throw 'PublicUrl must be an ngrok HTTPS origin without port, path, query, fragment or credentials.'
    }

    # A 401 from an arbitrary local service does not establish server identity.
    $listeners = @(Get-NetTCPConnection -LocalPort $LocalPort -State Listen -ErrorAction Stop |
        Where-Object { $_.LocalAddress -in @('127.0.0.1', '::1') })
    if ($listeners.Count -ne 1) {
        throw "Expected one loopback listener on port $LocalPort, found $($listeners.Count)."
    }
    $ownerPid = [int]$listeners[0].OwningProcess
    $owner = Get-CimInstance -ClassName Win32_Process -Filter "ProcessId = $ownerPid" -ErrorAction Stop
    if ($null -eq $owner -or
        [string]::IsNullOrWhiteSpace($owner.CommandLine) -or
        $owner.CommandLine.IndexOf($ServerCommandMarker, [StringComparison]::OrdinalIgnoreCase) -lt 0) {
        throw "Listener PID $ownerPid does not match expected server marker. Verify the existing launcher; do not expose a different process."
    }
    Write-Host "[PASS] MCP loopback listener process verified (PID $ownerPid)."

    $before = Get-VerifiedForward -ExpectedOrigin $origin
    Write-Host "[PASS] ngrok inspector forwarding points to $before"

    Assert-AnonymousRejected -Endpoint "http://127.0.0.1:$LocalPort/mcp" -Description 'Local MCP'
    Assert-AnonymousRejected -Endpoint "$origin/mcp" -Description 'Public MCP' -Headers @{
        'ngrok-skip-browser-warning' = 'true'
    }

    $after = Get-VerifiedForward -ExpectedOrigin $origin
    if ($before -ne $after) {
        throw 'ngrok forwarding changed during the probe. Retry only after investigating the change.'
    }
    Write-Host '[PASS] ngrok forwarding remained stable across the probe.'
    Write-Host '[PASS] Read-only transport/authentication probes completed.'
    Write-Host 'NOTE: Authenticated MCP registration in ChatGPT is NOT tested.'
    exit 0
}
catch {
    Write-Error "[FAIL] $($_.Exception.Message)"
    exit 1
}
