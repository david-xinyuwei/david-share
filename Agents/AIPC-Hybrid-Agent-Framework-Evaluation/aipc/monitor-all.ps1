# monitor-all.ps1 - AIPC Full Stack Monitor
# Demo: RDP to AIPC, right-click Run with PowerShell
$appDir = if ($env:AIPC_APP_DIR) { $env:AIPC_APP_DIR } else { [Environment]::GetFolderPath([Environment+SpecialFolder]::Desktop) }
$ollama = if ($env:OLLAMA_EXE) { $env:OLLAMA_EXE } else { Join-Path $env:USERPROFILE "ollama\ollama.exe" }
$host.UI.RawUI.WindowTitle = "AIPC Full Stack Monitor"
$proofVisibleSeconds = 30

function Test-RecentTimestamp {
    param(
        [string]$TimestampUtc,
        [int]$VisibleSeconds = $proofVisibleSeconds
    )
    try {
        if (-not $TimestampUtc) { return $false }
        $ts = ([DateTime]::Parse($TimestampUtc)).ToUniversalTime()
        return (((Get-Date).ToUniversalTime() - $ts).TotalSeconds -le $VisibleSeconds)
    } catch {
        return $false
    }
}

while ($true) {
    Clear-Host
    $now = Get-Date -Format 'HH:mm:ss'

    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host "  AIPC FULL STACK MONITOR                          $now" -ForegroundColor Cyan
    Write-Host "============================================================" -ForegroundColor Cyan

    # -- Ollama --
    Write-Host ""
    Write-Host "  -- OLLAMA (Local Model) ----------------------------------" -ForegroundColor Yellow
    $proc = Get-Process ollama -ErrorAction SilentlyContinue
    if ($proc) {
        $procInfo = Get-CimInstance Win32_Process -Filter "Name='ollama.exe'" -ErrorAction SilentlyContinue | Select-Object -First 1
        $mem = [math]::Round($proc.WorkingSet64 / 1MB, 0)
        Write-Host "     Service: " -NoNewline -ForegroundColor Gray
        Write-Host "READY" -NoNewline -ForegroundColor Green
        Write-Host "  PID=$($proc.Id)  RAM=${mem}MB" -ForegroundColor Gray
        if ($procInfo) {
            Write-Host "     Session: Services / Session $($procInfo.SessionId)" -ForegroundColor DarkGray
            Write-Host "     TaskMgr: open Details tab and search ollama.exe" -ForegroundColor DarkGray
        }
    } else {
        Write-Host "     Service: " -NoNewline -ForegroundColor Gray
        Write-Host "STOPPED" -ForegroundColor Red
    }

    # API health
    try {
        $api = curl.exe -s --max-time 2 http://127.0.0.1:11434/ 2>$null
        Write-Host "     API:    " -NoNewline -ForegroundColor Gray
        if ($api -match "Ollama is running") {
            Write-Host "READY" -NoNewline -ForegroundColor Green
            Write-Host "  http://127.0.0.1:11434" -ForegroundColor DarkGray
        } else {
            Write-Host "NO RESPONSE" -ForegroundColor Red
        }
    } catch {
        Write-Host "     API:    " -NoNewline -ForegroundColor Gray
        Write-Host "UNREACHABLE" -ForegroundColor Red
    }

    # Scheduled task status
    try {
        $taskStatus = (schtasks.exe /Query /TN OllamaServe /FO LIST 2>$null | Where-Object { $_ -match "^Status:" }) -replace "Status:\s*", ""
        if ($taskStatus) {
            Write-Host "     Startup: Scheduled Task OllamaServe = $taskStatus" -ForegroundColor DarkGray
        }
    } catch {}

    # Active inference: service can be READY while no model is currently generating.
    $ollamaActive = $false
    try {
        $raw = curl.exe -s --max-time 3 http://127.0.0.1:11434/api/ps 2>$null
        if ($raw) {
            $ps = $raw | ConvertFrom-Json
            if ($ps.models -and $ps.models.Count -gt 0) {
                $ollamaActive = $true
                foreach ($m in $ps.models) {
                    $sz = [math]::Round($m.size / 1GB, 2)
                    Write-Host "     Active Inference: " -NoNewline -ForegroundColor Gray
                    Write-Host "ACTIVE" -NoNewline -ForegroundColor Green
                    Write-Host "  model=$($m.name) size=$($sz)GB" -ForegroundColor DarkGray
                }
            } else {
                Write-Host "     Active Inference: IDLE (no active generation)" -ForegroundColor DarkGray
            }
        } else {
            Write-Host "     Active Inference: (API no response)" -ForegroundColor DarkGray
        }
    } catch {
        Write-Host "     Active Inference: (error: $($_.Exception.Message))" -ForegroundColor DarkGray
    }

    # Installed models
    try {
        $tagsRaw = curl.exe -s --max-time 3 http://127.0.0.1:11434/api/tags 2>$null
        $tags = $tagsRaw | ConvertFrom-Json
        $names = ($tags.models | ForEach-Object { "$($_.name) ($($_.details.parameter_size))" }) -join ", "
        Write-Host "     Installed: $names" -ForegroundColor DarkGray
    } catch {}

    # Last code generation by Ollama (evidence that local model is generating code)
    $lastCodegen = Join-Path $appDir "last_ollama_codegen.json"
    if (Test-Path $lastCodegen) {
        try {
            $cg = Get-Content $lastCodegen -Raw | ConvertFrom-Json
            $cgRecent = Test-RecentTimestamp $cg.timestamp_utc
            Write-Host "     ---- Last Code Generation ----" -ForegroundColor Yellow
            Write-Host "     Model:  " -NoNewline -ForegroundColor Gray
            Write-Host "$($cg.model)" -NoNewline -ForegroundColor Green
            Write-Host "  gen_time=$($cg.gen_time_s)s  at=$($cg.timestamp_utc)" -ForegroundColor DarkGray
            if ($cgRecent) {
                Write-Host "     Active Run: " -NoNewline -ForegroundColor Gray
                Write-Host "RECENT CODEGEN" -NoNewline -ForegroundColor Green
                Write-Host "  gen_time=$($cg.gen_time_s)s" -ForegroundColor DarkGray
            }
            if ($cg.success) {
                Write-Host "     Result: " -NoNewline -ForegroundColor Gray
                Write-Host "SUCCESS" -ForegroundColor Green
            } else {
                Write-Host "     Result: " -NoNewline -ForegroundColor Gray
                Write-Host "FAILED" -ForegroundColor Red
            }
            if ($cgRecent) {
                Write-Host "     Prompt:" -ForegroundColor Gray
                $promptLines = ($cg.prompt_preview -split "`n" | Select-Object -First 3)
                foreach ($pl in $promptLines) {
                    Write-Host "       $($pl.Substring(0, [math]::Min($pl.Length, 90)))" -ForegroundColor DarkGray
                }
                if ($cg.generated_code) {
                    Write-Host "     Code:" -ForegroundColor Gray
                    ($cg.generated_code -split "`n" | Select-Object -First 8) | ForEach-Object {
                        Write-Host "       $_" -ForegroundColor Cyan
                    }
                }
            } else {
                Write-Host "     Detail: hidden until next code generation (last run is older than ${proofVisibleSeconds}s)" -ForegroundColor DarkGray
            }
        } catch {
            Write-Host "     Codegen: unable to parse last_ollama_codegen.json" -ForegroundColor DarkGray
        }
    }
    Write-Host "  --------------------------------------------------------------" -ForegroundColor Yellow

    # -- Hyperlight Sandbox --
    Write-Host ""
    Write-Host "  -- HYPERLIGHT (Sandbox Runtime) ------------------------------" -ForegroundColor Magenta
    try {
        $port = Get-NetTCPConnection -LocalPort 8507 -State Listen -ErrorAction SilentlyContinue
        if ($port) {
            Write-Host "     Service: " -NoNewline -ForegroundColor Gray
            Write-Host "READY" -NoNewline -ForegroundColor Green
            Write-Host "  PID=$($port.OwningProcess)  port=8507" -ForegroundColor Gray
        } else {
            Write-Host "     Service: " -NoNewline -ForegroundColor Gray
            Write-Host "OFFLINE" -ForegroundColor Red
        }
    } catch {
        Write-Host "     Service: " -NoNewline -ForegroundColor Gray
        Write-Host "OFFLINE" -ForegroundColor Red
    }

    $activeRunShown = $false

    $lastCodeAct = Join-Path $appDir "last_codeact_run.json"
    if (Test-Path $lastCodeAct) {
        try {
            $ca = Get-Content $lastCodeAct -Raw | ConvertFrom-Json
            $caRecent = Test-RecentTimestamp $ca.timestamp_utc
            if ($caRecent) {
                $activeRunShown = $true
                Write-Host "     Active Run: " -NoNewline -ForegroundColor Gray
                if ($ca.success) { Write-Host "CODEACT SUCCESS" -NoNewline -ForegroundColor Green } else { Write-Host "CODEACT FAILED" -NoNewline -ForegroundColor Red }
                Write-Host "  provider=$($ca.provider)  elapsed_s=$($ca.elapsed_s)" -ForegroundColor DarkGray
                if ($ca.query) { Write-Host "     Query:  $($ca.query.Substring(0, [math]::Min($ca.query.Length, 90)))" -ForegroundColor DarkGray }
                if ($ca.result) { Write-Host "     Result: $($ca.result.Substring(0, [math]::Min($ca.result.Length, 90)))" -ForegroundColor Green }
            }
        } catch {
            Write-Host "     CodeAct: unable to parse last_codeact_run.json" -ForegroundColor DarkGray
        }
    }

    $lastRun = Join-Path $appDir "last_sandbox_run.json"
    if (Test-Path $lastRun) {
        try {
            $lr = Get-Content $lastRun -Raw | ConvertFrom-Json
            $lrRecent = Test-RecentTimestamp $lr.timestamp_utc
            if ($lrRecent) {
                $activeRunShown = $true
                Write-Host "     Active Run: " -NoNewline -ForegroundColor Gray
                if ($lr.success) { Write-Host "SANDBOX SUCCESS" -NoNewline -ForegroundColor Green } else { Write-Host "SANDBOX FAILED" -NoNewline -ForegroundColor Red }
                Write-Host "  exec_ms=$($lr.exec_ms)  at=$($lr.timestamp_utc)" -ForegroundColor DarkGray
            }

            Write-Host "     Last Completed: " -NoNewline -ForegroundColor Gray
            if ($lr.success) { Write-Host "SUCCESS" -NoNewline -ForegroundColor Green } else { Write-Host "FAILED" -NoNewline -ForegroundColor Red }
            Write-Host "  exec_ms=$($lr.exec_ms)  at=$($lr.timestamp_utc)" -ForegroundColor DarkGray

            if ($lrRecent) {
                Write-Host "     Code:" -ForegroundColor Gray
                ($lr.code -split "`n" | Select-Object -First 6) | ForEach-Object {
                    Write-Host "       $_" -ForegroundColor DarkGray
                }

                if ($lr.stdout) {
                    Write-Host "     Stdout:" -ForegroundColor Gray
                    ($lr.stdout -split "`n" | Where-Object { $_ -ne "" } | Select-Object -First 8) | ForEach-Object {
                        Write-Host "       $_" -ForegroundColor Green
                    }
                }
                if ($lr.stderr) {
                    Write-Host "     Stderr:" -ForegroundColor Gray
                    ($lr.stderr -split "`n" | Where-Object { $_ -ne "" } | Select-Object -First 4) | ForEach-Object {
                        Write-Host "       $_" -ForegroundColor Red
                    }
                }
            } else {
                Write-Host "     Detail: hidden until next sandbox execution (last run is older than ${proofVisibleSeconds}s)" -ForegroundColor DarkGray
            }
        } catch {
            Write-Host "     LastRun: unable to parse last_sandbox_run.json" -ForegroundColor DarkGray
        }
    } else {
        Write-Host "     Last Completed: (no sandbox execution recorded yet)" -ForegroundColor DarkGray
    }
    if (-not $activeRunShown) {
        Write-Host "     Active Run: IDLE (waiting for next portal task)" -ForegroundColor DarkGray
    }
    Write-Host "  --------------------------------------------------------------" -ForegroundColor Magenta

    # -- System --
    Write-Host ""
    Write-Host "  -- SYSTEM ----------------------------------------------------" -ForegroundColor DarkCyan
    $os = Get-CimInstance Win32_OperatingSystem
    $totalGB = [math]::Round($os.TotalVisibleMemorySize / 1MB, 1)
    $freeGB = [math]::Round($os.FreePhysicalMemory / 1MB, 1)
    $usedGB = [math]::Round($totalGB - $freeGB, 1)
    $cpuLoad = (Get-CimInstance Win32_Processor).LoadPercentage
    if (-not $cpuLoad) { $cpuLoad = 0 }
    $cpuBars = [math]::Min(20, [math]::Floor($cpuLoad / 5))
    $cpuEmpty = 20 - $cpuBars
    Write-Host "     CPU:  [$('#' * $cpuBars + '.' * $cpuEmpty)] ${cpuLoad}%" -ForegroundColor Gray
    $memBars = [math]::Min(20, [math]::Floor($usedGB / $totalGB * 20))
    $memEmpty = 20 - $memBars
    Write-Host "     RAM:  [$('#' * $memBars + '.' * $memEmpty)] ${usedGB}/${totalGB} GB" -ForegroundColor Gray
    Write-Host "  --------------------------------------------------------------" -ForegroundColor DarkCyan

    Write-Host ""
    Write-Host "  Refresh: 2s | Ctrl+C to exit" -ForegroundColor DarkGray

    Start-Sleep -Seconds 2
}
