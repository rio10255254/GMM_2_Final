param(
    [Parameter(Mandatory = $true)]
    [string]$DocumentPath,
    [Parameter(Mandatory = $true)]
    [string]$PdfPath
)

$word = $null
$doc = $null
try {
    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $word.DisplayAlerts = 0
    $doc = $word.Documents.Open($DocumentPath, $false, $true)
    $doc.Repaginate()
    $doc.ExportAsFixedFormat($PdfPath, 17)
    Write-Output "PDF=$PdfPath"
    Write-Output "PAGES=$($doc.ComputeStatistics(2))"
}
finally {
    if ($null -ne $doc) { $doc.Close(0) }
    if ($null -ne $word) { $word.Quit() }
    if ($null -ne $doc) { [System.Runtime.InteropServices.Marshal]::ReleaseComObject($doc) | Out-Null }
    if ($null -ne $word) { [System.Runtime.InteropServices.Marshal]::ReleaseComObject($word) | Out-Null }
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
}
