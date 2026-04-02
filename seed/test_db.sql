-- Test database for SQL evaluation
-- Indonesian business data

-- Customers table
CREATE TABLE customers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    city TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO customers (name, email, city) VALUES
('Budi Santoso', 'budi.santoso@example.com', 'Jakarta'),
('Sari Wijaya', 'sari.wijaya@example.com', 'Bandung'),
('Ahmad Rizky', 'ahmad.rizky@example.com', 'Surabaya'),
('Dewi Lestari', 'dewi.lestari@example.com', 'Yogyakarta'),
('Rudi Hartono', 'rudi.hartono@example.com', 'Medan'),
('Maya Sari', 'maya.sari@example.com', 'Semarang'),
('Joko Widodo', 'joko.widodo@example.com', 'Jakarta'),
('Ani Susanti', 'ani.susanti@example.com', 'Bandung'),
('Fajar Nugroho', 'fajar.nugroho@example.com', 'Surabaya'),
('Linda Pratiwi', 'linda.pratiwi@example.com', 'Yogyakarta'),
('Hendra Setiawan', 'hendra.setiawan@example.com', 'Medan'),
('Ratna Dewi', 'ratna.dewi@example.com', 'Semarang'),
('Bambang Sutrisno', 'bambang.sutrisno@example.com', 'Jakarta'),
('Citra Anggraini', 'citra.anggraini@example.com', 'Bandung'),
('Eko Prasetyo', 'eko.prasetyo@example.com', 'Surabaya'),
('Gita Maharani', 'gita.maharani@example.com', 'Yogyakarta'),
('Indra Kusuma', 'indra.kusuma@example.com', 'Medan'),
('Kartika Sari', 'kartika.sari@example.com', 'Semarang'),
('Mochammad Ali', 'mochammad.ali@example.com', 'Jakarta'),
('Nina Hartati', 'nina.hartati@example.com', 'Bandung');

-- Products table
CREATE TABLE products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    price DECIMAL(10,2) NOT NULL,
    category TEXT NOT NULL,
    stock INTEGER NOT NULL
);

INSERT INTO products (name, price, category, stock) VALUES
('Laptop ASUS ROG', 15000000, 'Electronics', 15),
('Smartphone Samsung Galaxy', 8000000, 'Electronics', 30),
('Kemeja Batik', 350000, 'Fashion', 50),
('Sepatu Nike', 1200000, 'Fashion', 25),
('Buku Programming Python', 250000, 'Books', 100),
('Tas Ransel', 450000, 'Fashion', 40),
('Mouse Wireless', 300000, 'Electronics', 60),
('Headphone Sony', 1500000, 'Electronics', 20),
('Jam Tangan Casio', 500000, 'Accessories', 35),
('Dompet Kulit', 200000, 'Accessories', 45),
('Monitor LG 24"', 2500000, 'Electronics', 12),
('Keyboard Mechanical', 800000, 'Electronics', 18),
('Kaos Polo', 150000, 'Fashion', 75),
('Novel Bumi Manusia', 120000, 'Books', 80),
('Power Bank 20000mAh', 400000, 'Electronics', 25),
('Celana Jeans', 300000, 'Fashion', 55),
('Kamera Canon', 5000000, 'Electronics', 8),
('Gelang Perak', 750000, 'Accessories', 15),
('Buku Akuntansi', 180000, 'Books', 60),
('Printer Epson', 2000000, 'Electronics', 10);

-- Orders table
CREATE TABLE orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL,
    total DECIMAL(10,2) NOT NULL,
    status TEXT NOT NULL,
    order_date DATE NOT NULL,
    FOREIGN KEY (customer_id) REFERENCES customers(id)
);

INSERT INTO orders (customer_id, total, status, order_date) VALUES
(1, 15350000, 'completed', '2024-01-15'),
(2, 450000, 'completed', '2024-01-16'),
(3, 8000000, 'processing', '2024-01-17'),
(4, 350000, 'completed', '2024-01-18'),
(5, 1200000, 'completed', '2024-01-19'),
(6, 250000, 'completed', '2024-01-20'),
(7, 450000, 'cancelled', '2024-01-21'),
(8, 300000, 'completed', '2024-01-22'),
(9, 1500000, 'processing', '2024-01-23'),
(10, 500000, 'completed', '2024-01-24'),
(11, 200000, 'completed', '2024-01-25'),
(12, 2500000, 'completed', '2024-01-26'),
(13, 800000, 'processing', '2024-01-27'),
(14, 150000, 'completed', '2024-01-28'),
(15, 120000, 'completed', '2024-01-29'),
(16, 400000, 'completed', '2024-01-30'),
(17, 300000, 'processing', '2024-01-31'),
(18, 5000000, 'completed', '2024-02-01'),
(19, 750000, 'completed', '2024-02-02'),
(20, 180000, 'completed', '2024-02-03');

-- Order items table
CREATE TABLE order_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL,
    unit_price DECIMAL(10,2) NOT NULL,
    FOREIGN KEY (order_id) REFERENCES orders(id),
    FOREIGN KEY (product_id) REFERENCES products(id)
);

INSERT INTO order_items (order_id, product_id, quantity, unit_price) VALUES
(1, 1, 1, 15000000),
(1, 7, 1, 300000),
(1, 8, 1, 50000),
(2, 3, 1, 350000),
(2, 20, 1, 100000),
(3, 2, 1, 8000000),
(4, 3, 1, 350000),
(5, 4, 1, 1200000),
(6, 5, 1, 250000),
(7, 6, 1, 450000),
(8, 7, 1, 300000),
(9, 8, 1, 1500000),
(10, 9, 1, 500000),
(11, 10, 1, 200000),
(12, 11, 1, 2500000),
(13, 12, 1, 800000),
(14, 13, 1, 150000),
(15, 14, 1, 120000),
(16, 15, 1, 400000),
(17, 16, 1, 300000),
(18, 17, 1, 5000000),
(19, 18, 1, 750000),
(20, 19, 1, 180000);

-- Employees table
CREATE TABLE employees (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    department TEXT NOT NULL,
    salary DECIMAL(10,2) NOT NULL,
    hire_date DATE NOT NULL
);

INSERT INTO employees (name, department, salary, hire_date) VALUES
('Agus Supriyanto', 'Sales', 8000000, '2023-01-15'),
('Dian Novita', 'Marketing', 7500000, '2023-02-10'),
('Rizki Ramadhan', 'IT', 12000000, '2023-03-05'),
('Siti Nurhaliza', 'HR', 6500000, '2023-04-20'),
('Bambang Hermawan', 'Finance', 9000000, '2023-05-15'),
('Maya Indah', 'Customer Service', 6000000, '2023-06-10'),
('Hendra Gunawan', 'Operations', 8500000, '2023-07-05'),
('Ratna Wulandari', 'Sales', 8200000, '2023-08-20'),
('Eko Prasetyo', 'IT', 12500000, '2023-09-15'),
('Citra Anggraini', 'Marketing', 7800000, '2023-10-10'),
('Fajar Setiawan', 'Finance', 9500000, '2023-11-05'),
('Gita Maharani', 'HR', 6800000, '2023-12-20'),
('Indra Kusuma', 'Operations', 8700000, '2024-01-15'),
('Kartika Sari', 'Customer Service', 6200000, '2024-02-10'),
('Mochammad Ali', 'Sales', 8300000, '2024-03-05');