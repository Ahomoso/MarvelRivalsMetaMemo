<#
Resize PNG images under a target folder, convert them to JPEG, and update
Markdown image references from .png to .jpg.

Basic usage:
  .\resize_images_to_jpeg.ps1 -Root "D:\vscode\クリンター"

Options:
  -MaxWidth 1200   Maximum output image width. Aspect ratio is preserved.
  -Quality 85      JPEG quality, from 0 to 100.
  -KeepPng         Keep active PNG files after JPEG conversion.

What this script does:
  1. Finds .png files recursively under -Root.
  2. Skips backup/test folders such as _png_backup, _png_before_jpeg*, and _resize_test.
  3. Backs up original PNG files to _png_before_jpeg_YYYYMMDD_HHMMSS.
  4. Saves resized .jpg files beside the original images.
  5. Rewrites Markdown references like image.png to image.jpg.
  6. Deletes active PNG files unless -KeepPng is specified.

Examples:
  .\resize_images_to_jpeg.ps1 -Root "D:\vscode\クリンター"
  .\resize_images_to_jpeg.ps1 -Root "D:\vscode\クリンター" -MaxWidth 1000 -Quality 82
  .\resize_images_to_jpeg.ps1 -Root "D:\vscode\クリンター" -KeepPng
#>

param(
    [Parameter(Mandatory = $true)]
    [string]$Root,

    [int]$MaxWidth = 1200,

    [long]$Quality = 85,

    [switch]$KeepPng
)

$ErrorActionPreference = "Stop"

$rootPath = (Resolve-Path -LiteralPath $Root).Path
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backupPath = Join-Path $rootPath ("_png_before_jpeg_" + $stamp)

New-Item -ItemType Directory -Force -Path $backupPath | Out-Null
Add-Type -AssemblyName System.Drawing

$pngs = Get-ChildItem -LiteralPath $rootPath -Recurse -File -Filter *.png |
    Where-Object {
        $_.FullName -notlike "*\_resize_test\*" -and
        $_.FullName -notlike "*\_png_backup\*" -and
        $_.FullName -notlike "*\_png_before_jpeg*\*" -and
        $_.FullName -notlike "*\.pdf_html\*"
    }

$jpgCodec = [System.Drawing.Imaging.ImageCodecInfo]::GetImageEncoders() |
    Where-Object { $_.MimeType -eq "image/jpeg" }

$encoderParams = New-Object System.Drawing.Imaging.EncoderParameters(1)
$encoderParams.Param[0] = New-Object System.Drawing.Imaging.EncoderParameter(
    [System.Drawing.Imaging.Encoder]::Quality,
    $Quality
)

$results = @()

foreach ($file in $pngs) {
    $relative = $file.FullName.Substring($rootPath.Length).TrimStart("\")
    $backupFile = Join-Path $backupPath $relative
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $backupFile) | Out-Null
    Copy-Item -LiteralPath $file.FullName -Destination $backupFile -Force

    $before = $file.Length
    $image = [System.Drawing.Image]::FromFile($file.FullName)

    try {
        $scale = [Math]::Min(1.0, $MaxWidth / $image.Width)
        $width = [int]($image.Width * $scale)
        $height = [int]($image.Height * $scale)

        $bitmap = New-Object System.Drawing.Bitmap(
            $width,
            $height,
            [System.Drawing.Imaging.PixelFormat]::Format24bppRgb
        )

        $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
        try {
            $graphics.Clear([System.Drawing.Color]::White)
            $graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
            $graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::HighQuality
            $graphics.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
            $graphics.DrawImage($image, 0, 0, $width, $height)

            $jpgPath = [System.IO.Path]::ChangeExtension($file.FullName, ".jpg")
            $bitmap.Save($jpgPath, $jpgCodec, $encoderParams)
        }
        finally {
            $graphics.Dispose()
            $bitmap.Dispose()
        }
    }
    finally {
        $image.Dispose()
    }

    $after = (Get-Item -LiteralPath $jpgPath).Length
    $results += [pscustomobject]@{
        Name = $relative
        PngBytes = $before
        JpgBytes = $after
    }
}

$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
$markdownFiles = Get-ChildItem -LiteralPath $rootPath -Recurse -File -Filter *.md |
    Where-Object {
        $_.FullName -notlike "*\_png_backup\*" -and
        $_.FullName -notlike "*\_png_before_jpeg*\*"
    }

$changedMarkdown = 0

foreach ($markdown in $markdownFiles) {
    $text = [System.IO.File]::ReadAllText($markdown.FullName, [System.Text.Encoding]::UTF8)
    $newText = [regex]::Replace(
        $text,
        "(!\[[^\]]*\]\([^)]*?)\.png(\))",
        '$1.jpg$2'
    )

    if ($newText -ne $text) {
        [System.IO.File]::WriteAllText($markdown.FullName, $newText, $utf8NoBom)
        $changedMarkdown++
    }
}

if (-not $KeepPng) {
    $pngs | Remove-Item -Force
}

$totalPng = ($results | Measure-Object PngBytes -Sum).Sum
$totalJpg = ($results | Measure-Object JpgBytes -Sum).Sum
$remainingPngs = Get-ChildItem -LiteralPath $rootPath -Recurse -File -Filter *.png |
    Where-Object {
        $_.FullName -notlike "*\_resize_test\*" -and
        $_.FullName -notlike "*\_png_backup\*" -and
        $_.FullName -notlike "*\_png_before_jpeg*\*" -and
        $_.FullName -notlike "*\.pdf_html\*"
    }

$jpgRefsMissing = @()
foreach ($markdown in $markdownFiles) {
    $text = [System.IO.File]::ReadAllText($markdown.FullName, [System.Text.Encoding]::UTF8)
    foreach ($match in [regex]::Matches($text, "!\[[^\]]*\]\(([^)]+\.jpg)\)")) {
        $target = $match.Groups[1].Value.Trim()
        $fullPath = [System.IO.Path]::GetFullPath((Join-Path $markdown.DirectoryName $target))
        if (-not (Test-Path -LiteralPath $fullPath)) {
            $jpgRefsMissing += [pscustomobject]@{
                Markdown = $markdown.FullName
                Missing = $fullPath
            }
        }
    }
}

Write-Host ("Converted PNGs: " + $results.Count)
Write-Host ("Markdown changed: " + $changedMarkdown)
Write-Host ("Backup: " + $backupPath)
Write-Host ("Total PNG bytes: " + $totalPng)
Write-Host ("Total JPG bytes: " + $totalJpg)
Write-Host ("Remaining active PNGs: " + $remainingPngs.Count)
Write-Host ("Missing JPG refs: " + $jpgRefsMissing.Count)

$results | Sort-Object PngBytes -Descending | Select-Object -First 20
