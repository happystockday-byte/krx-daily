@echo off
cd /d %~dp0
python daily_market_card.py >> logs.txt 2>&1
