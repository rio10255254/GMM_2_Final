@echo off
title AutoTune Status
cd /d "%~dp0..\.."
python Model\GeoEdgeAlignSR_v1_AutoTuneStatusWatch.py %*
