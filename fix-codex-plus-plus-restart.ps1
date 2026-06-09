$ErrorActionPreference = "Stop"

$desktop = [Environment]::GetFolderPath("Desktop")
$installDir = Join-Path $env:LOCALAPPDATA "Programs\Codex++"
$launcher = Join-Path $installDir "codex-plus-plus.exe"
$manager = Join-Path $installDir "codex-plus-plus-manager.exe"
$stateDir = Join-Path $env:USERPROFILE ".codex-session-delete"
$statusPath = Join-Path $stateDir "latest-status.json"
$logPath = Join-Path $stateDir "codex-plus.log"
$wrapperAppDir = Join-Path $stateDir "codex-plus-wrapper-app"
$realCodexPathFile = Join-Path $wrapperAppDir "real-codex-path.txt"
$plusProfile = Join-Path $stateDir "codex-plus-profile"
$stableLauncherScript = Join-Path $stateDir "start-codex-plus-plus.ps1"
$refreshCodexPathScript = Join-Path $stateDir "refresh-codex-plus-real-path.ps1"
$watchdogScript = Join-Path $stateDir "watch-codex-plus-plus.ps1"
$deferredSyncScript = Join-Path $stateDir "sync-codex-plus-profile-when-unlocked.ps1"
$deferredSyncPidFile = Join-Path $stateDir "sync-codex-plus-profile-when-unlocked.pid"
$resultPath = Join-Path $desktop "codex-plus-plus-repair-result.txt"
$debugPort = 9229
$helperPort = 57321
$helperPortCandidates = @(57321, 57322, 57323, 57324, 57325, 57326, 57327, 57328, 57329, 57330)
$deferredMode = $args -contains "--deferred-sync"
$bundledMarketplaceRoot = Join-Path $env:USERPROFILE ".codex\.tmp\bundled-marketplaces"
$stableBundledMarketplaceDir = Join-Path $bundledMarketplaceRoot "openai-bundled"
$stableCuratedMarketplaceDir = Join-Path $bundledMarketplaceRoot "openai-curated"

function Write-Result {
    param([string]$Message)
    $line = "[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message
    Add-Content -LiteralPath $resultPath -Value $line -Encoding UTF8
    Write-Host $line
}

function Backup-File {
    param([string]$Path)
    if (Test-Path -LiteralPath $Path) {
        $backup = "$Path.bak-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
        Copy-Item -LiteralPath $Path -Destination $backup -Force
        Write-Result "Backed up $Path -> $backup"
    }
}

function Resolve-HelperPort {
    foreach ($candidate in $helperPortCandidates) {
        $owner = Get-NetTCPConnection -LocalPort $candidate -State Listen -ErrorAction SilentlyContinue |
            Select-Object -First 1 -ExpandProperty OwningProcess
        if (-not $owner) {
            return $candidate
        }

        Write-Result "Helper port $candidate is already in use by pid=$owner; trying next candidate."
    }

    Write-Result "All preferred helper ports are in use; falling back to $helperPort and allowing the launcher to choose an alternate port."
    return $helperPort
}

function Get-LatestStatusHelperPort {
    if (-not (Test-Path -LiteralPath $statusPath)) {
        return 0
    }

    try {
        $status = Get-Content -LiteralPath $statusPath -Raw | ConvertFrom-Json
        if ($status.helper_port) {
            return [int]$status.helper_port
        }
    } catch {
    }

    return 0
}

function Get-CodexPlusHelperPorts {
    $launcherProcessIds = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
        $_.Name -eq "codex-plus-plus.exe"
    } | Select-Object -ExpandProperty ProcessId

    if (-not $launcherProcessIds) {
        return @()
    }

    $ports = Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object {
        ($launcherProcessIds -contains $_.OwningProcess) -and
        $_.LocalPort -ne 57320 -and
        $_.LocalPort -ne $debugPort
    } | Select-Object -ExpandProperty LocalPort -Unique

    return @($ports)
}

function Test-CodexPlusBackend {
    param([ref]$ActiveHelperPort)

    $ports = New-Object System.Collections.Generic.List[int]
    foreach ($port in (Get-CodexPlusHelperPorts)) {
        $ports.Add([int]$port)
    }

    $statusHelperPort = Get-LatestStatusHelperPort
    if ($statusHelperPort -gt 0 -and $statusHelperPort -ne $helperPort) {
        $ports.Add([int]$statusHelperPort)
    }

    $ports.Add([int]$helperPort)

    foreach ($port in ($ports | Select-Object -Unique)) {
        if (Test-Http "http://127.0.0.1:$port/backend/status") {
            $ActiveHelperPort.Value = $port
            return $true
        }
    }

    return $false
}

function Remove-CodexPathRefreshTask {
    & "$env:WINDIR\System32\schtasks.exe" /End /TN "Codex++ Refresh Codex Path" 2>$null | Out-Null
    & "$env:WINDIR\System32\schtasks.exe" /Delete /TN "Codex++ Refresh Codex Path" /F 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Result "Removed Codex path refresh task to prevent scheduled PowerShell window flashes."
    } else {
        Write-Result "Codex path refresh task was not present or could not be removed; schtasks exit code $LASTEXITCODE"
    }
}

function Copy-DirectorySafe {
    param([string]$Source, [string]$Destination, [string]$AllowedRoot)

    $resolvedRoot = [System.IO.Path]::GetFullPath($AllowedRoot).TrimEnd('\')
    $resolvedDestination = [System.IO.Path]::GetFullPath($Destination).TrimEnd('\')
    if (-not $resolvedDestination.StartsWith("$resolvedRoot\", [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to replace directory outside allowed root: $resolvedDestination"
    }

    if (Test-Path -LiteralPath $Destination) {
        Remove-Item -LiteralPath $Destination -Recurse -Force
    }
    Copy-Item -LiteralPath $Source -Destination $Destination -Recurse -Force
}

function Add-SuperpowersToMarketplace {
    param([string]$MarketplaceDir)

    $marketplaceJson = Join-Path $MarketplaceDir ".agents\plugins\marketplace.json"
    $pluginsDir = Join-Path $MarketplaceDir "plugins"
    if (-not (Test-Path -LiteralPath $marketplaceJson)) {
        Write-Result "Marketplace JSON not found; Superpowers injection skipped: $marketplaceJson"
        return
    }

    $cacheRoot = Join-Path $env:USERPROFILE ".codex\plugins\cache\openai-curated"
    $superpowersSource = Get-ChildItem -LiteralPath (Join-Path $cacheRoot "superpowers") -Directory -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
    if (-not $superpowersSource) {
        Write-Result "Superpowers cache not found; marketplace injection skipped."
        return
    }

    New-Item -ItemType Directory -Force -Path $pluginsDir | Out-Null
    $superpowersTarget = Join-Path $pluginsDir "superpowers"
    Copy-DirectorySafe -Source $superpowersSource.FullName -Destination $superpowersTarget -AllowedRoot $pluginsDir

    $marketplace = Get-Content -LiteralPath $marketplaceJson -Raw | ConvertFrom-Json
    $plugins = @($marketplace.plugins)
    $existing = $plugins | Where-Object { $_.name -eq "superpowers" } | Select-Object -First 1
    if (-not $existing) {
        $plugins += [ordered]@{
            name = "superpowers"
            source = [ordered]@{ source = "local"; path = "./plugins/superpowers" }
            policy = [ordered]@{ installation = "AVAILABLE"; authentication = "ON_INSTALL" }
            category = "Developer Tools"
        }
    }

    $updatedMarketplace = [ordered]@{
        name = $marketplace.name
        interface = $marketplace.interface
        plugins = $plugins
    }
    [System.IO.File]::WriteAllText(
        $marketplaceJson,
        ($updatedMarketplace | ConvertTo-Json -Depth 20),
        [System.Text.UTF8Encoding]::new($false)
    )
    Write-Result "Ensured Superpowers is available in marketplace: $MarketplaceDir"
}

function Install-StableBundledMarketplace {
    New-Item -ItemType Directory -Force -Path $bundledMarketplaceRoot | Out-Null

    $stableMarketplaceJson = Join-Path $stableBundledMarketplaceDir ".agents\plugins\marketplace.json"
    $stablePluginDir = Join-Path $stableBundledMarketplaceDir "plugins"
    if ((Test-Path -LiteralPath $stableMarketplaceJson) -and (Test-Path -LiteralPath $stablePluginDir)) {
        Write-Result "Stable openai-bundled marketplace already exists: $stableBundledMarketplaceDir"
        Add-SuperpowersToMarketplace -MarketplaceDir $stableBundledMarketplaceDir
        return
    }

    $source = Get-ChildItem -LiteralPath $bundledMarketplaceRoot -Directory -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -like "openai-bundled.staging*" } |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1

    if ($source) {
        Copy-DirectorySafe -Source $source.FullName -Destination $stableBundledMarketplaceDir -AllowedRoot $bundledMarketplaceRoot
        Write-Result "Restored stable openai-bundled marketplace from staging: $($source.FullName)"
        Add-SuperpowersToMarketplace -MarketplaceDir $stableBundledMarketplaceDir
        return
    }

    $cacheRoot = Join-Path $env:USERPROFILE ".codex\plugins\cache\openai-bundled"
    if (-not (Test-Path -LiteralPath $cacheRoot)) {
        Write-Result "openai-bundled cache not found; plugin marketplace restore skipped."
        return
    }

    if (Test-Path -LiteralPath $stableBundledMarketplaceDir) {
        Copy-DirectorySafe -Source $cacheRoot -Destination $stableBundledMarketplaceDir -AllowedRoot $bundledMarketplaceRoot
    } else {
        New-Item -ItemType Directory -Force -Path $stableBundledMarketplaceDir | Out-Null
    }

    $agentsDir = Join-Path $stableBundledMarketplaceDir ".agents\plugins"
    $pluginsDir = Join-Path $stableBundledMarketplaceDir "plugins"
    New-Item -ItemType Directory -Force -Path $agentsDir | Out-Null
    New-Item -ItemType Directory -Force -Path $pluginsDir | Out-Null

    $plugins = @()
    foreach ($name in @("browser", "chrome", "computer-use")) {
        $latest = Get-ChildItem -LiteralPath (Join-Path $cacheRoot $name) -Directory -ErrorAction SilentlyContinue |
            Sort-Object LastWriteTime -Descending |
            Select-Object -First 1
        if (-not $latest) {
            continue
        }
        $target = Join-Path $pluginsDir $name
        Copy-DirectorySafe -Source $latest.FullName -Destination $target -AllowedRoot $pluginsDir
        $plugins += [ordered]@{
            name = $name
            source = [ordered]@{ source = "local"; path = "./plugins/$name" }
            policy = [ordered]@{ installation = "AVAILABLE"; authentication = "ON_INSTALL" }
            category = if ($name -eq "browser") { "Engineering" } else { "Productivity" }
        }
    }

    $marketplace = [ordered]@{
        name = "openai-bundled"
        interface = [ordered]@{ displayName = "OpenAI Bundled" }
        plugins = $plugins
    }
    [System.IO.File]::WriteAllText(
        (Join-Path $agentsDir "marketplace.json"),
        ($marketplace | ConvertTo-Json -Depth 20),
        [System.Text.UTF8Encoding]::new($false)
    )
    Write-Result "Rebuilt stable openai-bundled marketplace from cache: $stableBundledMarketplaceDir"
    Add-SuperpowersToMarketplace -MarketplaceDir $stableBundledMarketplaceDir
}

function Install-StableCuratedMarketplace {
    New-Item -ItemType Directory -Force -Path $bundledMarketplaceRoot | Out-Null

    $cacheRoot = Join-Path $env:USERPROFILE ".codex\plugins\cache\openai-curated"
    $superpowersSource = Get-ChildItem -LiteralPath (Join-Path $cacheRoot "superpowers") -Directory -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1

    if (-not $superpowersSource) {
        Write-Result "openai-curated Superpowers cache not found; curated marketplace restore skipped."
        return
    }

    $pluginsDir = Join-Path $stableCuratedMarketplaceDir "plugins"
    $agentsDir = Join-Path $stableCuratedMarketplaceDir ".agents\plugins"
    New-Item -ItemType Directory -Force -Path $pluginsDir | Out-Null
    New-Item -ItemType Directory -Force -Path $agentsDir | Out-Null

    $superpowersTarget = Join-Path $pluginsDir "superpowers"
    Copy-DirectorySafe -Source $superpowersSource.FullName -Destination $superpowersTarget -AllowedRoot $pluginsDir

    $marketplace = [ordered]@{
        name = "openai-curated"
        interface = [ordered]@{ displayName = "OpenAI Curated" }
        plugins = @(
            [ordered]@{
                name = "superpowers"
                source = [ordered]@{ source = "local"; path = "./plugins/superpowers" }
                policy = [ordered]@{ installation = "AVAILABLE"; authentication = "ON_INSTALL" }
                category = "Developer Tools"
            }
        )
    }
    [System.IO.File]::WriteAllText(
        (Join-Path $agentsDir "marketplace.json"),
        ($marketplace | ConvertTo-Json -Depth 20),
        [System.Text.UTF8Encoding]::new($false)
    )
    Write-Result "Restored stable openai-curated marketplace with Superpowers: $stableCuratedMarketplaceDir"
}

function Update-CodexConfigMarketplaces {
    $configPath = Join-Path $env:USERPROFILE ".codex\config.toml"
    if (-not (Test-Path -LiteralPath $configPath)) {
        Write-Result "Codex config not found; marketplace config repair skipped: $configPath"
        return
    }

    Backup-File $configPath
    $text = Get-Content -LiteralPath $configPath -Raw
    $curatedSource = "\\?\$stableCuratedMarketplaceDir"
    $curatedBlock = @"
[marketplaces.openai-curated]
last_updated = "$(Get-Date -AsUTC -Format "yyyy-MM-ddTHH:mm:ssZ")"
source_type = "local"
source = '$curatedSource'
"@

    if ($text -match '(?ms)^\[marketplaces\.openai-curated\]\r?\n.*?(?=^\[|\z)') {
        $text = [regex]::Replace($text, '(?ms)^\[marketplaces\.openai-curated\]\r?\n.*?(?=^\[|\z)', $curatedBlock + "`r`n")
    } else {
        $insertAt = $text.IndexOf("[plugins.", [System.StringComparison]::OrdinalIgnoreCase)
        if ($insertAt -ge 0) {
            $text = $text.Insert($insertAt, $curatedBlock + "`r`n")
        } else {
            $text = $text.TrimEnd() + "`r`n`r`n" + $curatedBlock + "`r`n"
        }
    }

    if ($text.IndexOf('[plugins."superpowers@openai-curated"]', [System.StringComparison]::OrdinalIgnoreCase) -lt 0) {
        $text = $text.TrimEnd() + "`r`n`r`n[plugins.`"superpowers@openai-curated`"]`r`nenabled = true`r`n"
    } else {
        $text = [regex]::Replace(
            $text,
            '(?ms)^\[plugins\."superpowers@openai-curated"\]\r?\n.*?(?=^\[|\z)',
            "[plugins.`"superpowers@openai-curated`"]`r`nenabled = true`r`n"
        )
    }

    [System.IO.File]::WriteAllText($configPath, $text, [System.Text.UTF8Encoding]::new($false))
    Write-Result "Updated Codex marketplace config for openai-curated and Superpowers: $configPath"
}

function Get-CodexPlusDebugPort {
    $process = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
        $_.Name -eq "Codex.exe" -and
        $_.CommandLine -like "*codex-plus-profile*" -and
        $_.CommandLine -like "*--remote-debugging-port*"
    } | Select-Object -First 1

    if (-not $process) {
        return 0
    }

    $match = [regex]::Match($process.CommandLine, "--remote-debugging-port(?:=|\s+)(?<port>\d+)")
    if ($match.Success) {
        return [int]$match.Groups["port"].Value
    }

    return 0
}

function Update-LatestStatusFromRunningCodexPlus {
    $runningDebugPort = Get-CodexPlusDebugPort
    $runningHelperPort = 0
    $helperPorts = @(Get-CodexPlusHelperPorts)
    foreach ($port in $helperPorts) {
        $candidate = 0
        if (Test-CodexPlusBackend -ActiveHelperPort ([ref]$candidate)) {
            $runningHelperPort = $candidate
            break
        }
    }

    if ($runningDebugPort -gt 0 -and $runningHelperPort -gt 0) {
        $oldDebugPort = $script:debugPort
        $oldHelperPort = $script:helperPort
        $script:debugPort = $runningDebugPort
        $script:helperPort = $runningHelperPort
        if (Wait-DebugEndpoint -TimeoutSeconds 8) {
            Write-LatestStatus -ActiveHelperPort $runningHelperPort
        }
        $script:debugPort = $oldDebugPort
        $script:helperPort = $oldHelperPort
    }
}

function Install-CodexPlusWatchdogTask {
    $stableLauncherLiteral = $stableLauncherScript.Replace("'", "''")
    $realCodexPathLiteral = $realCodexPathFile.Replace("'", "''")
    $statusPathLiteral = $statusPath.Replace("'", "''")
    $bundledRootLiteral = $bundledMarketplaceRoot.Replace("'", "''")
    $stableBundledLiteral = $stableBundledMarketplaceDir.Replace("'", "''")
    $watchdog = @"
`$ErrorActionPreference = "SilentlyContinue"
`$bundledRoot = '$bundledRootLiteral'
`$stableBundled = '$stableBundledLiteral'
`$stableMarketplaceJson = Join-Path `$stableBundled ".agents\plugins\marketplace.json"
if (-not (Test-Path -LiteralPath `$stableMarketplaceJson)) {
    New-Item -ItemType Directory -Force -Path `$bundledRoot | Out-Null
    `$source = Get-ChildItem -LiteralPath `$bundledRoot -Directory |
        Where-Object { `$_.Name -like "openai-bundled.staging*" } |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
    if (`$source) {
        if (Test-Path -LiteralPath `$stableBundled) {
            Remove-Item -LiteralPath `$stableBundled -Recurse -Force
        }
        Copy-Item -LiteralPath `$source.FullName -Destination `$stableBundled -Recurse -Force
    }
}

`$package = Get-AppxPackage -Name "OpenAI.Codex" |
    Sort-Object Version -Descending |
    Select-Object -First 1
if (`$package) {
    `$codexExe = Join-Path `$package.InstallLocation "app\Codex.exe"
    if (Test-Path -LiteralPath `$codexExe) {
        [System.IO.File]::WriteAllText('$realCodexPathLiteral', `$codexExe, [System.Text.UTF8Encoding]::new(`$false))
    }
}

function Test-Url(`$url) {
    try {
        Invoke-WebRequest -UseBasicParsing -TimeoutSec 4 `$url | Out-Null
        return `$true
    } catch {
        return `$false
    }
}

function Get-CodexPlusDebugPort {
    `$proc = Get-CimInstance Win32_Process | Where-Object {
        `$_.Name -eq "Codex.exe" -and
        `$_.CommandLine -like "*codex-plus-profile*" -and
        `$_.CommandLine -like "*--remote-debugging-port*"
    } | Select-Object -First 1
    if (-not `$proc) { return 0 }
    `$match = [regex]::Match(`$proc.CommandLine, "--remote-debugging-port(?:=|\s+)(?<port>\d+)")
    if (`$match.Success) { return [int]`$match.Groups["port"].Value }
    return 0
}

function Get-CodexPlusHelperPorts {
    `$launcherIds = Get-CimInstance Win32_Process | Where-Object {
        `$_.Name -eq "codex-plus-plus.exe"
    } | Select-Object -ExpandProperty ProcessId
    if (-not `$launcherIds) { return @() }
    return @(Get-NetTCPConnection -State Listen | Where-Object {
        (`$launcherIds -contains `$_.OwningProcess) -and
        `$_.LocalPort -ne 57320
    } | Select-Object -ExpandProperty LocalPort -Unique)
}

function Update-LatestStatusFromRunningCodexPlus {
    `$debug = Get-CodexPlusDebugPort
    `$helper = 0
    foreach (`$port in (Get-CodexPlusHelperPorts)) {
        if (Test-Url "http://127.0.0.1:`$port/backend/status") {
            `$helper = `$port
            break
        }
    }
    if (`$debug -gt 0 -and `$helper -gt 0 -and (Test-Url "http://127.0.0.1:`$debug/json/version")) {
        `$status = [ordered]@{
            status = "running"
            message = "Codex++ launcher ready"
            started_at_ms = [int64]([DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds())
            debug_port = `$debug
            helper_port = `$helper
            codex_app = "C:\Users\DELL\.codex-session-delete\codex-plus-wrapper-app"
        }
        [System.IO.File]::WriteAllText('$statusPathLiteral', (`$status | ConvertTo-Json -Depth 10), [System.Text.UTF8Encoding]::new(`$false))
        return `$true
    }
    return `$false
}

if (-not (Update-LatestStatusFromRunningCodexPlus)) {
    Start-Process -FilePath "$env:WINDIR\System32\WindowsPowerShell\v1.0\powershell.exe" `
        -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", '$stableLauncherLiteral') `
        -WindowStyle Hidden
}
"@

    [System.IO.File]::WriteAllText($watchdogScript, $watchdog, [System.Text.UTF8Encoding]::new($false))
    Write-Result "Wrote Codex++ watchdog script: $watchdogScript"

    & "$env:WINDIR\System32\schtasks.exe" /Create /TN "Codex++ Watchdog" /SC MINUTE /MO 1 /RL LIMITED /F `
        /TR "`"$env:WINDIR\System32\WindowsPowerShell\v1.0\powershell.exe`" -NoProfile -ExecutionPolicy Bypass -File `"$watchdogScript`"" | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Result "Installed Codex++ watchdog task: Codex++ Watchdog"
    } else {
        Write-Result "Could not install Codex++ watchdog task; schtasks exit code $LASTEXITCODE"
    }
}

function Remove-CodexPlusWatchdogTask {
    & "$env:WINDIR\System32\schtasks.exe" /End /TN "Codex++ Watchdog" 2>$null | Out-Null
    & "$env:WINDIR\System32\schtasks.exe" /Delete /TN "Codex++ Watchdog" /F 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Result "Removed Codex++ watchdog task after successful verification."
    } else {
        Write-Result "Codex++ watchdog task was not present or could not be removed; schtasks exit code $LASTEXITCODE"
    }
}

function Write-CodexPlusSettings {
    param([string]$Path, [string]$CodexAppDir)

    $dir = Split-Path $Path
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
    Backup-File $Path

    # Codex++ needs a separate profile so it can open even when normal Codex is
    # already running; the launcher keeps that profile synced before startup.
    $settings = [ordered]@{
        codexAppPath = $CodexAppDir
        codexExtraArgs = @("--user-data-dir=$plusProfile")
        enhancementsEnabled = $true
        providerSyncEnabled = $false
        debugPort = $debugPort
        helperPort = $helperPort
    }
    $json = $settings | ConvertTo-Json -Depth 20
    [System.IO.File]::WriteAllText($Path, $json, [System.Text.UTF8Encoding]::new($false))
    Write-Result "Wrote stable Codex++ settings: $Path"
}

function Get-CodexAppDir {
    $appxPackage = Get-AppxPackage -Name "OpenAI.Codex" -ErrorAction SilentlyContinue |
        Sort-Object Version -Descending |
        Select-Object -First 1

    if ($appxPackage -and $appxPackage.InstallLocation) {
        $appDir = Join-Path $appxPackage.InstallLocation "app"
        $appExe = Join-Path $appDir "Codex.exe"
        if (Test-Path -LiteralPath $appExe) {
            return $appDir
        }
    }

    if (Test-Path -LiteralPath $realCodexPathFile) {
        $realCodexExe = (Get-Content -LiteralPath $realCodexPathFile -Raw).Trim()
        if ($realCodexExe -and (Test-Path -LiteralPath $realCodexExe)) {
            return (Split-Path $realCodexExe)
        }
    }

    $codexProcess = Get-CimInstance Win32_Process | Where-Object {
        $_.Name -eq "Codex.exe" -and
        $_.ExecutablePath -like "*\WindowsApps\OpenAI.Codex_*"
    } | Select-Object -First 1

    if ($codexProcess -and $codexProcess.ExecutablePath) {
        return (Split-Path $codexProcess.ExecutablePath)
    }

    return ""
}

function Get-NormalCodexProfileDir {
    $appxPackage = Get-AppxPackage -Name "OpenAI.Codex" -ErrorAction SilentlyContinue |
        Sort-Object Version -Descending |
        Select-Object -First 1

    if ($appxPackage -and $appxPackage.PackageFamilyName) {
        $profile = Join-Path $env:LOCALAPPDATA "Packages\$($appxPackage.PackageFamilyName)\LocalCache\Roaming\Codex\web\Codex"
        if (Test-Path -LiteralPath $profile) {
            return $profile
        }
    }

    $fallbacks = @(
        (Join-Path $env:APPDATA "Codex\web\Codex"),
        (Join-Path $env:LOCALAPPDATA "Codex\web\Codex")
    )

    foreach ($profile in $fallbacks) {
        if (Test-Path -LiteralPath $profile) {
            return $profile
        }
    }

    return ""
}

function Get-NormalCodexCookiesPath {
    $sourceProfile = Get-NormalCodexProfileDir
    if (-not $sourceProfile) {
        return ""
    }

    return (Join-Path $sourceProfile "Default\Network\Cookies")
}

function Test-FileReadable {
    param([string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        return $true
    }

    try {
        $stream = [System.IO.File]::Open(
            $Path,
            [System.IO.FileMode]::Open,
            [System.IO.FileAccess]::Read,
            [System.IO.FileShare]::ReadWrite
        )
        $stream.Dispose()
        return $true
    } catch {
        return $false
    }
}

function Test-NormalCodexCookiesLocked {
    $sourceCookies = Get-NormalCodexCookiesPath
    if (-not $sourceCookies) {
        return $false
    }

    return (-not (Test-FileReadable -Path $sourceCookies))
}

function Wait-NormalCodexCookiesUnlocked {
    param([int]$TimeoutSeconds = 43200)

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (-not (Test-NormalCodexCookiesLocked)) {
            return $true
        }
        Start-Sleep -Seconds 10
    }

    return $false
}

function Start-DeferredProfileSync {
    if ($deferredMode) {
        return
    }

    if (Test-Path -LiteralPath $deferredSyncPidFile) {
        $existingPidText = (Get-Content -LiteralPath $deferredSyncPidFile -Raw -ErrorAction SilentlyContinue).Trim()
        $existingPid = 0
        if ([int]::TryParse($existingPidText, [ref]$existingPid)) {
            $existing = Get-CimInstance Win32_Process -Filter "ProcessId=$existingPid" -ErrorAction SilentlyContinue
            if ($existing) {
                Write-Result "Deferred profile sync watcher already running: pid=$existingPid"
                return
            }
        }
    }

    $stableScriptLiteral = $stableLauncherScript.Replace("'", "''")
    $helper = @"
`$ErrorActionPreference = "Stop"
try {
    & '$stableScriptLiteral' --deferred-sync
} finally {
    Remove-Item -LiteralPath '$($deferredSyncPidFile.Replace("'", "''"))' -Force -ErrorAction SilentlyContinue
}
"@
    [System.IO.File]::WriteAllText($deferredSyncScript, $helper, [System.Text.UTF8Encoding]::new($false))
    $proc = Start-Process -FilePath "$env:WINDIR\System32\WindowsPowerShell\v1.0\powershell.exe" `
        -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $deferredSyncScript) `
        -WorkingDirectory $stateDir `
        -WindowStyle Hidden `
        -PassThru
    [System.IO.File]::WriteAllText($deferredSyncPidFile, "$($proc.Id)", [System.Text.UTF8Encoding]::new($false))
    Write-Result "Started deferred Codex++ profile sync watcher: pid=$($proc.Id)"
}

function Sync-CodexProfile {
    param([switch]$Deferred, [switch]$Force)

    $sourceProfile = Get-NormalCodexProfileDir
    if (-not $sourceProfile) {
        Write-Result "Normal Codex profile not found; keeping existing Codex++ profile."
        return
    }

    $resolvedStateDir = [System.IO.Path]::GetFullPath($stateDir).TrimEnd('\')
    $resolvedPlusProfile = [System.IO.Path]::GetFullPath($plusProfile).TrimEnd('\')
    if (-not $resolvedPlusProfile.StartsWith("$resolvedStateDir\", [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to sync Codex++ profile outside state directory: $resolvedPlusProfile"
    }

    $sourceCookies = Join-Path $sourceProfile "Default\Network\Cookies"
    $sourceCookiesLocked = (Test-Path -LiteralPath $sourceCookies) -and (-not (Test-FileReadable -Path $sourceCookies))
    if ($sourceCookiesLocked -and (-not $Force) -and (Test-Path -LiteralPath $plusProfile)) {
        Write-Result "Using existing Codex++ profile while normal Codex cookies are locked."
        Start-DeferredProfileSync
        return
    }

    $previousProfile = "$plusProfile.previous"
    if (Test-Path -LiteralPath $previousProfile) {
        Remove-Item -LiteralPath $previousProfile -Recurse -Force
    }
    if (Test-Path -LiteralPath $plusProfile) {
        Move-Item -LiteralPath $plusProfile -Destination $previousProfile -Force
    }
    New-Item -ItemType Directory -Force -Path $plusProfile | Out-Null

    $excludeDirs = @(
        "BrowserMetrics",
        "Crashpad",
        "DeferredBrowserMetrics",
        "GPUPersistentCache",
        "GrShaderCache",
        "ShaderCache"
    )
    $excludeFiles = @(
        "lockfile",
        "LOCK",
        "SingletonCookie",
        "SingletonLock",
        "SingletonSocket",
        "*.tmp"
    )

    & robocopy $sourceProfile $plusProfile /E /R:1 /W:1 /NFL /NDL /NP /XD $excludeDirs /XF $excludeFiles | Out-Null
    $copyExitCode = $LASTEXITCODE
    if ($copyExitCode -ge 8) {
        Write-Result "Profile sync had locked files; robocopy exit code $copyExitCode"
        if (-not $Force) {
            Start-DeferredProfileSync
        }
    }

    $criticalFiles = @(
        "Default\Network\Cookies",
        "Default\Network\Cookies-journal",
        "Default\Local Storage\leveldb\CURRENT",
        "Default\Local Storage\leveldb\LOG"
    )

    foreach ($relativePath in $criticalFiles) {
        $targetFile = Join-Path $plusProfile $relativePath
        $previousFile = Join-Path $previousProfile $relativePath
        if ((-not (Test-Path -LiteralPath $targetFile)) -and (Test-Path -LiteralPath $previousFile)) {
            $targetDir = Split-Path $targetFile
            New-Item -ItemType Directory -Force -Path $targetDir | Out-Null
            Copy-Item -LiteralPath $previousFile -Destination $targetFile -Force -ErrorAction SilentlyContinue
            Write-Result "Restored locked profile file from previous Codex++ profile: $relativePath"
        }
    }

    $targetCookies = Join-Path $plusProfile "Default\Network\Cookies"
    if ((Test-Path -LiteralPath $sourceCookies) -and (-not (Test-Path -LiteralPath $targetCookies))) {
        Write-Result "Codex cookies are locked by the running normal Codex app; keeping Codex++ usable and deferring full account sync."
        if (-not $Force) {
            Start-DeferredProfileSync
        }
    }

    Write-Result "Synced normal Codex profile to Codex++ profile: $plusProfile"
}

function Write-RealCodexPathFile {
    param([string]$CodexAppDir)

    $realCodexExe = Join-Path $CodexAppDir "Codex.exe"
    if (-not (Test-Path -LiteralPath $realCodexExe)) {
        Write-Result "Real Codex executable not found: $realCodexExe"
        return
    }

    $dir = Split-Path $realCodexPathFile
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
    Backup-File $realCodexPathFile
    [System.IO.File]::WriteAllText($realCodexPathFile, $realCodexExe, [System.Text.UTF8Encoding]::new($false))
    Write-Result "Updated wrapper real Codex path: $realCodexPathFile"
}

function Install-StableLauncherScript {
    if (-not $PSCommandPath) {
        return
    }

    $currentScript = [System.IO.Path]::GetFullPath($PSCommandPath)
    $stableScript = [System.IO.Path]::GetFullPath($stableLauncherScript)
    if (-not [string]::Equals($currentScript, $stableScript, [System.StringComparison]::OrdinalIgnoreCase)) {
        Copy-Item -LiteralPath $currentScript -Destination $stableLauncherScript -Force
        Write-Result "Installed stable self-healing launcher: $stableLauncherScript"
    }
}

function Stop-CodexPlusProcess {
    param([int]$TargetProcessId, [string]$Reason)

    if ($TargetProcessId -le 0 -or $TargetProcessId -eq $PID) {
        return
    }
    try {
        $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$TargetProcessId" -ErrorAction SilentlyContinue
        if (-not $proc) {
            return
        }
        Write-Result "Stopping pid=$TargetProcessId name=$($proc.Name) reason=$Reason"
        Stop-Process -Id $TargetProcessId -Force -ErrorAction SilentlyContinue
    } catch {
        Write-Result "Could not stop pid=$TargetProcessId reason=$Reason error=$($_.Exception.Message)"
    }
}

function Stop-CodexPlusFleet {
    $profileMarker = Join-Path $stateDir "codex-plus-profile"
    $wrapperMarker = Join-Path $stateDir "codex-plus-wrapper-app"

    $processes = Get-CimInstance Win32_Process | Where-Object {
        ($_.Name -in @("codex-plus-plus.exe", "codex-plus-plus-manager.exe")) -or
        ($_.CommandLine -like "*--remote-debugging-port=$debugPort*") -or
        ($_.CommandLine -like "*--remote-debugging-port $debugPort*") -or
        ($_.CommandLine -like "*$profileMarker*") -or
        ($_.ExecutablePath -like "$wrapperMarker*")
    }

    foreach ($process in $processes) {
        Stop-CodexPlusProcess -TargetProcessId $process.ProcessId -Reason "Codex++ fleet cleanup"
    }

    foreach ($port in @($helperPort, $debugPort)) {
        $owners = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue |
            Select-Object -ExpandProperty OwningProcess -Unique
        foreach ($owner in $owners) {
            Stop-CodexPlusProcess -TargetProcessId $owner -Reason "port $port cleanup"
        }
    }
}

function Update-Shortcuts {
    $shortcutPaths = @(
        (Join-Path $desktop "Codex++.lnk"),
        (Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Codex++\Codex++.lnk")
    )

    $shell = New-Object -ComObject WScript.Shell
    foreach ($path in $shortcutPaths) {
        $dir = Split-Path $path
        New-Item -ItemType Directory -Force -Path $dir | Out-Null
        $shortcut = $shell.CreateShortcut($path)
        $shortcut.TargetPath = "$env:WINDIR\System32\WindowsPowerShell\v1.0\powershell.exe"
        $shortcut.Arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$stableLauncherScript`""
        $shortcut.WorkingDirectory = $stateDir
        $shortcut.IconLocation = "$launcher,0"
        $shortcut.Save()
        Write-Result "Updated shortcut: $path"
    }

    $managerShortcutRoots = @(
        $desktop,
        (Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Codex++")
    )
    foreach ($root in $managerShortcutRoots) {
        if (-not (Test-Path -LiteralPath $root)) {
            continue
        }
        $links = Get-ChildItem -LiteralPath $root -Filter "*.lnk" -ErrorAction SilentlyContinue
        foreach ($link in $links) {
            $existing = $shell.CreateShortcut($link.FullName)
            if ($existing.TargetPath -ne $manager) {
                continue
            }
            $shortcut = $shell.CreateShortcut($link.FullName)
            $shortcut.TargetPath = $manager
            $shortcut.Arguments = ""
            $shortcut.WorkingDirectory = $installDir
            $shortcut.IconLocation = "$manager,0"
            $shortcut.Save()
            Write-Result "Updated manager shortcut: $($link.FullName)"
        }
    }
}

function Test-Http {
    param([string]$Url)
    try {
        $response = Invoke-WebRequest -UseBasicParsing -TimeoutSec 4 $Url
        $content = $response.Content
        if ($content.Length -gt 500) {
            $content = $content.Substring(0, 500)
        }
        Write-Result "$Url OK $($response.StatusCode) $content"
        return $true
    } catch {
        Write-Result "$Url ERROR $($_.Exception.Message)"
        return $false
    }
}

function Wait-DebugEndpoint {
    param([int]$TimeoutSeconds = 20)

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-Http "http://127.0.0.1:$debugPort/json/version") {
            return $true
        }
        Start-Sleep -Seconds 2
    }

    return $false
}

function Write-LatestStatus {
    param([string]$Message = "Codex++ launcher ready", [int]$ActiveHelperPort = $helperPort)

    $status = [ordered]@{
        status = "running"
        message = $Message
        started_at_ms = [int64]([DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds())
        debug_port = $debugPort
        helper_port = $ActiveHelperPort
        codex_app = $wrapperAppDir
    }
    $json = $status | ConvertTo-Json -Depth 10
    [System.IO.File]::WriteAllText($statusPath, $json, [System.Text.UTF8Encoding]::new($false))
    Write-Result "Wrote latest status file: $statusPath"
}

function Start-DirectCodexAppFallback {
    $realCodexExe = ""
    if (Test-Path -LiteralPath $realCodexPathFile) {
        $realCodexExe = (Get-Content -LiteralPath $realCodexPathFile -Raw).Trim()
    }

    if (-not $realCodexExe) {
        $codexAppDir = Get-CodexAppDir
        if ($codexAppDir) {
            $realCodexExe = Join-Path $codexAppDir "Codex.exe"
        }
    }

    if (-not ($realCodexExe -and (Test-Path -LiteralPath $realCodexExe))) {
        Write-Result "Direct Codex fallback skipped; real Codex executable not found."
        return $false
    }

    Write-Result "Starting direct Codex fallback on debug=$debugPort profile=$plusProfile"
    Start-Process -FilePath $realCodexExe `
        -ArgumentList @(
            "--remote-debugging-port=$debugPort",
            "--remote-allow-origins=http://127.0.0.1:$debugPort",
            "--user-data-dir=$plusProfile"
        ) `
        -WorkingDirectory (Split-Path $realCodexExe) `
        -WindowStyle Hidden
    return $true
}

function Start-CodexPlusLauncherAndVerify {
    Write-Result "Starting Codex++ launcher on debug=$debugPort helper=$helperPort"
    try {
        Start-Process -FilePath $launcher `
            -ArgumentList @("--debug-port", "$debugPort", "--helper-port", "$helperPort") `
            -WorkingDirectory $installDir `
            -WindowStyle Hidden
    } catch {
        Write-Result "Codex++ launcher start failed: $($_.Exception.Message)"
        Start-DirectCodexAppFallback | Out-Null
    }

    $deadline = (Get-Date).AddSeconds(90)
    $backendOk = $false
    $debugOk = $false
    $activeHelperPort = $helperPort
    while ((Get-Date) -lt $deadline -and (-not ($backendOk -and $debugOk))) {
        Start-Sleep -Seconds 2
        if (-not $backendOk) {
            $backendOk = Test-CodexPlusBackend -ActiveHelperPort ([ref]$activeHelperPort)
        }
        if (-not $debugOk) {
            $debugOk = Test-Http "http://127.0.0.1:$debugPort/json/version"
        }
    }

    if (-not $debugOk) {
        Write-Result "Debug endpoint is still unavailable; trying direct Codex fallback."
        if (Start-DirectCodexAppFallback) {
            $deadline = (Get-Date).AddSeconds(60)
            while ((Get-Date) -lt $deadline -and (-not $debugOk)) {
                Start-Sleep -Seconds 2
                $debugOk = Test-Http "http://127.0.0.1:$debugPort/json/version"
            }
        }
    }

    if ($backendOk -and $debugOk) {
        Start-Sleep -Seconds 8
        $stableHelperPort = $activeHelperPort
        if (Test-CodexPlusBackend -ActiveHelperPort ([ref]$stableHelperPort)) {
            $activeHelperPort = $stableHelperPort
        }
        $debugOk = Wait-DebugEndpoint -TimeoutSeconds 45
    }

    if ($backendOk -and $debugOk) {
        Write-LatestStatus -ActiveHelperPort $activeHelperPort
    }

    if (Test-Path -LiteralPath $statusPath) {
        Write-Result "Status file:"
        (Get-Content -LiteralPath $statusPath -Raw) -split "`r?`n" | ForEach-Object {
            if ($_) { Write-Result "  $_" }
        }
    }

    if (-not ($backendOk -and $debugOk)) {
        Update-LatestStatusFromRunningCodexPlus
        $activeHelperPort = $helperPort
        $backendOk = Test-CodexPlusBackend -ActiveHelperPort ([ref]$activeHelperPort)
        $debugOk = Wait-DebugEndpoint -TimeoutSeconds 15
        if ($backendOk -and $debugOk) {
            Write-LatestStatus -ActiveHelperPort $activeHelperPort
        }
    }

    return ($backendOk -and $debugOk)
}

if ($deferredMode) {
    Add-Content -LiteralPath $resultPath -Value "Codex++ deferred profile sync" -Encoding UTF8
} else {
    Set-Content -LiteralPath $resultPath -Value "Codex++ permanent repair" -Encoding UTF8
}
Write-Result "Starting permanent repair"

if (-not (Test-Path -LiteralPath $launcher)) {
    Write-Result "Launcher not found: $launcher"
    exit 1
}

New-Item -ItemType Directory -Force -Path $stateDir | Out-Null
$codexAppDir = Get-CodexAppDir
if (-not $codexAppDir) {
    Write-Result "Could not resolve Codex app directory"
    exit 1
}
Write-Result "Resolved Codex app directory: $codexAppDir"
$helperPort = Resolve-HelperPort
Write-Result "Using Codex++ helper port: $helperPort"
Install-StableLauncherScript
Write-CodexPlusSettings -Path (Join-Path $env:APPDATA "Codex++\settings.json") -CodexAppDir $wrapperAppDir
Write-CodexPlusSettings -Path (Join-Path $stateDir "settings.json") -CodexAppDir $wrapperAppDir
Write-RealCodexPathFile -CodexAppDir $codexAppDir
Install-StableBundledMarketplace
Install-StableCuratedMarketplace
Update-CodexConfigMarketplaces
Remove-CodexPathRefreshTask
Remove-CodexPlusWatchdogTask

if ($deferredMode) {
    Write-Result "Deferred profile sync watcher is waiting for normal Codex cookies to unlock."
    if (-not (Wait-NormalCodexCookiesUnlocked)) {
        Write-Result "Deferred profile sync timed out while waiting for normal Codex cookies."
        exit 3
    }
    Write-Result "Normal Codex cookies unlocked; syncing and restarting Codex++."
    Stop-CodexPlusFleet
    Sync-CodexProfile -Deferred -Force
    Update-Shortcuts
    Start-Sleep -Seconds 2
    if (Start-CodexPlusLauncherAndVerify) {
        Write-Result "Deferred profile sync verified: Codex++ restarted with synced profile."
        Remove-CodexPlusWatchdogTask
        exit 0
    }
    Write-Result "Deferred profile sync failed verification. Last log lines:"
    if (Test-Path -LiteralPath $logPath) {
        Get-Content -LiteralPath $logPath -Tail 40 | ForEach-Object { Write-Result "  $_" }
    }
    exit 2
}

if (Test-Path -LiteralPath $statusPath) {
    Backup-File $statusPath
    Remove-Item -LiteralPath $statusPath -Force
    Write-Result "Removed stale status file: $statusPath"
}

Stop-CodexPlusFleet
Sync-CodexProfile
Update-Shortcuts
Start-Sleep -Seconds 3

if (Start-CodexPlusLauncherAndVerify) {
    Write-Result "Repair verified: Codex++ backend and debug endpoint are both reachable."
    Remove-CodexPlusWatchdogTask
    exit 0
}

Write-Result "Repair failed verification. Last log lines:"
if (Test-Path -LiteralPath $logPath) {
    Get-Content -LiteralPath $logPath -Tail 40 | ForEach-Object { Write-Result "  $_" }
}
exit 2
