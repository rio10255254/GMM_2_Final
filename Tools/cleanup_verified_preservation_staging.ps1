param(
    [Parameter(Mandatory=$true)][string]$OperationRoot,
    [Parameter(Mandatory=$true)][string]$CleanupManifest
)
$ErrorActionPreference = 'Stop'
$root = [System.IO.Path]::GetFullPath($OperationRoot).TrimEnd('\')
$allowed = 'H:\GMM_2_Final_Archive\reproducibility\'
if (-not $root.StartsWith($allowed,[StringComparison]::OrdinalIgnoreCase)) { throw 'Only owned H preservation staging can be cleaned' }
if (-not (Test-Path -LiteralPath (Join-Path $root 'BASELINE.json') -PathType Leaf)) { throw 'Missing operation ownership record' }
$spec = Get-Content -LiteralPath $CleanupManifest -Raw -Encoding UTF8 | ConvertFrom-Json
$batch = [System.IO.Path]::GetFullPath([string]$spec.batch_root).TrimEnd('\')
if (-not $batch.StartsWith($root+'\',[StringComparison]::OrdinalIgnoreCase)) { throw 'Batch is outside this operation' }
$relativeBatch = $batch.Substring($root.Length+1)
if ($relativeBatch -notmatch '^(model_batches|numeric_batches|image_batches|package_batches)\\(MODELS|NUMERIC|IMAGES|PACKAGES)_B[0-9]{3}$') { throw 'Unrecognized owned batch directory' }
$selection = Get-Content -LiteralPath (Join-Path $batch 'SELECTION.json') -Raw -Encoding UTF8 | ConvertFrom-Json
if ($selection.reviewed -ne $true) { throw 'Batch was not reviewed' }
$verifiedPath = Join-Path $batch 'BATCH_GITHUB_RESTORE_VERIFIED.json'
$verified = Get-Content -LiteralPath $verifiedPath -Raw -Encoding UTF8 | ConvertFrom-Json
if ($verified.status -ne 'PASS_FILE_IDENTITY_AND_RESTORATION') { throw 'Actual downloaded object restoration has not passed' }
$downloaded = Get-Content -LiteralPath (Join-Path $batch 'GITHUB_DOWNLOADED_VERIFIED.json') -Raw -Encoding UTF8 | ConvertFrom-Json
if ($downloaded.status -ne 'PASS') { throw 'Actual GitHub download has not passed' }
$hashAlgorithm = [System.Security.Cryptography.SHA256]::Create()
$hashStream = [System.IO.File]::OpenRead($verifiedPath)
try { $reportHash = ([System.BitConverter]::ToString($hashAlgorithm.ComputeHash($hashStream))).Replace('-','').ToLowerInvariant() }
finally { $hashStream.Dispose(); $hashAlgorithm.Dispose() }
if ($reportHash -ne $spec.verification_report_sha256) { throw 'Verification record changed' }
$targets = @()
foreach ($entry in $spec.files) {
    $path = [System.IO.Path]::GetFullPath([string]$entry.path)
    if (-not $path.StartsWith($batch+'\',[StringComparison]::OrdinalIgnoreCase)) { throw 'Cleanup cannot address a research original or another batch' }
    $relative = $path.Substring($batch.Length+1)
    if ($relative -notmatch '^(bundle|github_downloads)\\research-[^\\]+\.zip$' -and $relative -ne 'restored_validation_buffer\verified_object.pth.tar') { throw 'Only verified part files and the owned validation buffer can be removed' }
    $item = Get-Item -LiteralPath $path -Force
    if ($item.PSIsContainer -or $item.Length -ne [long]$entry.bytes -or $item.LastWriteTimeUtc.Ticks -ne [long]$entry.last_write_utc_ticks) { throw 'Owned temporary file changed after verification' }
    $ancestor = $item
    while ($null -ne $ancestor -and $ancestor.FullName.Length -ge $root.Length) {
        if (($ancestor.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) { throw 'Cleanup cannot pass through a redirect' }
        $ancestor = if ($ancestor -is [System.IO.DirectoryInfo]) { $ancestor.Parent } else { $ancestor.Directory }
    }
    if ($relative -match '^(bundle|github_downloads)\\') {
        $matching = @($verified.assets | Where-Object { $_.name -eq $item.Name -and $_.bytes -eq $item.Length -and $_.sha256 -eq $entry.sha256 })
        $remote = @($downloaded.assets | Where-Object { $_.name -eq $item.Name -and $_.bytes -eq $item.Length -and $_.sha256 -eq $entry.sha256 -and $_.verified_from_github -eq $true })
        if ($matching.Count -ne 1 -or $remote.Count -ne 1) { throw 'A part lacks matching actual GitHub/restore proof' }
    } else {
        $last = @($verified.checks)[-1]
        if ($last.sha256 -ne $entry.sha256 -or $last.bytes -ne $item.Length) { throw 'Validation buffer does not match the last inspected original object' }
    }
    $targets += $item.FullName
}
# Preflight every literal file above before deleting any. Never recurse, move,
# alter original D/H research, invoke another shell for file operations, or use
# a fallback when this native cleanup is denied.
foreach ($path in $targets) { Remove-Item -LiteralPath $path -Force }
[ordered]@{status='PASS';removed_owned_temporary_files=$targets;research_originals_removed=0} |
    ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $batch 'TEMPORARY_STAGING_CLEANED.json') -Encoding UTF8
