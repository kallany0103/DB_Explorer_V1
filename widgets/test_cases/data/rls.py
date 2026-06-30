RLS_COMMANDS = [
    {
        "title": "Setup RLS Tables & Roles",
        "description": "Create a table, test roles, and insert sample data.",
        "sql": "DROP TABLE IF EXISTS public.tenant_data;\n\nCREATE TABLE public.tenant_data (\n    id SERIAL PRIMARY KEY,\n    tenant_id INT NOT NULL,\n    secret_data VARCHAR(255) NOT NULL\n);\n\nINSERT INTO public.tenant_data (tenant_id, secret_data)\nVALUES \n    (1, 'Tenant 1 Secret A'), \n    (1, 'Tenant 1 Secret B'), \n    (2, 'Tenant 2 Secret C');\n\n-- Create test roles\nDO $$\nBEGIN\n    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'tenant1_role') THEN\n        CREATE ROLE tenant1_role;\n    END IF;\n    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'tenant2_role') THEN\n        CREATE ROLE tenant2_role;\n    END IF;\nEND\n$$;\n\n-- Allow the current user to assume these roles\nGRANT tenant1_role TO CURRENT_USER;\nGRANT tenant2_role TO CURRENT_USER;\n\n-- Grant access to the table so the roles can query it at all\nGRANT SELECT ON public.tenant_data TO tenant1_role;\nGRANT SELECT ON public.tenant_data TO tenant2_role;"
    },
    {
        "title": "Enable Row-Level Security",
        "description": "Enable RLS on the table. (By default, this restricts all access unless a policy grants it).",
        "sql": "ALTER TABLE public.tenant_data ENABLE ROW LEVEL SECURITY;"
    },
    {
        "title": "Create Policies",
        "description": "Create policies restricting rows based on the role querying the table.",
        "sql": "-- Policy for Tenant 1\nCREATE POLICY tenant1_policy ON public.tenant_data\n    FOR SELECT\n    TO tenant1_role\n    USING (tenant_id = 1);\n\n-- Policy for Tenant 2\nCREATE POLICY tenant2_policy ON public.tenant_data\n    FOR SELECT\n    TO tenant2_role\n    USING (tenant_id = 2);"
    },
    {
        "title": "Test Access (Tenant 1)",
        "description": "Switch to tenant1_role and query the data. You should only see tenant_id = 1.",
        "sql": "SET ROLE tenant1_role;\nSELECT * FROM public.tenant_data;\nRESET ROLE;"
    },
    {
        "title": "Test Access (Tenant 2)",
        "description": "Switch to tenant2_role and query the data. You should only see tenant_id = 2.",
        "sql": "SET ROLE tenant2_role;\nSELECT * FROM public.tenant_data;\nRESET ROLE;"
    },
    {
        "title": "Disable Row-Level Security",
        "description": "Disable RLS on the table. (Policies remain but are ignored).",
        "sql": "ALTER TABLE public.tenant_data DISABLE ROW LEVEL SECURITY;"
    },
    {
        "title": "Advanced RLS: Setup App-Level Users Table",
        "description": "Create a more realistic scenario using a single DB role and application-level session variables (like Supabase).",
        "sql": "CREATE TABLE IF NOT EXISTS public.app_documents (\n    id SERIAL PRIMARY KEY,\n    owner_id INT NOT NULL,\n    document_text TEXT\n);\n\nINSERT INTO public.app_documents (owner_id, document_text)\nVALUES \n    (101, 'User 101 Document A'),\n    (101, 'User 101 Document B'),\n    (102, 'User 102 Document C');\n\nALTER TABLE public.app_documents ENABLE ROW LEVEL SECURITY;\n\n-- Create a generic web role\nDO $$\nBEGIN\n    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'web_anon') THEN\n        CREATE ROLE web_anon;\n    END IF;\nEND\n$$;\n\nGRANT web_anon TO CURRENT_USER;\nGRANT SELECT, INSERT, UPDATE, DELETE ON public.app_documents TO web_anon;"
    },
    {
        "title": "Advanced RLS: Session Variable Policy (SELECT)",
        "description": "Create a policy that reads a custom session variable (app.current_user_id) instead of relying on PostgreSQL roles.",
        "sql": "CREATE POLICY session_select_policy ON public.app_documents\n    FOR SELECT\n    TO web_anon\n    USING (owner_id = current_setting('app.current_user_id', true)::INT);"
    },
    {
        "title": "Advanced RLS: Test Session Policy",
        "description": "Pretend to be user 101 connecting through the web application. You should only see owner_id = 101.",
        "sql": "SET ROLE web_anon;\n-- The application sets this variable for the session:\nSET app.current_user_id = '101';\n\nSELECT * FROM public.app_documents;\n\nRESET ROLE;"
    },
    {
        "title": "Advanced RLS: WITH CHECK Policy (INSERT / UPDATE)",
        "description": "Ensure users can only insert or update documents if they set themselves as the owner.",
        "sql": "CREATE POLICY session_insert_policy ON public.app_documents\n    FOR INSERT\n    TO web_anon\n    WITH CHECK (owner_id = current_setting('app.current_user_id', true)::INT);\n\nCREATE POLICY session_update_policy ON public.app_documents\n    FOR UPDATE\n    TO web_anon\n    USING (owner_id = current_setting('app.current_user_id', true)::INT)\n    WITH CHECK (owner_id = current_setting('app.current_user_id', true)::INT);"
    },
    {
        "title": "Advanced RLS: Test WITH CHECK",
        "description": "Test that the database blocks User 101 from inserting a document belonging to User 102.",
        "sql": "SET ROLE web_anon;\nSET app.current_user_id = '101';\n\n-- This will SUCCEED:\nINSERT INTO public.app_documents (owner_id, document_text) \nVALUES (101, 'Legal doc');\n\n-- This will FAIL with an RLS error:\nINSERT INTO public.app_documents (owner_id, document_text) \nVALUES (102, 'Illegal doc');\n\nRESET ROLE;"
    },
    {
        "title": "Advanced RLS: DELETE Policy",
        "description": "Ensure users can only delete their own documents.",
        "sql": "CREATE POLICY session_delete_policy ON public.app_documents\n    FOR DELETE\n    TO web_anon\n    USING (owner_id = current_setting('app.current_user_id', true)::INT);"
    },
    {
        "title": "Advanced RLS: Test DELETE Policy",
        "description": "Test that the database prevents User 101 from deleting a document belonging to User 102.",
        "sql": "SET ROLE web_anon;\nSET app.current_user_id = '101';\n\n-- This will DELETE 0 rows, because User 101 cannot access User 102's data:\nDELETE FROM public.app_documents WHERE owner_id = 102;\n\n-- This will SUCCEED and delete User 101's documents:\nDELETE FROM public.app_documents WHERE owner_id = 101;\n\nRESET ROLE;"
    },
    {
        "title": "Clean Up",
        "description": "Drop the policies, tables, and test roles.",
        "sql": "DROP POLICY IF EXISTS tenant1_policy ON public.tenant_data;\nDROP POLICY IF EXISTS tenant2_policy ON public.tenant_data;\nDROP TABLE IF EXISTS public.tenant_data;\nDROP ROLE IF EXISTS tenant1_role;\nDROP ROLE IF EXISTS tenant2_role;\n\nDROP POLICY IF EXISTS session_select_policy ON public.app_documents;\nDROP POLICY IF EXISTS session_insert_policy ON public.app_documents;\nDROP POLICY IF EXISTS session_update_policy ON public.app_documents;\nDROP POLICY IF EXISTS session_delete_policy ON public.app_documents;\nDROP TABLE IF EXISTS public.app_documents;\nDROP ROLE IF EXISTS web_anon;"
    }
]
