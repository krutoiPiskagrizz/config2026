
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

run_test "1. Минимальная VFS (один файл)" 0 --vfs vfs/minimal.csv
run_test "2. VFS с несколькими файлами и папками" 0 --vfs vfs/several.csv
run_test "3. VFS с 3+ уровнями вложенности" 0 --vfs vfs/deep.csv
run_test "4. Файл VFS не найден (ожидается ошибка)" 1 --vfs vfs/missing.csv
run_test "5. Неверный формат: заголовок (ожидается ошибка)" 1 --vfs vfs/bad_header.csv
run_test "6. Неверный формат: base64 (ожидается ошибка)" 1 --vfs vfs/bad_base64.csv
run_test "7. Все команды: стартовый скрипт на глубокой VFS" 0 \
    --vfs vfs/deep.csv --script tests/all_commands.emu

echo "=============================="
if [ "$FAILED" -eq 0 ]; then
    echo "ИТОГ: ошибок нет, все тесты пройдены"
    exit 0
else
    echo "ИТОГ: тестов с ошибками: $FAILED"
    exit 1
fi
