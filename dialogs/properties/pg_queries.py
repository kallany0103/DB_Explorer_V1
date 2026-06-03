# dialogs/properties/pg_queries.py

"""
Centralized PostgreSQL catalog queries for database object properties.
"""

# --- Table Queries ---

GET_TABLE_DETAILS = """
    SELECT 
        pg_get_userbyid(c.relowner) AS "Owner",
        n.nspname AS "Schema",
        CASE c.relkind
            WHEN 'r' THEN 'Table'
            WHEN 'p' THEN 'Partitioned table'
            WHEN 'v' THEN 'View'
            WHEN 'm' THEN 'Materialized view'
            WHEN 'f' THEN 'Foreign table'
            WHEN 'S' THEN 'Sequence'
            ELSE c.relkind::text
        END AS "Object type",
        obj_description(c.oid, 'pg_class') AS "Comment",
        c.relispartition AS "Partitioned",
        COALESCE(c.reltuples::bigint, 0) AS "Estimated rows",
        pg_size_pretty(pg_total_relation_size(c.oid)) AS "Total size",
        (SELECT count(*) FROM pg_attribute a
         WHERE a.attrelid = c.oid AND a.attnum > 0 AND NOT a.attisdropped) AS "Columns"
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = %s AND c.relname = %s;
"""

GET_TABLE_COLUMNS = """
    SELECT 
        a.attname as name,
        pg_catalog.format_type(a.atttypid, a.atttypmod) as data_type,
        NOT a.attnotnull as nullable,
        pg_get_expr(d.adbin, d.adrelid) as default_value,
        col_description(a.attrelid, a.attnum) as comment
    FROM pg_attribute a
    LEFT JOIN pg_attrdef d ON a.attrelid = d.adrelid AND a.attnum = d.adnum
    WHERE a.attrelid = (SELECT c.oid FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace WHERE n.nspname = %s AND c.relname = %s)
    AND a.attnum > 0 AND NOT a.attisdropped
    ORDER BY a.attnum;
"""

GET_TABLE_CONSTRAINTS = """
    SELECT 
        conname as name,
        contype as type,
        pg_get_constraintdef(oid) as definition
    FROM pg_constraint
    WHERE conrelid = (SELECT c.oid FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace WHERE n.nspname = %s AND c.relname = %s);
"""

GET_TABLE_PRIVILEGES = """
    SELECT 
        COALESCE(grantee_name, 'PUBLIC') as grantee,
        string_agg(privilege_type, ', ') as privileges,
        grantor_name as grantor
    FROM (
        SELECT 
            pg_get_userbyid(grantee) as grantee_name,
            privilege_type,
            pg_get_userbyid(grantor) as grantor_name
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        CROSS JOIN aclexplode(c.relacl)
        WHERE n.nspname = %s AND c.relname = %s
    ) as acl
    GROUP BY grantee_name, grantor_name;
"""

# --- Schema Queries ---

GET_SCHEMA_DETAILS = """
    SELECT 
        pg_get_userbyid(n.oid) AS "Owner",
        obj_description(n.oid, 'pg_namespace') AS "Comment",
        count(*) FILTER (WHERE c.relkind IN ('r', 'p')) AS "Tables",
        count(*) FILTER (WHERE c.relkind = 'v') AS "Views",
        count(*) FILTER (WHERE c.relkind = 'm') AS "Mat. views",
        count(*) FILTER (WHERE c.relkind = 'S') AS "Sequences",
        (SELECT count(*) FROM pg_proc p WHERE p.pronamespace = n.oid) AS "Functions",
        pg_size_pretty(COALESCE(sum(pg_total_relation_size(c.oid))
            FILTER (WHERE c.relkind IN ('r', 'p', 'm')), 0)) AS "Total size"
    FROM pg_namespace n
    LEFT JOIN pg_class c ON c.relnamespace = n.oid
    WHERE n.nspname = %s
    GROUP BY n.oid, n.nspowner;
"""

GET_SCHEMA_PRIVILEGES = """
    SELECT 
        COALESCE(grantee_name, 'PUBLIC') as grantee,
        string_agg(privilege_type, ', ') as privileges,
        grantor_name as grantor
    FROM (
        SELECT 
            pg_get_userbyid(grantee) as grantee_name,
            privilege_type,
            pg_get_userbyid(grantor) as grantor_name
        FROM pg_namespace, aclexplode(nspacl)
        WHERE nspname = %s
    ) as acl
    GROUP BY grantee_name, grantor_name;
"""

GET_DEFAULT_PRIVILEGES = """
    SELECT
      pg_get_userbyid(d.defaclrole) AS owner,
      CASE d.defaclobjtype
        WHEN 'r' THEN 'Tables'
        WHEN 'S' THEN 'Sequences'
        WHEN 'f' THEN 'Functions'
        WHEN 'T' THEN 'Types'
      END AS object_type,
      array_to_string(d.defaclacl, ', ') AS privileges
    FROM pg_default_acl d
    LEFT JOIN pg_namespace n ON n.oid = d.defaclnamespace
    WHERE n.nspname = %s;
"""

# --- Role Queries ---

GET_ROLES = """
    SELECT rolname FROM pg_roles WHERE rolcanlogin = true ORDER BY rolname;
"""

# --- Function Queries ---

GET_FUNCTION_DETAILS = """
    SELECT 
        pg_get_userbyid(p.proowner) as owner,
        l.lanname as language,
        pg_get_function_result(p.oid) as result_type,
        pg_get_function_arguments(p.oid) as arguments,
        p.prosrc as definition,
        obj_description(p.oid, 'pg_proc') as comment
    FROM pg_proc p
    JOIN pg_namespace n ON n.oid = p.pronamespace
    JOIN pg_language l ON l.oid = p.prolang
    WHERE n.nspname = %s AND (p.proname || '(' || pg_get_function_arguments(p.oid) || ')') = %s;
"""

GET_FUNCTION_PRIVILEGES = """
    SELECT 
        COALESCE(grantee_name, 'PUBLIC') as grantee,
        string_agg(privilege_type, ', ') as privileges,
        grantor_name as grantor
    FROM (
        SELECT 
            pg_get_userbyid(grantee) as grantee_name,
            privilege_type,
            pg_get_userbyid(grantor) as grantor_name
        FROM pg_proc p
        JOIN pg_namespace n ON n.oid = p.pronamespace
        CROSS JOIN aclexplode(p.proacl)
        WHERE n.nspname = %s AND (p.proname || '(' || pg_get_function_arguments(p.oid) || ')') = %s
    ) as acl
    GROUP BY grantee_name, grantor_name;
"""

# --- Sequence Queries ---

GET_SEQUENCE_DETAILS = """
    SELECT 
        pg_get_userbyid(relowner) as owner,
        obj_description(c.oid, 'pg_class') as comment,
        s.seqstart as start_value,
        s.seqmin as min_value,
        s.seqmax as max_value,
        s.seqincrement as increment_by,
        s.seqcache as cache_size,
        s.seqcycle as is_cycled
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    JOIN pg_sequence s ON s.seqrelid = c.oid
    WHERE n.nspname = %s AND c.relname = %s;
"""

GET_SEQUENCE_PRIVILEGES = """
    SELECT 
        COALESCE(grantee_name, 'PUBLIC') as grantee,
        string_agg(privilege_type, ', ') as privileges,
        grantor_name as grantor
    FROM (
        SELECT 
            pg_get_userbyid(grantee) as grantee_name,
            privilege_type,
            pg_get_userbyid(grantor) as grantor_name
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        CROSS JOIN aclexplode(c.relacl)
        WHERE n.nspname = %s AND c.relname = %s
    ) as acl
    GROUP BY grantee_name, grantor_name;
"""

# --- Extension Queries ---

GET_EXTENSION_DETAILS = """
    SELECT 
        e.extname, 
        e.extversion, 
        n.nspname as schema_name,
        pg_get_userbyid(e.extowner) as owner,
        obj_description(e.oid, 'pg_extension') as comment
    FROM pg_extension e
    JOIN pg_namespace n ON n.oid = e.extnamespace
    WHERE e.extname = %s;
"""

# --- Language Queries ---

GET_LANGUAGE_DETAILS = """
    SELECT 
        lanname as name,
        pg_get_userbyid(lanowner) as owner,
        lanispl as is_pl,
        lanpltrusted as is_trusted,
        obj_description(oid, 'pg_language') as comment
    FROM pg_language
    WHERE lanname = %s;
"""

# --- Foreign Data Wrapper Queries ---

GET_FDW_DETAILS = """
    SELECT 
        fdwname as name,
        pg_get_userbyid(fdwowner) as owner,
        fdwhandler::regproc::text as handler,
        fdwvalidator::regproc::text as validator,
        array_to_string(fdwoptions, ', ') as options,
        obj_description(oid, 'pg_foreign_data_wrapper') as comment
    FROM pg_foreign_data_wrapper
    WHERE fdwname = %s;
"""

# --- Foreign Server Queries ---

GET_FOREIGN_SERVER_DETAILS = """
    SELECT 
        srvname as name,
        pg_get_userbyid(srvowner) as owner,
        srvtype as type,
        srvversion as version,
        array_to_string(srvoptions, ', ') as options,
        obj_description(oid, 'pg_foreign_server') as comment
    FROM pg_foreign_server
    WHERE srvname = %s;
"""

# --- User Mapping Queries ---

GET_USER_MAPPING_DETAILS = """
    SELECT 
        umuser::regrole::text as user_name,
        srvname as server_name,
        array_to_string(umoptions, ', ') as options
    FROM pg_user_mapping um
    JOIN pg_foreign_server s ON s.oid = um.umserver
    WHERE umuser::regrole::text = %s AND srvname = %s;
"""

# --- Statistics Queries ---

GET_TABLE_STATS = """
    SELECT 
        seq_scan AS "Sequential scans",
        idx_scan AS "Index scans",
        n_tup_ins AS "Inserts",
        n_tup_upd AS "Updates",
        n_tup_del AS "Deletes",
        last_vacuum AS "Last vacuum",
        last_autovacuum AS "Last autovacuum",
        last_analyze AS "Last analyze",
        last_autoanalyze AS "Last autoanalyze"
    FROM pg_stat_user_tables 
    WHERE schemaname = %s AND relname = %s;
"""

GET_TABLE_SIZE_STATS = """
    SELECT 
        pg_size_pretty(pg_total_relation_size(c.oid)) AS "Total size",
        pg_size_pretty(pg_relation_size(c.oid)) AS "Table size",
        pg_size_pretty(pg_total_relation_size(c.oid) - pg_relation_size(c.oid)) AS "Index size"
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = %s AND c.relname = %s;
"""

GET_FUNCTION_STATS = """
    SELECT 
        calls AS "Calls",
        total_exec_time::text || ' ms' AS "Total time",
        self_exec_time::text || ' ms' AS "Self time"
    FROM pg_stat_user_functions
    WHERE schemaname = %s AND funcname = %s;
"""

GET_TABLES_GROUP_STATS = """
    SELECT 
        count(*) AS "Object count",
        pg_size_pretty(COALESCE(sum(pg_total_relation_size(c.oid)), 0)) AS "Total size",
        COALESCE(sum(c.reltuples)::bigint, 0) AS "Estimated rows"
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = %s AND c.relkind IN ('r', 'p');
"""

GET_VIEWS_GROUP_STATS = """
    SELECT count(*) AS "Object count"
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = %s AND c.relkind = 'v';
"""

GET_MATVIEWS_GROUP_STATS = """
    SELECT 
        count(*) AS "Object count",
        pg_size_pretty(COALESCE(sum(pg_total_relation_size(c.oid)), 0)) AS "Total size"
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = %s AND c.relkind = 'm';
"""

GET_SEQUENCES_GROUP_STATS = """
    SELECT count(*) AS "Object count"
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = %s AND c.relkind = 'S';
"""

GET_FUNCTIONS_GROUP_STATS = """
    SELECT count(*) AS "Object count"
    FROM pg_proc p
    JOIN pg_namespace n ON n.oid = p.pronamespace
    WHERE n.nspname = %s;
"""

GET_FOREIGN_TABLES_GROUP_STATS = """
    SELECT count(*) AS "Object count"
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = %s AND c.relkind = 'f';
"""

GET_TRIGGER_FUNCTIONS_GROUP_STATS = """
    SELECT count(*) AS "Object count"
    FROM pg_proc p
    JOIN pg_namespace n ON n.oid = p.pronamespace
    WHERE n.nspname = %s AND p.prorettype = 'trigger'::regtype;
"""

GET_ALL_SCHEMAS_STATS = """
    SELECT 
        n.nspname AS "Schema",
        count(*) FILTER (WHERE c.relkind IN ('r', 'p')) AS "Tables",
        count(*) FILTER (WHERE c.relkind = 'v') AS "Views",
        pg_size_pretty(COALESCE(sum(pg_total_relation_size(c.oid))
            FILTER (WHERE c.relkind IN ('r', 'p', 'm')), 0)) AS "Total size"
    FROM pg_namespace n
    LEFT JOIN pg_class c ON c.relnamespace = n.oid
    WHERE n.nspname NOT LIKE 'pg_%%' AND n.nspname != 'information_schema'
    GROUP BY n.nspname
    ORDER BY n.nspname;
"""

GET_SCHEMA_STATS = """
    WITH counts AS (
        SELECT 
            count(*) FILTER (WHERE relkind = 'r') as tbl_count,
            count(*) FILTER (WHERE relkind = 'v') as view_count,
            count(*) FILTER (WHERE relkind = 'm') as mv_count,
            count(*) FILTER (WHERE relkind = 'S') as seq_count
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = %s
    ),
    funcs AS (
        SELECT count(*) as func_count
        FROM pg_proc p
        JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname = %s
    ),
    stats AS (
        SELECT 
            COALESCE(sum(seq_scan), 0) as seq_scans, 
            COALESCE(sum(idx_scan), 0) as idx_scans, 
            COALESCE(sum(n_tup_ins), 0) as inserts, 
            COALESCE(sum(n_tup_upd), 0) as updates, 
            COALESCE(sum(n_tup_del), 0) as deletes,
            pg_size_pretty(COALESCE(sum(pg_total_relation_size(c.oid)), 0)) as total_size
        FROM pg_namespace n
        LEFT JOIN pg_class c ON c.relnamespace = n.oid AND c.relkind IN ('r', 't', 'm')
        LEFT JOIN pg_stat_user_tables s ON s.relid = c.oid
        WHERE n.nspname = %s
    )
    SELECT 
        tbl_count as "Tables",
        view_count as "Views",
        mv_count as "Mat. Views",
        seq_count as "Sequences",
        func_count as "Functions",
        seq_scans as "Sequential Scans",
        idx_scans as "Index Scans",
        inserts as "Inserts",
        updates as "Updates",
        deletes as "Deletes",
        total_size as "Total Size"
    FROM counts, funcs, stats;
"""

GET_SEQUENCE_STATS = """
    SELECT 
        last_value AS "Last value",
        is_called AS "Called"
    FROM pg_sequences
    WHERE schemaname = %s AND sequencename = %s;
"""

GET_DATABASE_STATS = """
    SELECT 
        numbackends as "Backends",
        xact_commit as "Commits",
        xact_rollback as "Rollbacks",
        blks_read as "Blocks Read",
        blks_hit as "Blocks Hit",
        tup_returned as "Tuples Returned",
        tup_fetched as "Tuples Fetched",
        tup_inserted as "Tuples Inserted",
        tup_updated as "Tuples Updated",
        tup_deleted as "Tuples Deleted",
        pg_size_pretty(pg_database_size(datname)) as "Database Size"
    FROM pg_stat_database
    WHERE datname = %s;
"""

# --- Group Listing Queries ---

LIST_SCHEMAS = """
    SELECT 
        nspname as "Name",
        pg_get_userbyid(nspowner) as "Owner",
        obj_description(oid, 'pg_namespace') as "Comment"
    FROM pg_namespace
    WHERE nspname NOT LIKE 'pg_%%' AND nspname != 'information_schema'
    ORDER BY nspname;
"""

LIST_TABLES = """
    SELECT 
        c.relname as "Name",
        pg_get_userbyid(c.relowner) as "Owner",
        c.relispartition as "Partitioned?",
        obj_description(c.oid, 'pg_class') as "Comment"
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = %s AND c.relkind IN ('r', 'p')
    ORDER BY c.relname;
"""

LIST_VIEWS = """
    SELECT 
        c.relname as "Name",
        pg_get_userbyid(c.relowner) as "Owner",
        obj_description(c.oid, 'pg_class') as "Comment"
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = %s AND c.relkind = 'v'
    ORDER BY c.relname;
"""

LIST_FUNCTIONS = """
    SELECT 
        p.proname || '(' || pg_get_function_arguments(p.oid) || ')' as "Name",
        pg_get_userbyid(p.proowner) as "Owner",
        l.lanname as "Language",
        obj_description(p.oid, 'pg_proc') as "Comment"
    FROM pg_proc p
    JOIN pg_namespace n ON n.oid = p.pronamespace
    JOIN pg_language l ON l.oid = p.prolang
    WHERE n.nspname = %s
    ORDER BY 1;
"""

LIST_SEQUENCES = """
    SELECT 
        c.relname as "Name",
        pg_get_userbyid(c.relowner) as "Owner",
        obj_description(c.oid, 'pg_class') as "Comment"
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = %s AND c.relkind = 'S'
    ORDER BY c.relname;
"""

LIST_COLUMNS = """
    SELECT 
        a.attname as "Name",
        pg_catalog.format_type(a.atttypid, a.atttypmod) as "Data Type",
        NOT a.attnotnull as "Nullable?",
        pg_get_expr(d.adbin, d.adrelid) as "Default",
        col_description(a.attrelid, a.attnum) as "Comment"
    FROM pg_attribute a
    LEFT JOIN pg_attrdef d ON a.attrelid = d.adrelid AND a.attnum = d.adnum
    WHERE a.attrelid = (SELECT c.oid FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace WHERE n.nspname = %s AND c.relname = %s)
    AND a.attnum > 0 AND NOT a.attisdropped
    ORDER BY a.attnum;
"""

LIST_CONSTRAINTS = """
    SELECT 
        conname as "Name",
        contype as "Type",
        pg_get_constraintdef(oid) as "Definition"
    FROM pg_constraint
    WHERE conrelid = (SELECT c.oid FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace WHERE n.nspname = %s AND c.relname = %s)
    ORDER BY conname;
"""

LIST_INDEXES = """
    SELECT 
        indexname as "Name",
        indexdef as "Definition"
    FROM pg_indexes
    WHERE schemaname = %s AND tablename = %s
    ORDER BY indexname;
"""

LIST_TRIGGERS = """
    SELECT 
        t.tgname as "Name",
        pg_get_triggerdef(t.oid) as "Definition"
    FROM pg_trigger t
    JOIN pg_class c ON t.tgrelid = c.oid
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = %s AND c.relname = %s
    AND NOT t.tgisinternal
    ORDER BY t.tgname;
"""

GET_TABLE_TRIGGERS = """
    SELECT 
        t.tgname as name,
        pg_get_triggerdef(t.oid) as definition
    FROM pg_trigger t
    JOIN pg_class c ON t.tgrelid = c.oid
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = %s AND c.relname = %s
    AND NOT t.tgisinternal;
"""

GET_TRIGGER_DETAILS = """
    SELECT 
        t.tgname AS name,
        c.relname AS table_name,
        n.nspname AS schema_name,
        t.tgenabled AS enabled,
        p.proname AS function_name,
        CASE 
            WHEN (t.tgtype & 2) = 2 THEN 'BEFORE'
            WHEN (t.tgtype & 64) = 64 THEN 'INSTEAD OF'
            ELSE 'AFTER'
        END AS timing,
        TRIM(BOTH ' ' FROM (
            CASE WHEN (t.tgtype & 4) = 4 THEN 'INSERT ' ELSE '' END ||
            CASE WHEN (t.tgtype & 8) = 8 THEN 'DELETE ' ELSE '' END ||
            CASE WHEN (t.tgtype & 16) = 16 THEN 'UPDATE ' ELSE '' END ||
            CASE WHEN (t.tgtype & 32) = 32 THEN 'TRUNCATE ' ELSE '' END
        )) AS events,
        CASE WHEN (t.tgtype & 1) = 1 THEN 'ROW' ELSE 'STATEMENT' END AS level,
        pg_get_triggerdef(t.oid) as definition,
        obj_description(t.oid, 'pg_trigger') as comment
    FROM pg_trigger t
    JOIN pg_class c ON t.tgrelid = c.oid
    JOIN pg_namespace n ON n.oid = c.relnamespace
    JOIN pg_proc p ON p.oid = t.tgfoid
    WHERE n.nspname = %s AND t.tgname = %s;
"""
