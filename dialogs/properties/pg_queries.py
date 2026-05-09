# dialogs/properties/pg_queries.py

"""
Centralized PostgreSQL catalog queries for database object properties.
"""

# --- Table Queries ---

GET_TABLE_DETAILS = """
    SELECT 
        pg_get_userbyid(c.relowner) as owner,
        n.nspname as schema_name,
        obj_description(c.oid, 'pg_class') as comment,
        c.relkind
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
        pg_get_userbyid(nspowner) as owner,
        obj_description(oid, 'pg_namespace') as comment
    FROM pg_namespace
    WHERE nspname = %s;
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
        seq_scan, seq_tup_read, idx_scan, idx_tup_fetch, 
        n_tup_ins, n_tup_upd, n_tup_del, n_tup_hot_upd, 
        n_live_tup, n_dead_tup,
        last_vacuum, last_autovacuum, last_analyze, last_autoanalyze
    FROM pg_stat_user_tables 
    WHERE schemaname = %s AND relname = %s;
"""

GET_TABLE_SIZE_STATS = """
    SELECT 
        pg_size_pretty(pg_total_relation_size(c.oid)) as total_size,
        pg_size_pretty(pg_relation_size(c.oid)) as table_size,
        pg_size_pretty(pg_total_relation_size(c.oid) - pg_relation_size(c.oid)) as index_size
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = %s AND c.relname = %s;
"""

GET_FUNCTION_STATS = """
    SELECT 
        calls, 
        total_time || ' ms' as total_time, 
        self_time || ' ms' as self_time
    FROM pg_stat_user_functions
    WHERE schemaname = %s AND funcname = %s;
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
        last_value, 
        log_cnt, 
        is_called
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
