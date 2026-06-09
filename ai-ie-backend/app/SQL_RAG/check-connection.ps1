$ErrorActionPreference = "Stop"

$composeFile = Join-Path $PSScriptRoot "docker-compose.yml"
$envFile = Join-Path $PSScriptRoot ".env"
$envValues = @{}

$dockerInfo = Start-Job -ScriptBlock {
    docker info *> $null
    $LASTEXITCODE
}

if (-not (Wait-Job $dockerInfo -Timeout 10)) {
    Stop-Job $dockerInfo
    Remove-Job $dockerInfo -Force
    throw "Docker daemon check timed out. Start Docker Desktop, then rerun this script."
}

$dockerExitCode = Receive-Job $dockerInfo
Remove-Job $dockerInfo

if ($dockerExitCode -ne 0) {
    throw "Docker daemon is not running. Start Docker Desktop, then rerun this script."
}

Get-Content -LiteralPath $envFile | ForEach-Object {
    if ($_ -match "^\s*#" -or $_ -notmatch "=") {
        return
    }

    $key, $value = $_ -split "=", 2
    $envValues[$key.Trim()] = $value.Trim()
}

docker compose --env-file $envFile -f $composeFile up -d

$maxAttempts = 60
for ($attempt = 1; $attempt -le $maxAttempts; $attempt++) {
    $status = docker inspect --format "{{.State.Health.Status}}" sql-rag-sqlserver-2022 2>$null
    if ($status -eq "healthy") {
        break
    }
    Start-Sleep -Seconds 2
}

if ($status -ne "healthy") {
    throw "SQL Server container did not become healthy. Current status: $status"
}

docker compose --env-file $envFile -f $composeFile run --rm init-db

docker exec `
    -e APP_DB_NAME="$($envValues["APP_DB_NAME"])" `
    -e APP_DB_USER="$($envValues["APP_DB_USER"])" `
    -e APP_DB_PASSWORD="$($envValues["APP_DB_PASSWORD"])" `
    sql-rag-sqlserver-2022 `
    /opt/mssql-tools18/bin/sqlcmd `
    -S localhost `
    -U "$($envValues["APP_DB_USER"])" `
    -P "$($envValues["APP_DB_PASSWORD"])" `
    -C `
    -d "$($envValues["APP_DB_NAME"])" `
    -Q "SELECT DB_NAME() AS database_name, SUSER_SNAME() AS login_name"
