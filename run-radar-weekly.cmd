@echo off
rem 信息差雷达周报入口 (供任务计划每周一调用)
setlocal
set "DSH_CMD=D:\deepseekharness\resources\runtime\cli\bin\dsh.cmd"
if not exist "%DSH_CMD%" set "DSH_CMD=dsh"
cd /d "%~dp0.."
if not exist "radar\logs" mkdir "radar\logs"
echo ===== weekly run start =====>> radar\logs\radar.log
"%DSH_CMD%" headless --json "你是信息差雷达周报员兼学习教练。按照工作区 .dsh/skills 中 radar、radar-report、radar-learn 三个 skill 的说明: 1) 汇总 radar/reports/ 下最近7天日报, 统计各领域新增趋势、本周最重要的3-5个信息差信号(带来源链接与日期)、与上周对比的变化, 生成 radar/reports/radar-YYYY-MM-DD-weekly.md(不超过1500字); 2) 运行 quiz_radar.py 查看本周到期学习卡, 从本周卡片中抽5道检验问题附在周报末尾(答案不写进正文), 并在周报中总结本周学过的机制。全程中文, 不编造。" >> radar\logs\radar.log 2>&1
echo ===== weekly run end, exit %errorlevel% =====>> radar\logs\radar.log
exit /b %errorlevel%
