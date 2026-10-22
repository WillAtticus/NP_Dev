import os

def setup():
    d = os.path.expanduser("~/.streamlit")
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "credentials.toml"), "w", encoding="utf-8") as f:
        f.write('[general]\nemail = ""\n')
    with open(os.path.join(d, "config.toml"), "w", encoding="utf-8") as f:
        f.write('[server]\nheadless = true\n')
    print("Streamlit configured headless successfully!")

if __name__ == "__main__":
    setup()
