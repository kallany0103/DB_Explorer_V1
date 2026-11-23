# dialogs/properties/oracle_queries.py

"""
Centralized Oracle catalog queries for database object properties and statistics.
All queries use standard data dictionary views (ALL_*) compatible across all Oracle versions.
"""

# ============================================================================
# Group Collections Queries
# ============================================================================

LIST_SCHEMAS = """
    SELECT 
        username AS "Schema",
        created AS "Created"
    FROM all_users
    ORDER BY username
"""

LIST_TABLES = """
    SELECT 
        t.table_name AS "Name",
        t.owner AS "Owner",
        t.num_rows AS "Estimated rows",
        t.tablespace_name AS "Tablespace",
        c.comments AS "Comment"
    FROM all_tables t
    LEFT JOIN all_tab_comments c ON c.owner = t.owner AND c.table_name = t.table_name
    WHERE t.owner = :own
    ORDER BY t.table_name
"""

LIST_VIEWS = """
    SELECT 
        v.view_name AS "Name",
        v.owner AS "Owner",
        c.comments AS "Comment"
    FROM all_views v
    LEFT JOIN all_tab_comments c ON c.owner = v.owner AND c.table_name = v.view_name
    WHERE v.owner = :own
    ORDER BY v.view_name
"""

LIST_MATVIEWS = """
    SELECT 
        m.mview_name AS "Name",
        m.owner AS "Owner",
        m.refresh_mode AS "Refresh Mode",
        m.refresh_method AS "Refresh Method",
        c.comments AS "Comment"
    FROM all_mviews m
    LEFT JOIN all_tab_comments c ON c.owner = m.owner AND c.table_name = m.mview_name
    WHERE m.owner = :own
    ORDER BY m.mview_name
"""

LIST_SEQUENCES = """
    SELECT 
        sequence_name AS "Name",
        sequence_owner AS "Owner",
        min_value AS "Min Value",
        max_value AS "Max Value",
        increment_by AS "Increment By",
        last_number AS "Last Number"
    FROM all_sequences
    WHERE sequence_owner = :own
    ORDER BY sequence_name
"""

LIST_PROCEDURES = """
    SELECT 
        object_name AS "Name",
        owner AS "Owner",
        status AS "Status",
        created AS "Created",
        last_ddl_time AS "Last Modified"
    FROM all_objects
    WHERE owner = :own AND object_type = 'PROCEDURE'
    ORDER BY object_name
"""

LIST_FUNCTIONS = """
    SELECT 
        object_name AS "Name",
        owner AS "Owner",
        status AS "Status",
        created AS "Created",
        last_ddl_time AS "Last Modified"
    FROM all_objects
    WHERE owner = :own AND object_type = 'FUNCTION'
    ORDER BY object_name
"""

LIST_PACKAGES = """
    SELECT 
        object_name AS "Name",
        owner AS "Owner",
        status AS "Status",
        created AS "Created",
        last_ddl_time AS "Last Modified"
    FROM all_objects
    WHERE owner = :own AND object_type = 'PACKAGE'
    ORDER BY object_name
"""

LIST_TRIGGERS = """
    SELECT 
        trigger_name AS "Name",
        owner AS "Owner",
        trigger_type AS "Type",
        triggering_event AS "Event",
        table_name AS "Table",
        status AS "Status"
    FROM all_triggers
    WHERE owner = :own
    ORDER BY trigger_name
"""

LIST_SYNONYMS = """
    SELECT 
        synonym_name AS "Name",
        owner AS "Owner",
        table_owner AS "Target Owner",
        table_name AS "Target Table",
        db_link AS "Database Link"
    FROM all_synonyms
    WHERE owner = :own
    ORDER BY synonym_name
"""

LIST_DBLINKS = """
    SELECT 
        db_link AS "Name",
        owner AS "Owner",
        username AS "User",
        host AS "Host",
        created AS "Created"
    FROM all_db_links
    WHERE owner = :own OR owner = 'PUBLIC'
    ORDER BY db_link
"""

LIST_JAVA = """
    SELECT 
        object_name AS "Name",
        object_type AS "Type",
        owner AS "Owner",
        status AS "Status",
        last_ddl_time AS "Last Modified"
    FROM all_objects
    WHERE owner = :own AND object_type LIKE 'JAVA %'
    ORDER BY object_type, object_name
"""

LIST_COLUMNS = """
    SELECT 
        c.column_name AS "Name",
        c.data_type AS "Data Type",
        c.nullable AS "Nullable",
        c.data_default AS "Default",
        cm.comments AS "Comment"
    FROM all_tab_columns c
    LEFT JOIN all_col_comments cm ON cm.owner = c.owner AND cm.table_name = c.table_name AND cm.column_name = c.column_name
    WHERE c.owner = :own AND c.table_name = :obj
    ORDER BY c.column_id
"""

LIST_CONSTRAINTS = """
    SELECT 
        constraint_name AS "Name",
        CASE constraint_type
            WHEN 'P' THEN 'Primary Key'
            WHEN 'R' THEN 'Foreign Key'
            WHEN 'U' THEN 'Unique'
            WHEN 'C' THEN 'Check'
            ELSE constraint_type
        END AS "Type",
        search_condition AS "Definition",
        status AS "Status"
    FROM all_constraints
    WHERE owner = :own AND table_name = :obj
    ORDER BY constraint_name
"""

LIST_INDEXES = """
    SELECT 
        index_name AS "Name",
        index_type AS "Type",
        uniqueness AS "Uniqueness",
        status AS "Status",
        tablespace_name AS "Tablespace"
    FROM all_indexes
    WHERE owner = :own AND table_name = :obj
    ORDER BY index_name
"""

LIST_TABLE_TRIGGERS = """
    SELECT 
        trigger_name AS "Name",
        trigger_type AS "Type",
        triggering_event AS "Event",
        status AS "Status"
    FROM all_triggers
    WHERE table_owner = :own AND table_name = :obj
    ORDER BY trigger_name
"""

# ============================================================================
# Single Object Details Queries
# ============================================================================

GET_TABLE_DETAILS = """
    SELECT 
        t.owner AS "Owner",
        t.table_name AS "Name",
        'Table' AS "Object type",
        t.tablespace_name AS "Tablespace",
        t.status AS "Status",
        t.num_rows AS "Estimated rows",
        (SELECT count(*) FROM all_tab_columns c WHERE c.owner = t.owner AND c.table_name = t.table_name) AS "Columns",
        c.comments AS "Comment"
    FROM all_tables t
    LEFT JOIN all_tab_comments c ON c.owner = t.owner AND c.table_name = t.table_name
    WHERE t.owner = :own AND t.table_name = :obj
"""

GET_VIEW_DETAILS = """
    SELECT 
        v.owner AS "Owner",
        v.view_name AS "Name",
        'View' AS "Object type",
        (SELECT count(*) FROM all_tab_columns c WHERE c.owner = v.owner AND c.table_name = v.view_name) AS "Columns",
        c.comments AS "Comment"
    FROM all_views v
    LEFT JOIN all_tab_comments c ON c.owner = v.owner AND c.table_name = v.view_name
    WHERE v.owner = :own AND v.view_name = :obj
"""

GET_MATVIEW_DETAILS = """
    SELECT 
        m.owner AS "Owner",
        m.mview_name AS "Name",
        'Materialized view' AS "Object type",
        m.refresh_mode AS "Refresh Mode",
        m.refresh_method AS "Refresh Method",
        m.build_mode AS "Build Mode",
        m.fast_refreshable AS "Fast Refreshable",
        m.last_refresh_date AS "Last Refresh Date",
        c.comments AS "Comment"
    FROM all_mviews m
    LEFT JOIN all_tab_comments c ON c.owner = m.owner AND c.table_name = m.mview_name
    WHERE m.owner = :own AND m.mview_name = :obj
"""

GET_TABLE_COLUMNS = """
    SELECT 
        c.column_name,
        c.data_type,
        c.data_length,
        c.data_precision,
        c.data_scale,
        c.nullable,
        c.data_default,
        cm.comments
    FROM all_tab_columns c
    LEFT JOIN all_col_comments cm ON cm.owner = c.owner AND cm.table_name = c.table_name AND cm.column_name = c.column_name
    WHERE c.owner = :own AND c.table_name = :obj
    ORDER BY c.column_id
"""

GET_PRIMARY_KEYS = """
    SELECT cols.column_name
    FROM all_constraints cons
    JOIN all_cons_columns cols ON cons.constraint_name = cols.constraint_name AND cons.owner = cols.owner
    WHERE cons.constraint_type = 'P' AND cons.owner = :own AND cons.table_name = :obj
"""

GET_TABLE_CONSTRAINTS = """
    SELECT 
        constraint_name AS name,
        CASE constraint_type
            WHEN 'P' THEN 'Primary Key'
            WHEN 'R' THEN 'Foreign Key'
            WHEN 'U' THEN 'Unique'
            WHEN 'C' THEN 'Check'
            ELSE constraint_type
        END AS type,
        search_condition AS definition
    FROM all_constraints
    WHERE owner = :own AND table_name = :obj
    ORDER BY constraint_name
"""

GET_SEQUENCE_DETAILS = """
    SELECT 
        sequence_owner AS "Owner",
        min_value AS "Min value",
        max_value AS "Max value",
        increment_by AS "Increment by",
        cycle_flag AS "Cycle",
        order_flag AS "Order",
        cache_size AS "Cache size",
        last_number AS "Last number"
    FROM all_sequences
    WHERE sequence_owner = :own AND sequence_name = :obj
"""

GET_PROCEDURE_OR_FUNCTION_DETAILS = """
    SELECT 
        owner AS "Owner",
        object_name AS "Name",
        object_type AS "Object type",
        status AS "Status",
        created AS "Created",
        last_ddl_time AS "Last modified"
    FROM all_objects
    WHERE owner = :own AND object_name = :obj AND object_type IN ('PROCEDURE', 'FUNCTION', 'PACKAGE')
"""

GET_TRIGGER_DETAILS = """
    SELECT 
        owner AS "Owner",
        trigger_name AS "Name",
        trigger_type AS "Type",
        triggering_event AS "Event",
        table_owner AS "Table owner",
        table_name AS "Table name",
        status AS "Status",
        action_type AS "Action type"
    FROM all_triggers
    WHERE owner = :own AND trigger_name = :obj
"""

GET_SYNONYM_DETAILS = """
    SELECT 
        owner AS "Owner",
        synonym_name AS "Name",
        table_owner AS "Target owner",
        table_name AS "Target name",
        db_link AS "Database link"
    FROM all_synonyms
    WHERE owner = :own AND synonym_name = :obj
"""

GET_SCHEMA_DETAILS = """
    SELECT 
        u.username AS "Schema",
        u.created AS "Created",
        (SELECT count(*) FROM all_tables t WHERE t.owner = u.username) AS "Tables",
        (SELECT count(*) FROM all_views v WHERE v.owner = u.username) AS "Views",
        (SELECT count(*) FROM all_sequences s WHERE s.sequence_owner = u.username) AS "Sequences",
        (SELECT count(*) FROM all_objects o WHERE o.owner = u.username AND o.object_type IN ('FUNCTION', 'PROCEDURE', 'PACKAGE')) AS "Routines"
    FROM all_users u
    WHERE u.username = :own
"""

# ============================================================================
# Statistics Queries (used by inspector_stats.py)
# ============================================================================

GET_TABLE_STATS = """
    SELECT 
        num_rows AS "Number of rows",
        blocks AS "Blocks",
        empty_blocks AS "Empty blocks",
        avg_space AS "Average free space",
        chain_cnt AS "Chain count",
        avg_row_len AS "Average row length",
        sample_size AS "Sample size",
        last_analyzed AS "Last analyzed"
    FROM all_tables
    WHERE owner = :own AND table_name = :obj
"""

GET_COLUMN_STATS = """
    SELECT 
        column_name AS "Column",
        num_distinct AS "Distinct values",
        density AS "Density",
        num_nulls AS "Nulls count",
        avg_col_len AS "Average length",
        last_analyzed AS "Last analyzed"
    FROM all_tab_col_statistics
    WHERE owner = :own AND table_name = :obj
    ORDER BY column_name
"""

GET_INDEX_STATS = """
    SELECT 
        index_name AS "Index",
        uniqueness AS "Uniqueness",
        blevel AS "B-Tree Level",
        leaf_blocks AS "Leaf blocks",
        distinct_keys AS "Distinct keys",
        clustering_factor AS "Clustering factor",
        num_rows AS "Number of rows",
        last_analyzed AS "Last analyzed"
    FROM all_indexes
    WHERE owner = :own AND table_name = :obj
    ORDER BY index_name
"""

GET_SCHEMA_STATS = """
    SELECT 
        object_type AS "Object Type",
        count(*) AS "Count",
        sum(CASE WHEN status = 'VALID' THEN 1 ELSE 0 END) AS "Valid",
        sum(CASE WHEN status = 'INVALID' THEN 1 ELSE 0 END) AS "Invalid"
    FROM all_objects
    WHERE owner = :own
    GROUP BY object_type
    ORDER BY object_type
"""

GET_DATABASE_STATS = """
    SELECT 
        sys_context('USERENV', 'DB_NAME') AS "Database Name",
        sys_context('USERENV', 'SESSION_USER') AS "Session User",
        sys_context('USERENV', 'CURRENT_SCHEMA') AS "Current Schema",
        sys_context('USERENV', 'INSTANCE_NAME') AS "Instance Name",
        sys_context('USERENV', 'SERVER_HOST') AS "Server Host",
        sys_context('USERENV', 'SERVICE_NAME') AS "Service Name"
    FROM dual
"""

GET_ALL_SCHEMAS_STATS = """
    SELECT 
        owner AS "Schema",
        count(*) AS "Total Objects",
        sum(CASE WHEN object_type = 'TABLE' THEN 1 ELSE 0 END) AS "Tables",
        sum(CASE WHEN object_type = 'VIEW' THEN 1 ELSE 0 END) AS "Views"
    FROM all_objects
    GROUP BY owner
    ORDER BY owner
"""

GET_TABLES_GROUP_STATS = """
    SELECT 
        count(*) AS "Table Count",
        sum(nvl(num_rows, 0)) AS "Total Estimated Rows",
        sum(nvl(blocks, 0)) AS "Total Blocks"
    FROM all_tables
    WHERE owner = :own
"""

GET_VIEWS_GROUP_STATS = """
    SELECT count(*) AS "View Count"
    FROM all_views
    WHERE owner = :own
"""

GET_MATVIEWS_GROUP_STATS = """
    SELECT count(*) AS "Materialized View Count"
    FROM all_mviews
    WHERE owner = :own
"""

GET_SEQUENCES_GROUP_STATS = """
    SELECT count(*) AS "Sequence Count"
    FROM all_sequences
    WHERE sequence_owner = :own
"""

GET_FUNCTIONS_GROUP_STATS = """
    SELECT count(*) AS "Function Count"
    FROM all_objects
    WHERE owner = :own AND object_type = 'FUNCTION'
"""

GET_PROCEDURES_GROUP_STATS = """
    SELECT count(*) AS "Procedure Count"
    FROM all_objects
    WHERE owner = :own AND object_type = 'PROCEDURE'
"""

GET_PACKAGES_GROUP_STATS = """
    SELECT count(*) AS "Package Count"
    FROM all_objects
    WHERE owner = :own AND object_type = 'PACKAGE'
"""

GET_TRIGGERS_GROUP_STATS = """
    SELECT count(*) AS "Trigger Count"
    FROM all_triggers
    WHERE owner = :own
"""

GET_SYNONYMS_GROUP_STATS = """
    SELECT count(*) AS "Synonym Count"
    FROM all_synonyms
    WHERE owner = :own
"""

GET_DBLINKS_GROUP_STATS = """
    SELECT count(*) AS "Database Link Count"
    FROM all_db_links
    WHERE owner = :own OR owner = 'PUBLIC'
"""

GET_JAVA_GROUP_STATS = """
    SELECT count(*) AS "Java Object Count"
    FROM all_objects
    WHERE owner = :own AND object_type LIKE 'JAVA %'
"""
