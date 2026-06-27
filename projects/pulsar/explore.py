import duckdb
con = duckdb.connect()
con.execute("INSTALL ducklake; LOAD ducklake; INSTALL sqlite; LOAD sqlite;")
con.execute("ATTACH 'ducklake:sqlite:lake/catalog.sqlite' AS lake (READ_ONLY)")
con.execute("USE lake")
con.execute("INSTALL ui; LOAD ui;")
con.execute("CALL start_ui()")
input("UI en http://localhost:4213  (Enter para cerrar)")