param(
    [string]$Config = "qwen35_2b_llamacpp.yaml",
    [string]$Command = "prepare"
)

# SQL_RAG Qwen3.5-2B 本机验证模型脚本。

# 定义脚本参数：Config 是 Qwen3.5-2B 配置文件，Command 是 prepare/start/health/env/apply-env 等子命令。

# 读取当前脚本目录。
$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
# 定位 SQL_RAG 根目录。
$SqlRagRoot = Resolve-Path (Join-Path $ScriptRoot "..\..")
# 定位后端虚拟环境 Python。
$VenvPython = Join-Path $SqlRagRoot "..\..\.venv\Scripts\python.exe"
# 如果虚拟环境 Python 存在就使用它。
if (Test-Path $VenvPython) {
    # 保存 Python 可执行文件路径。
    $Python = $VenvPython
}
# 如果虚拟环境 Python 不存在就使用系统 Python。
else {
    # 使用 PATH 中的 python。
    $Python = "python"
}
# 组装 main.py 路径。
$MainPy = Join-Path $SqlRagRoot "main.py"
# 判断配置是否已经是绝对路径。
if ([System.IO.Path]::IsPathRooted($Config)) {
    # 绝对路径直接使用。
    $ConfigPath = $Config
}
# 相对路径按脚本目录解析。
else {
    # 组装配置路径。
    $ConfigPath = Join-Path $ScriptRoot $Config
}
# 调用统一入口执行 Qwen3.5-2B 命令。
& $Python $MainPy qwen35-2b --config $ConfigPath $Command
# 透传 Python 子命令退出码。
exit $LASTEXITCODE


