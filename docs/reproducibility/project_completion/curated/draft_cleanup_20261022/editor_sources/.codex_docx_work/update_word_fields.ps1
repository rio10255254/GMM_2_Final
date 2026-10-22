param(
    [Parameter(Mandatory = $true)]
    [string]$DocumentPath
)

$word = $null
$doc = $null
try {
    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $word.DisplayAlerts = 0
    $doc = $word.Documents.Open($DocumentPath, $false, $false)
    $doc.Repaginate()
    foreach ($toc in $doc.TablesOfContents) {
        $toc.Update()
    }
    foreach ($tof in $doc.TablesOfFigures) {
        $tof.Update()
    }
    $doc.Fields.Update() | Out-Null
    $doc.Repaginate()
    $doc.Save()
    Write-Output "UPDATED=$DocumentPath"
}
finally {
    if ($null -ne $doc) {
        $doc.Close(0)
    }
    if ($null -ne $word) {
        $word.Quit()
    }
    if ($null -ne $doc) {
        [System.Runtime.InteropServices.Marshal]::ReleaseComObject($doc) | Out-Null
    }
    if ($null -ne $word) {
        [System.Runtime.InteropServices.Marshal]::ReleaseComObject($word) | Out-Null
    }
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
}
