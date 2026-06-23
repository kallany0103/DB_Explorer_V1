VIEW_COMMANDS = [
    {
        "title": "Setup Dependent Tables",
        "description": "Create and populate the underlying tables required for the view tests.",
        "sql": "CREATE TABLE IF NOT EXISTS public.test_departments (\n    id SERIAL PRIMARY KEY,\n    department_name VARCHAR(100) NOT NULL\n);\n\nCREATE TABLE IF NOT EXISTS public.test_users (\n    id SERIAL PRIMARY KEY,\n    username VARCHAR(50) UNIQUE NOT NULL,\n    email VARCHAR(255) NOT NULL,\n    department_id INT,\n    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP\n);\n\nINSERT INTO public.test_departments (department_name)\nVALUES ('Engineering'), ('Sales');\n\nINSERT INTO public.test_users (username, email, department_id)\nVALUES \n    ('test_user1', 'user1@example.com', 1),\n    ('test_user2', 'user2@example.com', 2),\n    ('test_user3', 'user3@example.com', 1);"
    },
    {
        "title": "Create Simple View",
        "description": "Create a view based on a single table.",
        "sql": "CREATE OR REPLACE VIEW public.vw_active_users AS\nSELECT id, username, email \nFROM public.test_users\nWHERE created_at >= CURRENT_DATE - INTERVAL '30 days';"
    },
    {
        "title": "Create View with JOIN",
        "description": "Create a more complex view that joins multiple tables.",
        "sql": "CREATE OR REPLACE VIEW public.vw_user_departments AS\nSELECT u.username, u.email, d.department_name\nFROM public.test_users u\nINNER JOIN public.test_departments d ON u.department_id = d.id;"
    },
    {
        "title": "Create View with Aggregation",
        "description": "Create a view summarizing data.",
        "sql": "CREATE OR REPLACE VIEW public.vw_department_stats AS\nSELECT d.department_name, COUNT(u.id) as total_users\nFROM public.test_departments d\nLEFT JOIN public.test_users u ON d.id = u.department_id\nGROUP BY d.department_name;"
    },
    {
        "title": "Read from View",
        "description": "Select all data from a view.",
        "sql": "SELECT * FROM public.vw_user_departments;"
    },
    {
        "title": "Filter View Data (WHERE)",
        "description": "Select data from a view with a condition.",
        "sql": "SELECT * FROM public.vw_user_departments\nWHERE department_name = 'Engineering';"
    },
    {
        "title": "Drop Views",
        "description": "Drop the views from the public schema.",
        "sql": "DROP VIEW public.vw_active_users;\nDROP VIEW public.vw_user_departments;\nDROP VIEW public.vw_department_stats;"
    }
]
