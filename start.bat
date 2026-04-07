@echo off
rem 获取当前批处理文件所在目录
set "SCRIPT_DIR=%~dp0"

rem 激活虚拟环境
call "%SCRIPT_DIR%venv\Scripts\activate.bat"

rem 使用虚拟环境中的 Python 启动 Django 开发服务器
"%SCRIPT_DIR%venv\Scripts\python.exe" run.py

rem 保持命令窗口打开，方便查看输出
pause