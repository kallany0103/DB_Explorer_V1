FUNCTION_COMMANDS = [
    {
        "title": "Setup Dependent Tables",
        "description": "Create and populate the underlying tables required for these functions.",
        "sql": "CREATE TABLE IF NOT EXISTS public.test_departments (\n    id SERIAL PRIMARY KEY,\n    department_name VARCHAR(100) NOT NULL\n);\n\nCREATE TABLE IF NOT EXISTS public.test_users (\n    id SERIAL PRIMARY KEY,\n    username VARCHAR(50) UNIQUE NOT NULL,\n    email VARCHAR(255) NOT NULL,\n    department_id INT,\n    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP\n);\n\nINSERT INTO public.test_departments (department_name)\nVALUES ('Engineering'), ('Sales');\n\nINSERT INTO public.test_users (username, email, department_id)\nVALUES \n    ('test_user1', 'user1@example.com', 1),\n    ('test_user2', 'user2@example.com', 2),\n    ('test_user3', 'user3@example.com', 1);"
    },
    {
        "title": "Create Simple Function",
        "description": "Create a function that takes arguments and returns a value.",
        "sql": "CREATE OR REPLACE FUNCTION public.calculate_bonus(salary NUMERIC, bonus_percentage NUMERIC)\nRETURNS NUMERIC\nLANGUAGE plpgsql\nAS $$\nBEGIN\n    RETURN salary * (bonus_percentage / 100.0);\nEND;\n$$;"
    },
    {
        "title": "Create Function Returning Table",
        "description": "Create a function that returns a set of rows (table function).",
        "sql": "CREATE OR REPLACE FUNCTION public.get_users_by_department(dept_id INT)\nRETURNS TABLE(user_id INT, user_email VARCHAR)\nLANGUAGE plpgsql\nAS $$\nBEGIN\n    RETURN QUERY \n    SELECT id, email \n    FROM public.test_users \n    WHERE department_id = dept_id;\nEND;\n$$;"
    },
    {
        "title": "Execute Scalar Function",
        "description": "Call a function that returns a single scalar value.",
        "sql": "SELECT public.calculate_bonus(50000, 10) AS bonus_amount;"
    },
    {
        "title": "Execute Table Function",
        "description": "Select from a function that returns a table.",
        "sql": "SELECT * FROM public.get_users_by_department(1);"
    },
    {
        "title": "Drop Functions",
        "description": "Drop the functions from the public schema.",
        "sql": "DROP FUNCTION public.calculate_bonus(NUMERIC, NUMERIC);\nDROP FUNCTION public.get_users_by_department(INT);"
    }
]
