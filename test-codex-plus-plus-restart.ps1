$ErrorActionPreference = "Stop"

$scriptPath = Join-Path $PSScriptRoot "fix-codex-plus-plus-restart.ps1"
$source = Get-Content -LiteralPath $scriptPath -Raw

$functionMatch = [regex]::Match(
    $source,
    "function\s+Get-CodexAppDir\s*\{(?<body>[\s\S]*?)\r?\n\}",
    [System.Text.RegularExpressions.RegexOptions]::IgnoreCase
)

if (-not $functionMatch.Success) {
    throw "Get-CodexAppDir function was not found."
}

$body = $functionMatch.Groups["body"].Value
$appxIndex = $body.IndexOf("Get-AppxPackage", [System.StringComparison]::OrdinalIgnoreCase)
$cacheIndex = $body.IndexOf("realCodexPathFile", [System.StringComparison]::OrdinalIgnoreCase)

if ($appxIndex -lt 0) {
    throw "Get-CodexAppDir must resolve OpenAI.Codex through Get-AppxPackage so Codex++ survives WindowsApps version changes."
}

if ($cacheIndex -ge 0 -and $cacheIndex -lt $appxIndex) {
    throw "Get-CodexAppDir must prefer the current Appx install location before stale cached wrapper paths."
}

$requires = @{
    "Sync-CodexProfile" = "The repair script must sync the normal Codex profile into the Codex++ profile before launch."
    "codex-plus-profile" = "Codex++ must use a separate user-data-dir so it can open while normal Codex is already running."
    "--user-data-dir=" = "Codex++ settings must include a user-data-dir argument for the separate profile."
    "Test-FileReadable" = "The repair script must detect locked normal-Codex cookie files before touching the Codex++ profile."
    "Start-DeferredProfileSync" = "The repair script must start a background sync watcher when normal Codex keeps cookies locked."
    "Sync-CodexProfile -Deferred" = "The deferred watcher must be able to sync and restart Codex++ after cookies unlock."
    "Using existing Codex++ profile while normal Codex cookies are locked" = "The repair script must preserve the existing Codex++ profile when normal Codex cookies are locked."
    "Write-LatestStatus" = "The repair script must write latest-status.json after verified launches so the manager UI stays accurate."
    "Start-DirectCodexAppFallback" = "The repair script must directly launch Codex when the Codex++ launcher is blocked by a stale elevated helper."
    "Resolve-HelperPort" = "The repair script must avoid a helper port that is already owned by another local service."
    "Test-CodexPlusBackend" = "The repair script must verify the actual helper port reported by latest-status.json when the launcher falls back to another port."
    "Get-CodexPlusHelperPorts" = "The repair script must discover the persistent helper port owned by the Codex++ launcher guard."
    "Wait-DebugEndpoint" = "The repair script must wait for the debug endpoint during post-launch stability checks instead of failing on a single transient timeout."
    "Remove-CodexPathRefreshTask" = "The repair script must remove the scheduled Codex path refresh task so no PowerShell window flashes on a timer."
    "Install-StableBundledMarketplace" = "The repair script must restore the stable openai-bundled marketplace so plugins do not disappear after restart or account switching."
    "openai-bundled.staging" = "The repair script must recover openai-bundled from existing staging marketplace folders."
    "Install-StableCuratedMarketplace" = "The repair script must restore the stable openai-curated marketplace so Superpowers does not disappear after restart or account switching."
    "Update-CodexConfigMarketplaces" = "The repair script must point openai-curated at the stable marketplace path and keep Superpowers enabled."
    "superpowers" = "The repair script must explicitly keep the Superpowers plugin available in Codex++."
    "Install-CodexPlusWatchdogTask" = "The repair script must install a watchdog task so Codex++ responds after account switching and restarts."
    "Remove-CodexPlusWatchdogTask" = "The repair script must remove the watchdog task after successful verification so no background guard remains."
    "watch-codex-plus-plus.ps1" = "The repair script must write a persistent Codex++ watchdog script."
    "Update-LatestStatusFromRunningCodexPlus" = "The watchdog must refresh latest-status.json from the actual running debug/helper ports."
}

foreach ($needle in $requires.Keys) {
    if ($source.IndexOf($needle, [System.StringComparison]::OrdinalIgnoreCase) -lt 0) {
        throw $requires[$needle]
    }
}

if ($source -match '/Create\s+/TN\s+"Codex\+\+ Refresh Codex Path"') {
    throw "The repair script must not recreate the Codex++ Refresh Codex Path scheduled task."
}

$wrapperSourcePath = Join-Path $env:USERPROFILE ".codex-session-delete\codex-plus-wrapper-app\CodexWrapper.cs"
if (-not (Test-Path -LiteralPath $wrapperSourcePath)) {
    throw "Codex++ wrapper source was not found: $wrapperSourcePath"
}

$wrapperSource = Get-Content -LiteralPath $wrapperSourcePath -Raw
$wrapperRequires = @{
    "ResolveRealCodexPath" = "The wrapper must resolve the current real Codex executable instead of trusting a stale real-codex-path.txt after Appx upgrades."
    "Get-AppxPackage -Name OpenAI.Codex" = "The wrapper must query the current OpenAI.Codex Appx install location when its cached real path is stale."
    "File.WriteAllText(realPathFile" = "The wrapper must refresh real-codex-path.txt so future Codex++ restarts follow the upgraded Codex app."
}

foreach ($needle in $wrapperRequires.Keys) {
    if ($wrapperSource.IndexOf($needle, [System.StringComparison]::OrdinalIgnoreCase) -lt 0) {
        throw $wrapperRequires[$needle]
    }
}

"PASS: Codex++ repair handles Appx upgrades and normal-Codex-already-running launches."
