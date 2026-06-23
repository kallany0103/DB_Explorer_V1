TABLE_COMMANDS = [
    {
        "title": "Create Table",
        "description": "Create a sample table in the public schema.",
        "sql": "CREATE TABLE public.test_users (\n    id SERIAL PRIMARY KEY,\n    username VARCHAR(50) UNIQUE NOT NULL,\n    email VARCHAR(255) NOT NULL,\n    department_id INT,\n    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP\n);"
    },
    {
        "title": "Create Second Table for Joins",
        "description": "Create another table to test JOIN operations.",
        "sql": "CREATE TABLE public.test_departments (\n    id SERIAL PRIMARY KEY,\n    department_name VARCHAR(100) NOT NULL\n);"
    },
    {
        "title": "Insert Data",
        "description": "Insert sample records into the test tables.",
        "sql": "INSERT INTO public.test_departments (department_name)\nVALUES \n    ('Engineering'),\n    ('Sales');\n\nINSERT INTO public.test_users (username, email, department_id)\nVALUES \n    ('test_user1', 'user1@example.com', 1),\n    ('test_user2', 'user2@example.com', 2),\n    ('test_user3', 'user3@example.com', 1);"
    },
    {
        "title": "Read Data (Select All)",
        "description": "Retrieve all records from the test table.",
        "sql": "SELECT * FROM public.test_users;"
    },
    {
        "title": "Filter Data (WHERE Clause)",
        "description": "Retrieve records based on a specific condition.",
        "sql": "SELECT username, email \nFROM public.test_users \nWHERE department_id = 1 \nAND created_at >= CURRENT_DATE - INTERVAL '1 day';"
    },
    {
        "title": "Sort Data (ORDER BY)",
        "description": "Sort the result set by one or more columns.",
        "sql": "SELECT * FROM public.test_users \nORDER BY created_at DESC, username ASC;"
    },
    {
        "title": "Update Data",
        "description": "Update specific records matching a condition.",
        "sql": "UPDATE public.test_users \nSET email = 'new_email@example.com' \nWHERE username = 'test_user1';"
    },
    {
        "title": "Delete Data",
        "description": "Delete a specific record from the test table.",
        "sql": "DELETE FROM public.test_users \nWHERE username = 'test_user2';"
    },
    {
        "title": "Drop Tables",
        "description": "Drop the sample tables from the public schema.",
        "sql": "DROP TABLE public.test_users;\nDROP TABLE public.test_departments;"
    }
]
