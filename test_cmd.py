import subprocess

cmd_line = 'cmd /k "echo Hello World && timeout 2"'
print("Running:", cmd_line)
try:
    subprocess.Popen(
        cmd_line,
        shell=False,
        creationflags=subprocess.CREATE_NEW_CONSOLE,
    )
    print("Success shell=False")
except Exception as e:
    print("Error:", e)

try:
    subprocess.Popen(
        cmd_line,
        shell=True,
        creationflags=subprocess.CREATE_NEW_CONSOLE,
    )
    print("Success shell=True")
except Exception as e:
    print("Error:", e)
