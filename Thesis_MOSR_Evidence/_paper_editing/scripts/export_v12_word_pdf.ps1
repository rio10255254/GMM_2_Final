$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
$ErrorActionPreference = 'Stop'

$documentPath = 'C:\Users\Rio\OneDrive\學業\碩班\論文\可用\論文完整版_20260716_v12.docx'
$outputDirectory = (Join-Path $ProjectRoot 'Thesis_MOSR_Evidence\_paper_editing\qa\v12_final_render_20260720_c')
$pdfPath = Join-Path $outputDirectory '論文完整版_20260716_v12.pdf'

New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null

$word = $null
$document = $null
try {
    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $word.DisplayAlerts = 0
    $document = $word.Documents.Open($documentPath, $false, $true, $false)
    $document.Repaginate()
    $pageCount = $document.ComputeStatistics(2)
    $document.ExportAsFixedFormat(
        $pdfPath,
        17,
        $false,
        0,
        0,
        1,
        $pageCount,
        0,
        $true,
        $true,
        0,
        $true,
        $true,
        $false
    )

    [pscustomobject]@{
        Pdf = $pdfPath
        WordPages = $pageCount
        Bytes = (Get-Item -LiteralPath $pdfPath).Length
    } | ConvertTo-Json
}
finally {
    if ($null -ne $document) {
        try { $document.Close($false) } catch {}
        [System.Runtime.InteropServices.Marshal]::ReleaseComObject($document) | Out-Null
    }
    if ($null -ne $word) {
        try { $word.Quit() } catch {}
        [System.Runtime.InteropServices.Marshal]::ReleaseComObject($word) | Out-Null
    }
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
}
