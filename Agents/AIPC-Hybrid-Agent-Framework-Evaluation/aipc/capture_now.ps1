param(
    [string]$OutputPath = $(if ($env:AIPC_SCREENSHOT_PATH) { $env:AIPC_SCREENSHOT_PATH } else { Join-Path ([Environment]::GetFolderPath([Environment+SpecialFolder]::Desktop)) "last_screenshot.png" })
)

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
try {
    $bounds = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
    $bmp = New-Object System.Drawing.Bitmap($bounds.Width, $bounds.Height)
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.CopyFromScreen($bounds.Location, [System.Drawing.Point]::Empty, $bounds.Size)
    $bmp.Save($OutputPath, [System.Drawing.Imaging.ImageFormat]::Png)
    $g.Dispose(); $bmp.Dispose()
    Write-Output "CAPTURED"
} catch {
    Write-Output "ERROR: $_"
}
