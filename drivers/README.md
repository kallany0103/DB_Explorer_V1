# CData Drivers

This folder contains CData connector `.whl` packages for Windows.

## Folder Structure

```
drivers/
└── windows/
    └── x64/        # Windows 64-bit .whl files (place them here)
```

> `.whl` files are excluded from version control. Download them from the CData portal and drop into `drivers\windows\x64\`.

---

## Step 1 — Place the driver files

Download the following from the CData portal and place them in `drivers\windows\x64\`:

- `cdata_servicenow_connector-25.0.9539-cp311-cp311-win_amd64.whl`
- `cdata_csv_connector-25.0.9539-cp311-cp311-win_amd64.whl`

---

## Step 2 — Activate the virtual environment

```cmd
venv\Scripts\activate
```

---

## Step 3 — Install all dependencies (including CData drivers)

```cmd
pip install -r requirements.txt
```

> ⚠️ If you get `[WinError 5] Access is denied`, the app is running and has the driver files locked.
> Close the application completely and retry.

---

## Step 4 — Activate the CData licenses

The drivers require a one-time license activation (free community edition).
Run each installer **from its own directory**:

### ServiceNow
```cmd
cd "venv\Lib\site-packages\cdata\installlic_servicenow"
install-license.exe
```

### CSV
```cmd
cd "venv\Lib\site-packages\cdata\installlic_csv"
install-license.exe
```

When prompted, enter your **name** and **email** to activate the free community license.
You should see:
```
License installation succeeded.
```

> ⚠️ Do NOT run `install-license.exe` from the project root — it will fail with
> `WARNING: Failed to open file 'prod.inf' in the current directory.`
> Always `cd` into the installer folder first.

---

## Notes

- Drivers are **Python 3.11 (`cp311`)** specific. Ensure your Python version matches.
- The community edition is **free forever** but requires one-time email registration.
- The community edition has a **100-row limit** per query.
- If you have a paid product key, pass it as a parameter: `install-license.exe YOUR_PRODUCT_KEY`
