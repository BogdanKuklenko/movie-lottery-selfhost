Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "F:\Сайт опрос\movie-lottery-refactored\notification_client"
WshShell.Run "powershell.exe -ExecutionPolicy Bypass -WindowStyle Hidden -File keep_alive.ps1", 0, False

