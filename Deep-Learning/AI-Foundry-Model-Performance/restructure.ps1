# Repository Restructuring Script
# This script organizes the repository files into a cleaner structure

Write-Host "🚀 Starting repository restructuring..." -ForegroundColor Green

# Create directories if they don't exist
$directories = @(
    "scripts/deployment",
    "scripts/testing",
    "docs",
    "assets"
)

foreach ($dir in $directories) {
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
        Write-Host "✅ Created directory: $dir" -ForegroundColor Cyan
    }
}

# Move deployment scripts
$deploymentScripts = @(
    "deploymodels-linux-20250405.py",
    "deploymodels-powershell-20250405.py",
    "delete-endpoint-20250327.py"
)

Write-Host "`n📦 Moving deployment scripts..." -ForegroundColor Yellow
foreach ($script in $deploymentScripts) {
    if (Test-Path $script) {
        Move-Item -Path $script -Destination "scripts/deployment/" -Force
        Write-Host "  ✓ Moved $script" -ForegroundColor Green
    }
}

# Move testing scripts
$testingScripts = @(
    "callaiinference-20250406.py",
    "concurrency_test.py",
    "press-phi4-0403.py",
    "press-phi35and0v-20250323.py",
    "press-phi35v-multi-imges-20250315.py",
    "press-llama3.211bv-20250407.py",
    "press-Mixtral-8x7B-20250323.py",
    "press-nemotron-3-8b-chat-4k-steerlm-20250324.py",
    "press-orca-20250324.py",
    "press-swinv2-20250322.py",
    "press-whisper-20250323.py",
    "press.financial-reports-analysis-20250321.py"
)

Write-Host "`n🧪 Moving testing scripts..." -ForegroundColor Yellow
foreach ($script in $testingScripts) {
    if (Test-Path $script) {
        Move-Item -Path $script -Destination "scripts/testing/" -Force
        Write-Host "  ✓ Moved $script" -ForegroundColor Green
    }
}

# Move documentation
Write-Host "`n📚 Moving documentation files..." -ForegroundColor Yellow
if (Test-Path "muse.md") {
    Move-Item -Path "muse.md" -Destination "docs/" -Force
    Write-Host "  ✓ Moved muse.md" -ForegroundColor Green
}

# Move assets
Write-Host "`n🎵 Moving asset files..." -ForegroundColor Yellow
if (Test-Path "1.m4a") {
    Move-Item -Path "1.m4a" -Destination "assets/" -Force
    Write-Host "  ✓ Moved 1.m4a" -ForegroundColor Green
}

Write-Host "`n✨ Restructuring complete!" -ForegroundColor Green
Write-Host "`n📝 Next steps:" -ForegroundColor Cyan
Write-Host "  1. Review the changes" -ForegroundColor White
Write-Host "  2. Update README.md script paths (see RESTRUCTURE_GUIDE.md)" -ForegroundColor White
Write-Host "  3. Test the scripts with new paths" -ForegroundColor White
Write-Host "  4. Commit changes: git add . && git commit -m 'refactor: reorganize project structure'" -ForegroundColor White
Write-Host "  5. Push to GitHub: git push" -ForegroundColor White
