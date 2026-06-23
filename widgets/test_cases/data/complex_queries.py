COMPLEX_QUERIES = [
    {
        "title": "Setup Dependent Tables",
        "description": "Create and populate the underlying tables required for these queries.",
        "sql": "CREATE TABLE IF NOT EXISTS public.test_departments (\n    id SERIAL PRIMARY KEY,\n    department_name VARCHAR(100) NOT NULL\n);\n\nCREATE TABLE IF NOT EXISTS public.test_users (\n    id SERIAL PRIMARY KEY,\n    username VARCHAR(50) UNIQUE NOT NULL,\n    email VARCHAR(255) NOT NULL,\n    department_id INT,\n    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP\n);\n\nINSERT INTO public.test_departments (department_name)\nVALUES ('Engineering'), ('Sales');\n\nINSERT INTO public.test_users (username, email, department_id)\nVALUES \n    ('test_user1', 'user1@example.com', 1),\n    ('test_user2', 'user2@example.com', 2),\n    ('test_user3', 'user3@example.com', 1);"
    },
    {
        "title": "Join Data (INNER JOIN)",
        "description": "Combine rows from two tables based on a related column.",
        "sql": "SELECT u.username, u.email, d.department_name \nFROM public.test_users u \nINNER JOIN public.test_departments d \nON u.department_id = d.id;"
    },
    {
        "title": "Join Data (LEFT JOIN)",
        "description": "Retrieve all rows from the left table, and matching rows from the right table.",
        "sql": "SELECT d.department_name, u.username\nFROM public.test_departments d\nLEFT JOIN public.test_users u ON d.id = u.department_id;"
    },
    {
        "title": "Aggregate Data (GROUP BY)",
        "description": "Group records and apply an aggregate function like COUNT.",
        "sql": "SELECT d.department_name, COUNT(u.id) as user_count\nFROM public.test_departments d\nLEFT JOIN public.test_users u ON d.id = u.department_id\nGROUP BY d.department_name;"
    },
    {
        "title": "Filter Aggregated Data (HAVING)",
        "description": "Use HAVING to filter groups after aggregation.",
        "sql": "SELECT d.department_name, COUNT(u.id) as user_count\nFROM public.test_departments d\nLEFT JOIN public.test_users u ON d.id = u.department_id\nGROUP BY d.department_name\nHAVING COUNT(u.id) > 1;"
    },
    {
        "title": "Subquery (IN)",
        "description": "Use a subquery to filter records based on results from another query.",
        "sql": "SELECT username, email \nFROM public.test_users \nWHERE department_id IN (\n    SELECT id FROM public.test_departments WHERE department_name = 'Engineering'\n);"
    },
    {
        "title": "Common Table Expression (WITH)",
        "description": "Use a CTE to simplify complex queries and make them readable.",
        "sql": "WITH DeptStats AS (\n    SELECT department_id, COUNT(*) as emp_count\n    FROM public.test_users\n    GROUP BY department_id\n)\nSELECT d.department_name, s.emp_count\nFROM public.test_departments d\nINNER JOIN DeptStats s ON d.id = s.department_id;"
    }
]
