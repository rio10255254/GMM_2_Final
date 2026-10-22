$ErrorActionPreference = 'Stop'
$sourcePath = 'C:\Users\Rio\OneDrive\學業\碩班\論文\可用\江彥諠_口試簡報_附講稿.pptx'
$outputPath = 'C:\Users\Rio\OneDrive\學業\碩班\論文\可用\江彥諠_口試簡報_附講稿_v17效能表格修正.pptx'
$expectedOutput = [System.IO.Path]::GetFullPath($outputPath)
$resolvedOutput = [System.IO.Path]::GetFullPath($outputPath)
if ($resolvedOutput -ne $expectedOutput) { throw 'Unexpected output path.' }
if (Test-Path -LiteralPath $resolvedOutput) { Remove-Item -LiteralPath $resolvedOutput -Force }

$values = @(
    @('Model', 'Parameters (M)', 'Median Latency (ms)', 'P95 Latency (ms)', 'Throughput (MP/s)'),
    @('NAFNet', '4.182', '152.7', '155.3', '20.60'),
    @('EDSR-x1', '4.071', '915.6', '920.4', '3.44'),
    @('MOSR', '4.024', '400.2', '406.8', '7.86')
)

function Convert-HexToOfficeRgb([string]$hex) {
    $clean = $hex.TrimStart('#')
    $r = [Convert]::ToInt32($clean.Substring(0, 2), 16)
    $g = [Convert]::ToInt32($clean.Substring(2, 2), 16)
    $b = [Convert]::ToInt32($clean.Substring(4, 2), 16)
    return $r + (256 * $g) + (65536 * $b)
}

$green = Convert-HexToOfficeRgb '#4EA72E'
$blue = Convert-HexToOfficeRgb '#0F9ED5'
$black = Convert-HexToOfficeRgb '#000000'
$powerPoint = $null
$presentation = $null
try {
    $powerPoint = New-Object -ComObject PowerPoint.Application
    $presentation = $powerPoint.Presentations.Open($sourcePath, $true, $false, $false)
    if ($presentation.Slides.Count -ne 63) { throw "Expected 63 slides, found $($presentation.Slides.Count)." }
    $slide = $presentation.Slides.Item(59)
    $tableShape = $null
    foreach ($shape in $slide.Shapes) {
        if ($shape.Name -eq 'Table 1' -and $shape.HasTable) { $tableShape = $shape; break }
    }
    if (-not $tableShape) { throw 'Could not find slide 59 table named Table 1.' }
    $table = $tableShape.Table
    if ($table.Rows.Count -ne 4 -or $table.Columns.Count -ne 5) { throw 'Unexpected slide 59 table dimensions.' }

    for ($row = 1; $row -le 4; $row++) {
        for ($column = 1; $column -le 5; $column++) {
            $table.Cell($row, $column).Shape.TextFrame.TextRange.Text = $values[$row - 1][$column - 1]
        }
    }

    for ($row = 2; $row -le 4; $row++) {
        for ($column = 2; $column -le 5; $column++) {
            $font = $table.Cell($row, $column).Shape.TextFrame.TextRange.Font
            $font.Color.RGB = $black
            $font.Bold = 0
        }
    }
    foreach ($cell in @(@(2,3), @(2,4), @(2,5), @(4,2))) {
        $font = $table.Cell($cell[0], $cell[1]).Shape.TextFrame.TextRange.Font
        $font.Color.RGB = $green
        $font.Bold = -1
    }
    foreach ($cell in @(@(3,2), @(4,3), @(4,4), @(4,5))) {
        $font = $table.Cell($cell[0], $cell[1]).Shape.TextFrame.TextRange.Font
        $font.Color.RGB = $blue
        $font.Bold = -1
    }

    $presentation.SaveCopyAs($resolvedOutput, 24)
}
finally {
    if ($presentation) { $presentation.Close() }
    if ($powerPoint) { $powerPoint.Quit() }
    if ($tableShape) { [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($tableShape) }
    if ($slide) { [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($slide) }
    if ($presentation) { [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($presentation) }
    if ($powerPoint) { [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($powerPoint) }
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
}

Get-Item -LiteralPath $resolvedOutput | Select-Object FullName,Length,LastWriteTime | Format-List
