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
        "title": "Clean Up",
        "description": "Drop the policies, table, and test roles.",
        "sql": "DROP POLICY IF EXISTS tenant1_policy ON public.tenant_data;\nDROP POLICY IF EXISTS tenant2_policy ON public.tenant_data;\nDROP TABLE IF EXISTS public.tenant_data;\nDROP ROLE IF EXISTS tenant1_role;\nDROP ROLE IF EXISTS tenant2_role;"
    }
]
