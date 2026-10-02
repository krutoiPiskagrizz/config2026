import argparse
import os
import shlex
import sys

VFS_NAME = "vfs"

class ShellError(Exception):
 """ошибка выполнения команды"""

def cmd_ls(args):
    print("ls", args)  

def cmd_cd(args):
    print("cd", args) 

def cmd_exit(args):
    sys.exit(0)

COMMANDS = {"ls": cmd_ls, "cd": cmd_cd, "exit": cmd_exit}

def execute(line):
    try:
        argv = shlex.split(line)
    except ValueError as e:
        raise ShellError(f"ошибка разбора: {e}")
    if not argv:
        return
    name, args = argv[0], argv[1:]
    if name not in COMMANDS:
        raise ShellError(f"{name}: команда не найдена")
    if name == "exit" and args:
        raise ShellError("exit: команда не принимает аргументов")
    COMMANDS[name](args)

def run_script(path, prompt):
    """выполняет скрипт: показывает ввод и вывод, ошибочные строки пропускает"""
    try:
        with open(path, encoding="utf-8") as f:
            lines = f.read().splitlines()
    except OSError as e:
        print(f"ошибка: не удалось открыть стартовый скрипт: {e}", file=sys.stderr)
        return
    for n, line in enumerate(lines, 1):
        print(prompt + line)  
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        try:
            execute(line)
        except ShellError as e:
            print(e, file=sys.stderr)
            print(f"[скрипт] ошибка в строке {n}, строка пропущена", file=sys.stderr)

def main():
    ap = argparse.ArgumentParser(description="Эмулятор оболочки UNIX")
    ap.add_argument("--vfs", required=True, help="путь к физическому расположению VFS")
    ap.add_argument("--script", help="путь к стартовому скрипту")
    a = ap.parse_args()

    print("[debug] Параметры запуска:")
    print(f"[debug]   vfs    = {a.vfs}")
    print(f"[debug]   script = {a.script}")

    vfs_name = os.path.splitext(os.path.basename(a.vfs))[0] or "vfs"
    prompt = f"user@{vfs_name}:/$ "

    if a.script:
        run_script(a.script, prompt)

    while True:
        try:
            line = input(prompt)
        except EOFError:
            print()
            break
        except KeyboardInterrupt:
            print()
            continue
        try:
            execute(line)
        except ShellError as e:
            print(e, file=sys.stderr)

if __name__ == "__main__":
    main()