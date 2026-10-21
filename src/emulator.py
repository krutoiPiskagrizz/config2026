import argparse
import os
import shlex
import sys
import base64
import binascii
import csv
import posixpath

VFS_NAME = "vfs"

class ShellError(Exception):
 """ошибка выполнения команды"""
 
class VfsError(Exception):
    """Ошибка загрузки VFS."""
    
class Node:
    """Элемент VFS: каталог (is_dir=True) или файл с данными."""

    def __init__(self, name, is_dir, data=b""):
        self.name = name
        self.is_dir = is_dir
        self.data = data
        self.children = {}  

class VFS:
    """виртуальная файловая система, целиком в памяти.

    Формат CSV: path,type,content
      path    - полный путь от корня (/a/b/c.txt): так задаётся вложенность;
      type    - dir | file;
      content - base64 для файлов (для каталогов пусто).
    """

    def __init__(self, name):
        self.name = name
        self.root = Node("", True)

    @classmethod
    def from_csv(cls, path):
        if not os.path.isfile(path):
            raise VfsError(f"файл VFS не найден: {path}")
        name = os.path.splitext(os.path.basename(path))[0]
        vfs = cls(name)
        try:
            with open(path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                header = [h.strip() for h in reader.fieldnames or []]
                if header != ["path", "type", "content"]:
                    raise VfsError("неверный формат VFS: ожидается заголовок path,type,content")
                for lineno, row in enumerate(reader, start=2):
                    vfs._add_row(row, lineno)
        except (UnicodeDecodeError, csv.Error) as e:
            raise VfsError(f"неверный формат VFS: {e}")
        return vfs

    def _add_row(self, row, lineno):
        if None in row or None in row.values():
            raise VfsError(f"строка {lineno}: неверное число столбцов")
        p = posixpath.normpath("/" + row["path"].strip())
        kind = row["type"].strip()
        if p == "/":
            raise VfsError(f"строка {lineno}: недопустимый путь")
        if kind not in ("dir", "file"):
            raise VfsError(f"строка {lineno}: неизвестный тип '{kind}'")
        parts = p.strip("/").split("/")
        node = self.root
        for part in parts[:-1]:  
            nxt = node.children.setdefault(part, Node(part, True))
            if not nxt.is_dir:
                raise VfsError(f"строка {lineno}: '{part}' - не каталог")
            node = nxt
        last = parts[-1]
        if kind == "dir":
            existing = node.children.get(last)
            if existing is not None and not existing.is_dir:
                raise VfsError(f"строка {lineno}: '{p}' уже существует как файл")
            node.children.setdefault(last, Node(last, True))
        else:
            if last in node.children:
                raise VfsError(f"строка {lineno}: '{p}' уже существует")
            try:
                data = base64.b64decode(row["content"].strip(), validate=True)
            except (binascii.Error, ValueError):
                raise VfsError(f"строка {lineno}: содержимое не является base64")
            node.children[last] = Node(last, False, data)

    def count(self):
        """Возвращает (число каталогов, число файлов) без учёта корня."""
        dirs = files = 0
        stack = [self.root]
        while stack:
            for child in stack.pop().children.values():
                if child.is_dir:
                    dirs += 1
                    stack.append(child)
                else:
                    files += 1
        return dirs, files

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

    try:
        vfs = VFS.from_csv(a.vfs)
    except VfsError as e:
        print(f"Ошибка загрузки VFS: {e}", file=sys.stderr)
        return 1
    dirs, files = vfs.count()
    print(f"[debug] VFS '{vfs.name}' загружена: каталогов {dirs}, файлов {files}")
    
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
    sys.exit(main())