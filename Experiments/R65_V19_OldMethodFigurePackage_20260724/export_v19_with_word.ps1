$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$ErrorActionPreference = 'Stop'

$source = (Join-Path $ProjectRoot 'Experiments\R65_V19_OldMethodFigurePackage_20260724\論文完整版_20260716_v19_第六章更新版.docx')
$output = (Join-Path $ProjectRoot 'Experiments\R65_V19_OldMethodFigurePackage_20260724\v19_format_alignment_qa.pdf')
$log = (Join-Path $ProjectRoot 'Experiments\R65_V19_OldMethodFigurePackage_20260724\v19_word_export.log')

$word = $null
$document = $null
try {
    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $word.DisplayAlerts = 0
    $word.Options.UpdateLinksAtOpen = $false
    $document = $word.Documents.Open($source, $false, $false, $false)
    $document.Fields.Update() | Out-Null
    foreach ($toc in $document.TablesOfContents) {
        $toc.Update()
    }
    foreach ($tof in $document.TablesOfFigures) {
        $tof.Update()
    }
    $document.Repaginate()
    $document.Save()
    $document.ExportAsFixedFormat($output, 17, $false, 0, 0, 1, 9999, 0, $true, $true, 1, $true, $true, $false)
    "SUCCESS`n$output" | Set-Content -LiteralPath $log -Encoding UTF8
}
catch {
    "FAILED`n$($_.Exception.ToString())" | Set-Content -LiteralPath $log -Encoding UTF8
    throw
}
finally {
    if ($document -ne $null) {
        $document.Close(0)
        [System.Runtime.InteropServices.Marshal]::ReleaseComObject($document) | Out-Null
    }
    if ($word -ne $null) {
        $word.Quit()
        [System.Runtime.InteropServices.Marshal]::ReleaseComObject($word) | Out-Null
    }
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
}
