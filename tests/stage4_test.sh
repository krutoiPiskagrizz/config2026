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
run_test "1. Все команды этапа 4 на глубокой VFS (со стартовым скриптом)" 0 \
    --vfs vfs/deep.csv --script tests/commands_stage4.emu
run_test "2. Команды на VFS с несколькими файлами" 0 \
    --vfs vfs/several.csv --script tests/commands_stage4.emu
run_test "3. Команды на минимальной VFS" 0 \
    --vfs vfs/minimal.csv --script tests/commands_stage4.emu
run_test "4. Ошибка загрузки VFS (ожидается код 1)" 1 --vfs vfs/missing.csv

echo "=============================="
if [ "$FAILED" -eq 0 ]; then
    echo "ИТОГ: ошибок нет, все тесты пройдены"
    exit 0
else
    echo "ИТОГ: тестов с ошибками: $FAILED"
    exit 1
fi
