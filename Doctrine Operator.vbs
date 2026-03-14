Set shell = CreateObject("WScript.Shell")
repoRoot = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
command = """" & repoRoot & "\.venv\Scripts\pythonw.exe"" -m doctrine_engine.product.cli launcher"
shell.Run command, 0, False
