import argparse
import os
import shlex
import sys
import base64
import binascii
import csv
import posixpath
import calendar
import datetime
import time

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
    
    def find(self, abspath):
        """Возвращает Node по абсолютному пути или None, если пути нет."""
        node = self.root
        for part in [x for x in abspath.split("/") if x]:
            if not node.is_dir or part not in node.children:
                return None
            node = node.children[part]
        return node

class Shell:
    def __init__(self, vfs):
        self.vfs = vfs
        self.cwd = "/"  # текущий каталог
        self.start = time.time()  # для uptime
        self.running = True
        self.commands = {
            "ls": (self.cmd_ls, "ls [-l] [путь...]", "список содержимого каталога (-l - подробно)"),
            "cd": (self.cmd_cd, "cd [путь]", "сменить каталог (без аргумента - в корень)"),
            "uptime": (self.cmd_uptime, "uptime", "вывести информацию о времени работы системы"),
            "cal": (self.cmd_cal, "cal [месяц] [год]", "вывести календарь"),
            "rm": (self.cmd_rm, "rm [-r] путь...", "удалить файлы (-r - каталоги), только в памяти"),
            "help": (self.cmd_help, "help", "список команд с описанием"),
            "exit": (self.cmd_exit, "exit", "завершить работу эмулятора"),
        }

    def prompt(self):
        return f"user@{self.vfs.name}:{self.cwd}$ "

    def abspath(self, p):
        """Превращает относительный путь в абсолютный (учитывает . и ..)."""
        return posixpath.normpath(posixpath.join(self.cwd, p))

    def execute(self, line):
        try:
            argv = shlex.split(line)
        except ValueError as e:
            raise ShellError(f"ошибка разбора: {e}")
        if not argv:
            return
        name, args = argv[0], argv[1:]
        if name not in self.commands:
            raise ShellError(f"{name}: команда не найдена")
        self.commands[name][0](args)

    @staticmethod
    def split_opts(args, allowed, cmd):
        """Делит аргументы на ключи (-l) и остальное (пути)."""
        flags, rest = set(), []
        for a in args:
            if a.startswith("-") and len(a) > 1:
                for ch in a[1:]:
                    if ch not in allowed:
                        raise ShellError(f"{cmd}: неверный ключ -- '{ch}'")
                    flags.add(ch)
            else:
                rest.append(a)
        return flags, rest
    
    def cmd_ls(self, args):
        flags, paths = self.split_opts(args, "l", "ls")
        paths = paths or ["."]
        for i, p in enumerate(paths):
            node = self.vfs.find(self.abspath(p))
            if node is None:
                raise ShellError(f"ls: не удалось получить доступ к '{p}': нет такого файла или каталога")
            if len(paths) > 1:
                print(f"{p}:")
            if node.is_dir:
                items = sorted(node.children.values(), key=lambda n: n.name)
            else:
                items = [node]
            for n in items:
                label = p if n is node else n.name + ("/" if n.is_dir else "")
                if "l" in flags:
                    size = 0 if n.is_dir else len(n.data)
                    print(f"{'d' if n.is_dir else '-'} {size:>8} {label}")
                else:
                    print(label)
            if len(paths) > 1 and i < len(paths) - 1:
                print()
                
                
    def cmd_cd(self, args):
        if len(args) > 1:
            raise ShellError("cd: слишком много аргументов")
        target = self.abspath(args[0]) if args else "/"
        node = self.vfs.find(target)
        if node is None:
            raise ShellError(f"cd: {args[0]}: нет такого файла или каталога")
        if not node.is_dir:
            raise ShellError(f"cd: {args[0]}: не является каталогом")
        self.cwd = target

    def cmd_uptime(self, args):
        if args:
            raise ShellError("uptime: команда не принимает аргументов")
        secs = int(time.time() - self.start)
        h, rem = divmod(secs, 3600)
        m, s = divmod(rem, 60)
        now = datetime.datetime.now().strftime("%H:%M:%S")
        print(f" {now} up {h:02d}:{m:02d}:{s:02d}, 1 user")

    def cmd_cal(self, args):
        try:
            nums = [int(a) for a in args]
        except ValueError:
            raise ShellError("cal: аргументы должны быть числами")
        today = datetime.date.today()
        if len(nums) == 0:
            year, month = today.year, today.month
        elif len(nums) == 1:
            year, month = nums[0], None  # весь год
        elif len(nums) == 2:
            month, year = nums
        else:
            raise ShellError("cal: слишком много аргументов")
        if not 1 <= year <= 9999:
            raise ShellError(f"cal: неверный год: {year}")
        if month is not None and not 1 <= month <= 12:
            raise ShellError(f"cal: неверный месяц: {month}")
        cal = calendar.TextCalendar(firstweekday=0)
        print(cal.formatyear(year) if month is None else cal.formatmonth(year, month))
        
    def cmd_rm(self, args):
        flags, paths = self.split_opts(args, "r", "rm")
        if not paths:
            raise ShellError("rm: не указан операнд")
        for p in paths:
            ab = self.abspath(p)
            node = self.vfs.find(ab)
            if node is None:
                raise ShellError(f"rm: невозможно удалить '{p}': нет такого файла или каталога")
            if ab == "/":
                raise ShellError("rm: нельзя удалить корневой каталог")
            if node.is_dir and "r" not in flags:
                raise ShellError(f"rm: невозможно удалить '{p}': это каталог (нужен ключ -r)")
            if self.cwd == ab or self.cwd.startswith(ab + "/"):
                raise ShellError(f"rm: невозможно удалить '{p}': это текущий каталог или его родитель")
            parent = self.vfs.find(posixpath.dirname(ab))
            del parent.children[node.name]
            
    def cmd_help(self, args):
        if args:
            raise ShellError("help: команда не принимает аргументов")
        for _, usage, desc in self.commands.values():
            print(f"  {usage:<22} {desc}")

    def cmd_exit(self, args):
        if args:
            raise ShellError("exit: команда не принимает аргументов")
        self.running = False

    def run_script(self, path):
        """Выполняет скрипт: показывает ввод и вывод, ошибочные строки пропускает."""
        try:
            with open(path, encoding="utf-8") as f:
                lines = f.read().splitlines()
        except OSError as e:
            print(f"Ошибка: не удалось открыть стартовый скрипт: {e}", file=sys.stderr)
            return
        for n, line in enumerate(lines, 1):
            if not self.running:
                break
            print(self.prompt() + line)
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            try:
                self.execute(line)
            except ShellError as e:
                print(e, file=sys.stderr)
                print(f"[скрипт] ошибка в строке {n}, строка пропущена", file=sys.stderr)

    def repl(self):
        while self.running:
            try:
                line = input(self.prompt())
            except EOFError:
                print()
                break
            except KeyboardInterrupt:
                print()
                continue
            try:
                self.execute(line)
            except ShellError as e:
                print(e, file=sys.stderr)


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
    
    shell = Shell(vfs)
    if a.script:
        shell.run_script(a.script)
    shell.repl()
    return 0


if __name__ == "__main__":
    sys.exit(main())