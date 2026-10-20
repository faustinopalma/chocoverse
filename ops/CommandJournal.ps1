#Requires -Version 7.4

function Protect-CommandText {
    param([AllowEmptyString()][string]$Text)
    $text = $Text -replace '(?i)Bearer\s+\S+', 'Bearer <redacted>'
    $text = $text -replace '(?i)([?&](?:sig|token|key|code|client_secret|access_token)=)[^&\s"]+', '$1<redacted>'
    $text = $text -replace '(?i)((?:password|secret|accountkey|authorization|access_token)\s*[=:]\s*)[^,\s"}]+', '$1<redacted>'
    $text = $text -replace '[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]+', '<redacted-jwt>'
    $text = $text -replace '(?i)[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}', '<id>'
    $text = $text -replace '[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}', '<principal>'
    return $text
}

function Write-CommandRecord {
    param(
        [Parameter(Mandatory)][string]$Operation,
        [Parameter(Mandatory)][ValidateSet('Started', 'Succeeded', 'Failed')][string]$Status,
        [Parameter(Mandatory)][string]$InvocationId,
        [object]$Details
    )
    $directory = Join-Path $PSScriptRoot '..\.local\command-journal'
    [IO.Directory]::CreateDirectory($directory) | Out-Null
    $record = [ordered]@{
        timestamp = [DateTimeOffset]::UtcNow.ToString('o')
        processId = $PID
        invocationId = $InvocationId
        operation = Protect-CommandText $Operation
        status = $Status
        details = if ($null -eq $Details) { $null } else {
            Protect-CommandText ($Details | ConvertTo-Json -Depth 7 -Compress) | ConvertFrom-Json
        }
    }
    $json = $record | ConvertTo-Json -Depth 8 -Compress
    [IO.File]::AppendAllText((Join-Path $directory "$PID.jsonl"), "$json`r`n", [Text.UTF8Encoding]::new($false))
}

function Get-RecordedArguments {
    param([string[]]$Arguments)
    $hideNext = $false
    return @(
        foreach ($argument in $Arguments) {
            if ($hideNext) { '<redacted>'; $hideNext = $false; continue }
            if ($argument -match '^(--(?:password|client-secret|access-token|account-key|sas-token|body))=') {
                "$($Matches[1])=<redacted>"; continue
            }
            if ($argument -match '^(--(?:password|client-secret|access-token|account-key|sas-token|body)|-EncodedCommand)$') {
                $hideNext = $true
            }
            Protect-CommandText $argument
        }
    )
}

function Invoke-RecordedNative {
    param(
        [Parameter(Mandatory)][string]$FilePath,
        [string[]]$Arguments = @(),
        [ValidateRange(0, 3600)][int]$TimeoutSeconds = 0
    )
    $id = [guid]::NewGuid().ToString()
    $operation = $FilePath
    $safeArguments = @(Get-RecordedArguments $Arguments)
    Write-CommandRecord -Operation $operation -Status Started -InvocationId $id -Details @{
        arguments = $safeArguments; timeoutSeconds = $TimeoutSeconds
    }
    $code = $null
    try {
        if ($TimeoutSeconds) {
            $start = [Diagnostics.ProcessStartInfo]::new($FilePath)
            $start.UseShellExecute = $false
            foreach ($argument in $Arguments) { $start.ArgumentList.Add($argument) }
            $process = [Diagnostics.Process]::Start($start)
            try {
                if (-not $process.WaitForExit($TimeoutSeconds * 1000)) {
                    $process.Kill($true)
                    $process.WaitForExit()
                    throw "Native command exceeded its $TimeoutSeconds-second limit."
                }
                $code = $process.ExitCode
            }
            finally { $process.Dispose() }
        }
        else {
            & $FilePath @Arguments
            $code = $LASTEXITCODE
        }
        if ($code -ne 0) { throw "Native command failed with exit code $code." }
        Write-CommandRecord -Operation $operation -Status Succeeded -InvocationId $id -Details @{ exitCode = $code }
    }
    catch {
        Write-CommandRecord -Operation $operation -Status Failed -InvocationId $id -Details @{
            errorType = $_.Exception.GetType().FullName
            timeoutSeconds = $TimeoutSeconds
            exitCode = $code
        }
        throw
    }
}

function Invoke-RecordedWebRequest {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][uri]$Uri,
        [string]$Method = 'GET',
        [hashtable]$Headers = @{},
        [object]$Body,
        [string]$ContentType,
        [switch]$SkipHttpErrorCheck,
        [int]$TimeoutSec = 60
    )
    if ($Uri.Scheme -ne 'https') { throw 'Recorded requests require HTTPS.' }
    $id = [guid]::NewGuid().ToString()
    $operation = "$Method $Uri"
    $details = @{}
    if ($PSBoundParameters.ContainsKey('Body')) {
        $bytes = if ($Body -is [byte[]]) { $Body } else { [Text.Encoding]::UTF8.GetBytes([string]$Body) }
        $details.bodySha256 = [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($bytes))
        $details.bodyBytes = $bytes.Length
    }
    Write-CommandRecord -Operation $operation -Status Started -InvocationId $id -Details $details
    $recorded = $false
    try {
        $request = @{
            Uri = $Uri; Method = $Method; Headers = $Headers; SkipHttpErrorCheck = $true; TimeoutSec = $TimeoutSec
        }
        if ($PSBoundParameters.ContainsKey('Body')) { $request.Body = $Body }
        if ($ContentType) { $request.ContentType = $ContentType }
        $response = Invoke-WebRequest @request
        $ok = [int]$response.StatusCode -ge 200 -and [int]$response.StatusCode -lt 300
        Write-CommandRecord -Operation $operation -Status $(if ($ok) { 'Succeeded' } else { 'Failed' }) `
            -InvocationId $id -Details @{ httpStatus = [int]$response.StatusCode }
        $recorded = $true
        if (-not $ok -and -not $SkipHttpErrorCheck) {
            throw "HTTP $([int]$response.StatusCode): $(Protect-CommandText $response.Content)"
        }
        return $response
    }
    catch {
        if (-not $recorded) {
            Write-CommandRecord -Operation $operation -Status Failed -InvocationId $id -Details @{
                errorType = $_.Exception.GetType().FullName
            }
        }
        throw
    }
}
