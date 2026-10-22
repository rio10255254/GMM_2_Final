$ErrorActionPreference = 'Stop'
$deckPath = 'C:\Users\Rio\OneDrive\學業\碩班\論文\可用\江彥諠_口試簡報_附講稿_英文圖表_v17效能修正.pptx'
$outputDir = 'D:\GMM_2_Final\PSF_Fitting\.codex_tmp\oral_defense_with_notes_20260728\powerpoint-final-render'
New-Item -ItemType Directory -Force $outputDir | Out-Null

$powerPoint = $null
$presentation = $null
try {
    $powerPoint = New-Object -ComObject PowerPoint.Application
    $presentation = $powerPoint.Presentations.Open($deckPath, $true, $false, $false)
    $presentation.Export($outputDir, 'PNG', 1280, 720)
}
finally {
    if ($presentation) { $presentation.Close() }
    if ($powerPoint) { $powerPoint.Quit() }
    if ($presentation) { [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($presentation) }
    if ($powerPoint) { [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($powerPoint) }
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
}

Get-ChildItem -File $outputDir | Sort-Object Name | Select-Object Name, Length
