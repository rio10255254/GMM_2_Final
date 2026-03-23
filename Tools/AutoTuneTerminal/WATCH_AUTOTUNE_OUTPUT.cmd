@echo off
title AutoTune Output
cd /d "%~dp0..\.."
python Model\GeoEdgeAlignSR_v1_AutoTuneOutputWatch.py %*
