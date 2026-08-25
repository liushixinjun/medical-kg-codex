param(
    [switch]$Strict
)

$ErrorActionPreference = "Stop"

$ExpectedPython = "D:\Program Files Ai\python-venvs\medical-kg\Scripts\python.exe"
$ExpectedToolRoot = "D:\Program Files Ai"
$BlockedPathFragments = @(
    "C:\Users\LiuAiyi\AppData\Local\Python",
    "C:\Users\LiuAiyi\AppData\Local\Programs\Python",
    "C:\Users\LiuAiyi\.cache\codex-runtimes",
    "C:\Program Files\Tesseract-OCR",
    "C:\Program Files\poppler",
    "C:\poppler"
)

function Find-CommandPath {
    param([string]$Name)
    $oldPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $paths = & cmd.exe /d /c "where $Name 2>nul"
    $exitCode = $LASTEXITCODE
    $ErrorActionPreference = $oldPreference
    if ($exitCode -ne 0 -or -not $paths) {
        return @()
    }
    return @($paths)
}

function Test-BlockedPath {
    param([string]$PathText)
    foreach ($fragment in $BlockedPathFragments) {
        if ($PathText -like "$fragment*") {
            return $true
        }
    }
    return $false
}

$problems = New-Object System.Collections.Generic.List[string]
$warnings = New-Object System.Collections.Generic.List[string]

if (-not (Test-Path -LiteralPath $ExpectedPython)) {
    $problems.Add("Project Python missing: $ExpectedPython")
}

if (-not (Test-Path -LiteralPath $ExpectedToolRoot)) {
    $problems.Add("Project tool root missing: $ExpectedToolRoot")
}

$pythonWhere = Find-CommandPath "python"
$pipWhere = Find-CommandPath "pip"

if ($pythonWhere.Count -gt 0 -and $pythonWhere[0] -ne $ExpectedPython) {
    $warnings.Add("Do not call bare python. First PATH hit is $($pythonWhere[0]). Use explicit project Python: $ExpectedPython")
}

if ($pipWhere.Count -gt 0 -and (Test-BlockedPath $pipWhere[0])) {
    $warnings.Add("Do not call bare pip. First PATH hit is $($pipWhere[0]). Use: $ExpectedPython -m pip")
}

$tools = @("tesseract", "pdftoppm", "pdftotext", "java", "node", "dot")
foreach ($tool in $tools) {
    $paths = Find-CommandPath $tool
    foreach ($path in $paths) {
        if (Test-BlockedPath $path) {
            $warnings.Add("Tool $tool hits non-project path: $path. Prefer installation/config under $ExpectedToolRoot")
        }
    }
}

$report = [ordered]@{
    check_time = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
    expected_python = $ExpectedPython
    expected_tool_root = $ExpectedToolRoot
    python_where = $pythonWhere
    pip_where = $pipWhere
    tesseract_where = Find-CommandPath "tesseract"
    pdftoppm_where = Find-CommandPath "pdftoppm"
    pdftotext_where = Find-CommandPath "pdftotext"
    java_where = Find-CommandPath "java"
    node_where = Find-CommandPath "node"
    graphviz_dot_where = Find-CommandPath "dot"
    problems = @($problems)
    warnings = @($warnings)
}

$report | ConvertTo-Json -Depth 5 -Compress:$false

if ($problems.Count -gt 0 -or ($Strict -and $warnings.Count -gt 0)) {
    Write-Error ("Environment precheck failed. Problems: " + ($problems -join "; ") + " Warnings: " + ($warnings -join "; "))
    exit 1
}

Write-Output "Environment precheck finished."
