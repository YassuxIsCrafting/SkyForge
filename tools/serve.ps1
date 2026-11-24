# Petit serveur local pour tester SkyForge (http://localhost:8765/)
param([string]$Root = (Join-Path $PSScriptRoot '..'), [int]$Port = 8765)
$Root = (Resolve-Path $Root).Path
$types = @{ '.html' = 'text/html; charset=utf-8'; '.glb' = 'model/gltf-binary'; '.js' = 'text/javascript'; '.css' = 'text/css'; '.png' = 'image/png'; '.json' = 'application/json' }
$l = New-Object System.Net.HttpListener
$l.Prefixes.Add("http://localhost:$Port/")
$l.Start()
Write-Host "SkyForge sur http://localhost:$Port/"
while ($l.IsListening) {
  $ctx = $l.GetContext()
  try {
    $path = [Uri]::UnescapeDataString($ctx.Request.Url.AbsolutePath.TrimStart('/'))
    if ($path -eq '') { $path = 'index.html' }
    $file = [IO.Path]::GetFullPath((Join-Path $Root $path))
    if (-not $file.StartsWith($Root) -or -not (Test-Path -LiteralPath $file -PathType Leaf)) {
      $ctx.Response.StatusCode = 404
    } else {
      $bytes = [IO.File]::ReadAllBytes($file)
      if ($path -eq 'index.html') {
        # meme enveloppe que la publication en Artifact
        $head = '<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover"><style>[hidden]{display:none!important}body{margin:0}</style></head><body>'
        $bytes = [Text.Encoding]::UTF8.GetBytes($head + [Text.Encoding]::UTF8.GetString($bytes) + '</body></html>')
        # regles proches de celles des Artifacts : pas de fetch vers data:, scripts limites aux CDN autorises
        $ctx.Response.Headers.Add('Content-Security-Policy', "default-src 'self'; script-src 'self' 'unsafe-inline' 'wasm-unsafe-eval' https://cdn.jsdelivr.net/npm/ https://cdnjs.cloudflare.com https://unpkg.com; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src https://fonts.gstatic.com; img-src 'self' data: blob:; connect-src 'self'; worker-src blob:")
      }
      $ext = [IO.Path]::GetExtension($file).ToLower()
      $ctx.Response.ContentType = $(if ($types[$ext]) { $types[$ext] } else { 'application/octet-stream' })
      $ctx.Response.ContentLength64 = $bytes.Length
      $ctx.Response.OutputStream.Write($bytes, 0, $bytes.Length)
    }
  } catch { $ctx.Response.StatusCode = 500 }
  $ctx.Response.Close()
}
