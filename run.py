# run.py
from movie_lottery import create_app, db

app = create_app()

# --- НАЧАЛО НОВОГО КОДА ---
# Создаем специальную команду для принудительного создания таблиц
@app.cli.command("create-tables")
def create_tables():
    """Создает все таблицы базы данных."""
    with app.app_context():
        print("Создание таблиц базы данных...")
        db.create_all()
        print("Таблицы успешно созданы.")
# --- КОНЕЦ НОВОГО КОДА ---

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)