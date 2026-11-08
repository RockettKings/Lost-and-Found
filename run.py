from app import create_app

app = create_app()

if __name__ == "__main__":
    # Enable the debugger explicitly with `flask --app run run --debug` locally.
    app.run()
