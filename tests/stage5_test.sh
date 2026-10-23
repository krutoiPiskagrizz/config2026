cd "$(dirname "$0")/.."

FAILED=0
run_test() {
    local title="$1" expected="$2"
    shift 2
    echo "=== $title ==="
    echo "exit" | ./run.sh "$@"
    local code=$?
    if [ "$code" -eq "$expected" ]; then
        echo ">>> OK (код возврата $code)"
    else
        echo ">>> ОШИБКА: ожидался код $expected, получен $code"
        FAILED=$((FAILED + 1))
    fi
    echo
}
run_test "1. Команды rm и help на VFS с несколькими файлами" 0 \
    --vfs vfs/several.csv --script tests/commands_stage5.emu
run_test "2. Команды rm и help на глубокой VFS (ошибки: нет таких путей)" 0 \
    --vfs vfs/deep.csv --script tests/commands_stage5.emu
run_test "3. Ошибка загрузки VFS (ожидается код 1)" 1 --vfs vfs/missing.csv

echo "=== 4. Файл VFS на диске не изменился после rm ==="
BEFORE=$(cksum < vfs/several.csv)
printf 'rm -r docs\nrm hello.txt\nexit\n' | ./run.sh --vfs vfs/several.csv > /dev/null
AFTER=$(cksum < vfs/several.csv)
if [ "$BEFORE" = "$AFTER" ]; then
    echo ">>> OK (файл не изменился)"
else
    echo ">>> ОШИБКА: файл VFS был изменён"
    FAILED=$((FAILED + 1))
fi
echo
echo "=============================="
if [ "$FAILED" -eq 0 ]; then
    echo "ИТОГ: ошибок нет, все тесты пройдены"
    exit 0
else
    echo "ИТОГ: тестов с ошибками: $FAILED"
    exit 1
fi
