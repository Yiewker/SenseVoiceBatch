@echo off
:: 设置窗口标题
TITLE SenseVoiceBatch 启动器

:: -----------------------------------------------------
:: 这是一个批处理脚本，用于激活 Conda 环境并运行 Gradio ASR 应用
:: -----------------------------------------------------

echo [1/4] 正在激活 Conda 环境 (sensevoice)...
:: (这一步必须用 "call"，否则脚本会在激活后停止)
call conda activate sensevoice

:: 检查 Conda 激活是否成功
if %errorlevel% neq 0 (
    echo.
    echo 错误: 无法激活 Conda 环境 'sensevoice'。
    echo 请确保你已安装 Anaconda 并且环境名称正确。
    echo (你可以尝试先手动打开 Anaconda Prompt 运行 'conda activate sensevoice' 来测试)
    pause
    exit /b
)

echo [2/4] Conda 环境已激活。正在切换到项目目录...
:: 切换到 J: 盘符
J:
:: 切换到 app.py 所在的目录
cd "J:\Users\ccd\Desktop\projects\asr\SenseVoiceBatch"

echo [3/4] 正在启动 Gradio ASR 应用 (app.py)...
echo (请稍候，模型加载需要几秒钟...)
echo (浏览器将自动打开 http://127.0.0.1:7080)
echo.

:: 运行 Python 脚本
python app.py

:: -----------------------------------------------------
:: 脚本运行结束后 (例如你关闭了 Gradio 窗口)
:: -----------------------------------------------------
echo [4/4] Gradio 服务已关闭。
pause