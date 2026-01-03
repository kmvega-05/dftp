# dFTP Streamlit UI

Run the UI from the `client` folder:

```bash
pip install -r client/requirements.txt
streamlit run client/ui/app.py
```

Features:
- Connect to FTP host/port
- Enter commands in a terminal-like input
- History panel with timestamps and responses
- Basic progress indications for `STOR` and `RETR`
- Errors shown in the UI (app does not crash)
