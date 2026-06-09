param(
    [string]$Config = "qwen35_vllm.yaml",
    [switch]$Execute
)

# SQL_RAG Qwen3.5 模型拉取脚本。

# 定义脚本参数：Config 是配置文件名或绝对路径，Execute 表示真实执行拉取命令。

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
# 根据是否执行选择参数。
if ($Execute) {
    # 真实执行模型拉取命令。
    & $Python $MainPy model-service pull-command --config $ConfigPath --execute
    # 透传 Python 子命令退出码。
    exit $LASTEXITCODE
}
# 默认只输出命令，避免误占磁盘。
else {
    # 输出模型拉取命令。
    & $Python $MainPy model-service pull-command --config $ConfigPath
    # 透传 Python 子命令退出码。
    exit $LASTEXITCODE
}


