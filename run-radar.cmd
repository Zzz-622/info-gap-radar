@echo off
rem ============================================================
rem  信息差雷达每日入口 (供 Windows 任务计划调用)
rem  流程: cd 到工作区 -> dsh headless 按 radar skills 执行:
rem  采集 -> 差异分析 -> 生成日报(基础版 + LLM 精炼解读)
rem  注意: 首次使用前需在 %USERPROFILE%\.dsh\.env 配置
rem        DEEPSEEK_API_KEY (与 GUI 中使用的同一个 key)
rem ============================================================
setlocal
set "DSH_CMD=D:\deepseekharness\resources\runtime\cli\bin\dsh.cmd"
if not exist "%DSH_CMD%" set "DSH_CMD=dsh"
cd /d "%~dp0.."
if not exist "radar\logs" mkdir "radar\logs"
for /f "tokens=2 delims==." %%a in ('wmic os get localdatetime /value ^| find "="') do set "TS=%%a"
echo ===== %TS% radar run start =====>> radar\logs\radar.log
"%DSH_CMD%" headless --json "你是信息差雷达值班员。严格按照工作区 .dsh/skills 下 radar、radar-fetch、radar-diff、radar-report、radar-pick、radar-learn 六个 skill 的说明执行每日流程: 1) 运行采集脚本 fetch_radar.py; 2) 运行差异分析 diff_radar.py; 3) 运行 report_radar.py 生成基础日报; 4) 运行 scripts/llm_digest.py 追加『雷达解读』章节(无key自动跳过), 保存到 radar/reports/radar-YYYY-MM-DD.md; 5) 按 radar-pick skill 运行 pick_news.py 生成个性化精选报告, 再运行 deep_read.py 深读 top 精选写摘要; 6) 按 radar-learn skill 从精选/告警中挑一条写费曼学习卡到 radar/learn/cards/, 更新对应主题时间线, 运行 quiz_radar.py --scan 登记复习计划。全程中文, 不编造数据, 机制描述查不到就写待查。" >> radar\logs\radar.log 2>&1
echo ===== %TS% radar run end, exit %errorlevel% =====>> radar\logs\radar.log
exit /b %errorlevel%
