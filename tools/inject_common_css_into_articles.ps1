param(
  [string]$DocsRoot = (Join-Path $PSScriptRoot '..\docs'),
  [string]$CssPath = (Join-Path $PSScriptRoot '..\docs\article.css')
)

$docsRoot = [System.IO.Path]::GetFullPath($DocsRoot)
$cssPath = [System.IO.Path]::GetFullPath($CssPath)
$articlesRoot = Join-Path $docsRoot 'articles'

if (-not (Test-Path -LiteralPath $articlesRoot)) {
  throw "articles root not found: $articlesRoot"
}

if (-not (Test-Path -LiteralPath $cssPath)) {
  throw "css not found: $cssPath"
}

$htmlFiles = Get-ChildItem -Path $articlesRoot -Recurse -File -Filter *.html

foreach ($file in $htmlFiles) {
  $content = Get-Content -LiteralPath $file.FullName -Raw -Encoding UTF8
  if ($null -eq $content) { continue }

  $fromUri = [Uri]((Resolve-Path -LiteralPath $file.DirectoryName).Path.TrimEnd('\') + '\')
  $toUri = [Uri]((Resolve-Path -LiteralPath $cssPath).Path)
  $relCss = [Uri]::UnescapeDataString($fromUri.MakeRelativeUri($toUri).ToString())
  $relCss = $relCss -replace '/', '/'

  $linkTag = "  <link rel=`"stylesheet`" href=`"$relCss`">`r`n"
  $styleRx = [regex]'(?s)<style>.*?</style>\s*'
  for ($i = 0; $i -lt 3; $i++) {
    if ($styleRx.IsMatch($content)) {
      $content = $styleRx.Replace($content, '', 1)
    }
  }
  $content = [regex]::Replace($content, '(?m)^\s*<link rel="stylesheet" href="[^"]*common\.css">\s*\r?\n?', '')
  $content = [regex]::Replace($content, '(?m)^\s*<link rel="stylesheet" href="[^"]*article\.css">\s*\r?\n?', '')

  $headClose = '</head>'
  $headIndex = $content.IndexOf($headClose, [System.StringComparison]::OrdinalIgnoreCase)
  if ($headIndex -lt 0) {
    throw "no </head> found in: $($file.FullName)"
  }

  $updated = $content.Substring(0, $headIndex) + $linkTag + $content.Substring($headIndex)
  Set-Content -LiteralPath $file.FullName -Value $updated -Encoding UTF8
}
