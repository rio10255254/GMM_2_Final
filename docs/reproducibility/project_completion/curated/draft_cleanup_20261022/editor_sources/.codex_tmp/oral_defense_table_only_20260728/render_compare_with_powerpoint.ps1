$ErrorActionPreference = 'Stop'
$pairs = @(
    @{ Deck = 'C:\Users\Rio\OneDrive\學業\碩班\論文\可用\江彥諠_口試簡報_附講稿.pptx'; Out = 'D:\GMM_2_Final\PSF_Fitting\.codex_tmp\oral_defense_table_only_20260728\render-source' },
    @{ Deck = 'C:\Users\Rio\OneDrive\學業\碩班\論文\可用\江彥諠_口試簡報_附講稿_v17效能表格修正.pptx'; Out = 'D:\GMM_2_Final\PSF_Fitting\.codex_tmp\oral_defense_table_only_20260728\render-final' }
)

$powerPoint = $null
try {
    $powerPoint = New-Object -ComObject PowerPoint.Application
    foreach ($pair in $pairs) {
        New-Item -ItemType Directory -Force $pair.Out | Out-Null
        $presentation = $null
        try {
            $presentation = $powerPoint.Presentations.Open($pair.Deck, $true, $false, $false)
            $presentation.Export($pair.Out, 'PNG', 1280, 720)
        }
        finally {
            if ($presentation) { $presentation.Close() }
            if ($presentation) { [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($presentation) }
        }
    }
}
finally {
    if ($powerPoint) { $powerPoint.Quit() }
    if ($powerPoint) { [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($powerPoint) }
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
}

$sourceFiles = Get-ChildItem -LiteralPath $pairs[0].Out -File | Sort-Object { [int]([regex]::Match($_.BaseName,'\d+').Value) }
$finalFiles = Get-ChildItem -LiteralPath $pairs[1].Out -File | Sort-Object { [int]([regex]::Match($_.BaseName,'\d+').Value) }
$differences = @()
for ($i = 0; $i -lt $sourceFiles.Count; $i++) {
    $sourceHash = (Get-FileHash -LiteralPath $sourceFiles[$i].FullName -Algorithm SHA256).Hash
    $finalHash = (Get-FileHash -LiteralPath $finalFiles[$i].FullName -Algorithm SHA256).Hash
    if ($sourceHash -ne $finalHash) { $differences += ($i + 1) }
}
[PSCustomObject]@{ SourceSlides = $sourceFiles.Count; FinalSlides = $finalFiles.Count; DifferentSlides = ($differences -join ',') } | Format-List
