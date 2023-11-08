#!/bin/bash

# Name of the SQLite database
db_name="monarch.db"

# Remove database if it already exists
if [ -f $db_name ] ; then
    rm $db_name
fi

# # Start SQLite and import the data
# sqlite3 $db_name <<EOF
# .mode tabs
# .import monarch-kg_nodes.tsv nodes
# .import monarch-kg_edges.tsv edges
# EOF

db_name="monarch.duckdb"


# Start DuckDB and import the data
duckdb $db_name <<EOF
CREATE TABLE nodes AS SELECT * FROM read_csv_auto('monarch-kg_nodes.tsv');
CREATE TABLE edges AS SELECT * FROM read_csv_auto('monarch-kg_edges.tsv');
CREATE TABLE denormalized AS SELECT * FROM read_csv_auto('monarch-kg-denormalized-edges.tsv')
EOF