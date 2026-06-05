# WAMP DB bridge

Goal: WeMos POSTs readings to WAMP (PHP) → your existing MySQL stores them → web reads from MySQL.

## 1) Copy files into WAMP
Copy this whole folder into your WAMP web root as:
- `C:\wamp64\www\shrimp-db\`

So these URLs exist:
- `http://localhost/shrimp-db/dashboard.html`
- `http://localhost/shrimp-db/insert_reading.php`
- `http://localhost/shrimp-db/get_latest.php`

## 2) Use your existing DB/table
This project is configured for:
- DB: `shrimply_smart`
- Table: `api_feederreading`
- Columns: `timestamp`, `servo_state`, `distance_cm`

If your table uses different column names, tell me and I’ll adjust the PHP.

## 3) API key
Default API key in `insert_reading.php` is:
- `shrimp-key-123`

Set the same key in the WeMos sketch.

## 4) Test insert manually
Use a tool like Postman or just a browser plugin to POST:
- `distance_cm=12.3`  (or `distance=12.3`)
- `servo_state=ON`    (or `servoOnOrOff=ON`)
- `api_key=shrimp-key-123`

Then open `dashboard.html`.
