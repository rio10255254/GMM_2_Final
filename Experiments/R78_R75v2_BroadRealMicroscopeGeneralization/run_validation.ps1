param(
    [ValidateSet("Primary", "Followup", "Test", "All")]
    [string]$Stage = "Test"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$PythonExe = "C:\Users\Rio\anaconda3\python.exe"

function Run-Python {
    param([string[]]$Arguments)
    & $PythonExe @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Python command failed with exit code $LASTEXITCODE"
    }
}

if ($Stage -in @("Primary", "All")) {
    Run-Python @((Join-Path $Root "scripts\run_r78.py"), "--stage", "all")
}

if ($Stage -in @("Followup", "All")) {
    $InferScript = "D:\GMM_2_Final\Experiments\R75v2_R61ArchitectureScratchGeneralization\inference\infer_r75v2.py"
    $Checkpoint = "D:\GMM_2_Final\Experiments\R75v2_R61ArchitectureScratchGeneralization\runs\training_progress_LAB_GESR_v1_v5_R75v2_scratch_formal_seed752031_diverse_data_e100_20260731_163219\epoch_100.pth.tar"
    $FullBase = Join-Path $Root "results\diagnostics\5x_tile1024_full"
    $FollowupInputs = @{
        "5x_0p5um" = "D:\GMM_2_Final\20260704_20x_5x_analysis\raw_inputs\5x_0p5um\bmp"
        "5x_1um" = "D:\GMM_2_Final\20260704_20x_5x_analysis\raw_inputs\5x_1um\bmp"
    }
    foreach ($Name in $FollowupInputs.Keys) {
        $Output = Join-Path $FullBase $Name
        if (-not (Test-Path -LiteralPath (Join-Path $Output "inference_manifest.json"))) {
            Run-Python @($InferScript, "--checkpoint", $Checkpoint, "--input", $FollowupInputs[$Name], "--output", $Output, "--device", "cuda:0", "--tile-size", "1024", "--overlap", "128")
        }
    }
    $SingleInput = "D:\GMM_2_Final\20260704_20x_5x_analysis\raw_inputs\5x_0p5um\bmp\frame_0000.bmp"
    $SensitivityBase = Join-Path $Root "results\diagnostics\5x_tile_sensitivity"
    $SensitivitySettings = @(
        @{ Name = "tile768_overlap96"; Tile = "768"; Overlap = "96" },
        @{ Name = "tile1024_overlap128"; Tile = "1024"; Overlap = "128" }
    )
    foreach ($Setting in $SensitivitySettings) {
        $Output = Join-Path $SensitivityBase $Setting.Name
        if (-not (Test-Path -LiteralPath (Join-Path $Output "inference_manifest.json"))) {
            Run-Python @($InferScript, "--checkpoint", $Checkpoint, "--input", $SingleInput, "--output", $Output, "--device", "cuda:0", "--tile-size", $Setting.Tile, "--overlap", $Setting.Overlap)
        }
    }
    Run-Python @((Join-Path $Root "scripts\run_r78_5x_followup.py"))
    Run-Python @((Join-Path $Root "scripts\run_r78_5x_tile1024_motion.py"))
    Run-Python @((Join-Path $Root "scripts\evaluate_r78_5x_tile_sensitivity.py"))
    Run-Python @((Join-Path $Root "scripts\run_r78.py"), "--stage", "analyze")
}

if ($Stage -in @("Test", "All")) {
    Run-Python @("-m", "unittest", "discover", "-s", (Join-Path $Root "tests"), "-v")
}
