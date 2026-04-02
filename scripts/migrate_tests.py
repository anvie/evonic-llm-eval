#!/usr/bin/env python3
"""
Migration script to convert hardcoded tests to JSON format.

This script reads the existing test classes from the tests/ module
and creates corresponding JSON files in test_definitions/.
"""

import json
import os
from pathlib import Path
from datetime import datetime

# Base directory for test definitions
BASE_DIR = Path(__file__).parent.parent / "test_definitions"

# Domain configurations
DOMAIN_CONFIGS = {
    "conversation": {
        "name": "Conversation",
        "description": "Indonesian conversational Q&A tests - tests natural language understanding and response generation",
        "icon": "chat",
        "color": "#3B82F6",
        "evaluator_id": "keyword"
    },
    "math": {
        "name": "Math",
        "description": "Mathematical calculation tests - expects clean numerical answers",
        "icon": "calculator",
        "color": "#10B981",
        "evaluator_id": "two_pass"
    },
    "sql": {
        "name": "SQL",
        "description": "SQL query generation tests - tests database query generation capabilities",
        "icon": "database",
        "color": "#8B5CF6",
        "evaluator_id": "sql_executor"
    },
    "tool_calling": {
        "name": "Tool Calling",
        "description": "Function/tool calling tests - tests ability to use tools and APIs correctly",
        "icon": "wrench",
        "color": "#F59E0B",
        "evaluator_id": "tool_call"
    },
    "reasoning": {
        "name": "Reasoning",
        "description": "Logical reasoning tests - tests deductive and inductive reasoning capabilities",
        "icon": "brain",
        "color": "#EF4444",
        "evaluator_id": "two_pass"
    }
}

# Evaluator configurations
EVALUATOR_CONFIGS = [
    {
        "id": "two_pass",
        "name": "Two-Pass Evaluator",
        "type": "predefined",
        "description": "Uses two-pass evaluation - first extracts clean answer, then scores",
        "uses_pass2": True,
        "config": {"tolerance": 0.01}
    },
    {
        "id": "keyword",
        "name": "Keyword Evaluator",
        "type": "predefined",
        "description": "Evaluates based on keyword presence and relevance",
        "uses_pass2": False,
        "config": {
            "relevance_weight": 0.3,
            "correctness_weight": 0.4,
            "fluency_weight": 0.3
        }
    },
    {
        "id": "sql_executor",
        "name": "SQL Executor Evaluator",
        "type": "predefined",
        "description": "Executes SQL queries and compares results",
        "uses_pass2": False,
        "config": {
            "db_type": "sqlite",
            "compare_results": True
        }
    },
    {
        "id": "tool_call",
        "name": "Tool Call Evaluator",
        "type": "predefined",
        "description": "Evaluates tool/function calling accuracy and correctness",
        "uses_pass2": False,
        "config": {
            "validate_args": True,
            "check_execution": True
        }
    }
]

# Test prompts extracted from test classes
CONVERSATION_TESTS = {
    1: [
        {
            "id": "conv_intro_1",
            "name": "Basic Introduction",
            "description": "Test basic self-introduction capability",
            "prompt": "Halo! Bisa tolong perkenalkan diri Anda?",
            "expected": {
                "keywords": ["ai", "assistant", "membantu", "help", "asisten", "saya", "i am", "qwen", "alibaba", "llm", "model"],
                "type": "introduction"
            }
        }
    ],
    2: [
        {
            "id": "conv_capital_2",
            "name": "Capital City Knowledge",
            "description": "Test knowledge about Indonesian capital city",
            "prompt": "Apa ibu kota Indonesia dan mengapa kota tersebut penting?",
            "expected": {
                "keywords": ["jakarta", "ibu kota", "indonesia", "pusat", "pemerintahan", "nusantara", "ikn"],
                "type": "factual"
            }
        }
    ],
    3: [
        {
            "id": "conv_startup_3",
            "name": "Startup Definition",
            "description": "Test ability to explain startup concept",
            "prompt": "Jelaskan apa yang dimaksud dengan 'startup' dalam konteks bisnis teknologi.",
            "expected": {
                "keywords": ["startup", "teknologi", "bisnis", "inovasi", "perusahaan", "skala", "pertumbuhan"],
                "type": "explanatory"
            }
        }
    ],
    4: [
        {
            "id": "conv_ecommerce_4",
            "name": "E-commerce Advice",
            "description": "Test ability to provide business advice for e-commerce",
            "prompt": "Saya sedang mempertimbangkan untuk memulai bisnis e-commerce di Indonesia. Bisa berikan saran tentang platform yang cocok dan strategi pemasaran yang efektif?",
            "expected": {
                "keywords": ["e-commerce", "tokopedia", "shopee", "pemasaran", "digital", "marketplace", "strategi"],
                "type": "advisory"
            }
        }
    ],
    5: [
        {
            "id": "conv_digital_transform_5",
            "name": "Digital Transformation Strategy",
            "description": "Test ability to provide complex strategic advice",
            "prompt": "Sebagai konsultan teknologi, bagaimana Anda akan menyarankan perusahaan tradisional untuk beradaptasi dengan transformasi digital? Berikan contoh konkret untuk sektor retail.",
            "expected": {
                "keywords": ["transformasi digital", "retail", "teknologi", "adaptasi", "contoh", "online", "omnichannel"],
                "type": "strategic"
            }
        }
    ]
}

MATH_TESTS = {
    1: [
        {
            "id": "math_add_1",
            "name": "Simple Addition",
            "description": "Test basic addition calculation",
            "prompt": "Berapa hasil dari 7 + 3?",
            "expected": {"answer": 10.0, "type": "numeric"}
        },
        {
            "id": "math_subtract_1",
            "name": "Simple Subtraction",
            "description": "Test basic subtraction calculation",
            "prompt": "Berapa hasil dari 15 - 8?",
            "expected": {"answer": 7.0, "type": "numeric"}
        }
    ],
    2: [
        {
            "id": "math_percentage_2",
            "name": "Percentage Calculation",
            "description": "Test percentage calculation",
            "prompt": "Hitung 15% dari 240",
            "expected": {"answer": 36.0, "type": "numeric"}
        }
    ],
    3: [
        {
            "id": "math_deposito_3",
            "name": "Compound Interest",
            "description": "Test compound interest calculation",
            "prompt": "Jika deposito Rp 10.000.000 dengan bunga 6% per tahun, berapa total setelah 2 tahun?",
            "expected": {"answer": 11236000.0, "type": "numeric"}
        }
    ],
    4: [
        {
            "id": "math_triangle_4",
            "name": "Triangle Area",
            "description": "Test geometry calculation - triangle area",
            "prompt": "Hitung luas segitiga dengan alas 8 cm dan tinggi 6 cm",
            "expected": {"answer": 24.0, "type": "numeric"}
        }
    ],
    5: [
        {
            "id": "math_double_discount_5",
            "name": "Double Discount",
            "description": "Test complex discount calculation",
            "prompt": "Sebuah toko memberikan diskon 20% kemudian tambahan diskon 10%. Jika harga awal Rp 500.000, berapa harga akhir?",
            "expected": {"answer": 360000.0, "type": "numeric"}
        }
    ]
}

SQL_TESTS = {
    1: [
        {
            "id": "sql_select_1",
            "name": "Simple SELECT",
            "description": "Test basic SELECT query",
            "prompt": "Buat query SQL untuk menampilkan semua data dari tabel customers",
            "expected": {"query_type": "SELECT", "table": "customers"}
        }
    ],
    2: [
        {
            "id": "sql_filter_2",
            "name": "Filter with WHERE",
            "description": "Test WHERE clause usage",
            "prompt": "Buat query SQL untuk menampilkan customers yang tinggal di Jakarta",
            "expected": {"query_type": "SELECT", "clause": "WHERE"}
        }
    ],
    3: [
        {
            "id": "sql_join_3",
            "name": "JOIN Query",
            "description": "Test JOIN operation",
            "prompt": "Buat query SQL untuk menampilkan nama customer dan pesanan mereka",
            "expected": {"query_type": "SELECT", "clause": "JOIN"}
        }
    ],
    4: [
        {
            "id": "sql_aggregate_4",
            "name": "Aggregation",
            "description": "Test aggregate functions",
            "prompt": "Buat query SQL untuk menghitung total penjualan per bulan",
            "expected": {"query_type": "SELECT", "functions": ["SUM", "GROUP BY"]}
        }
    ],
    5: [
        {
            "id": "sql_subquery_5",
            "name": "Subquery",
            "description": "Test subquery usage",
            "prompt": "Buat query SQL untuk menampilkan customers yang memiliki total pesanan di atas rata-rata",
            "expected": {"query_type": "SELECT", "clause": "SUBQUERY"}
        }
    ]
}

TOOL_CALLING_TESTS = {
    1: [
        {
            "id": "tool_simple_1",
            "name": "Simple Tool Call",
            "description": "Test basic tool calling",
            "prompt": "Berapa cuaca di Jakarta hari ini?",
            "expected": {"tool": "get_weather", "args": ["Jakarta"]}
        }
    ],
    2: [
        {
            "id": "tool_args_2",
            "name": "Tool with Arguments",
            "description": "Test tool calling with arguments",
            "prompt": "Cari restoran Italia di Jakarta dengan rating minimal 4 bintang",
            "expected": {"tool": "search_restaurants", "args": {"cuisine": "Italian", "location": "Jakarta", "min_rating": 4}}
        }
    ],
    3: [
        {
            "id": "tool_multi_3",
            "name": "Multiple Tools",
            "description": "Test calling multiple tools",
            "prompt": "Cari hotel di Bali dan tampilkan cuaca di sana",
            "expected": {"tools": ["search_hotels", "get_weather"]}
        }
    ],
    4: [
        {
            "id": "tool_chained_4",
            "name": "Chained Tool Calls",
            "description": "Test chained tool calls",
            "prompt": "Cari pesanan terbaru customer ID 123 dan kirim notifikasi ke email mereka",
            "expected": {"chain": ["get_order", "send_notification"]}
        }
    ],
    5: [
        {
            "id": "tool_complex_5",
            "name": "Complex Tool Usage",
            "description": "Test complex tool orchestration",
            "prompt": "Rencanakan perjalanan ke Yogyakarta untuk 3 orang, termasuk penerbangan, hotel, dan aktivitas",
            "expected": {"multiple_chains": True}
        }
    ]
}

REASONING_TESTS = {
    1: [
        {
            "id": "reason_syllogism_1",
            "name": "Simple Syllogism",
            "description": "Test basic logical reasoning",
            "prompt": "Semua kucing adalah mamalia. Tom adalah kucing. Apakah Tom mamalia?",
            "expected": {"answer": "Ya", "reasoning": "syllogism"}
        }
    ],
    2: [
        {
            "id": "reason_conditional_2",
            "name": "Conditional Reasoning",
            "description": "Test conditional logic",
            "prompt": "Jika hari ini hujan, maka tanaman akan disiram. Hari ini hujan. Apakah tanaman disiram?",
            "expected": {"answer": "Ya", "reasoning": "modus_ponens"}
        }
    ],
    3: [
        {
            "id": "reason_analogy_3",
            "name": "Analogical Reasoning",
            "description": "Test analogical reasoning",
            "prompt": "Panas : Dingin seperti Terang : ...",
            "expected": {"answer": "Gelap", "reasoning": "analogy"}
        }
    ],
    4: [
        {
            "id": "reason_causal_4",
            "name": "Causal Reasoning",
            "description": "Test causal reasoning",
            "prompt": "Setelah meminum obat, pasien merasa lebih baik. Apakah obat menyebabkan perbaikan?",
            "expected": {"reasoning": "causal", "consider_alternatives": True}
        }
    ],
    5: [
        {
            "id": "reason_complex_5",
            "name": "Complex Reasoning",
            "description": "Test complex multi-step reasoning",
            "prompt": "Dalam sebuah ruangan ada 5 orang. Setiap orang berjabat tangan dengan setiap orang lain tepat sekali. Berapa total jabat tangan?",
            "expected": {"answer": 10, "reasoning": "combinatorics"}
        }
    ]
}

ALL_TESTS = {
    "conversation": CONVERSATION_TESTS,
    "math": MATH_TESTS,
    "sql": SQL_TESTS,
    "tool_calling": TOOL_CALLING_TESTS,
    "reasoning": REASONING_TESTS
}


def create_directory_structure():
    """Create the directory structure for test definitions"""
    print("Creating directory structure...")
    
    # Create base directories
    (BASE_DIR / "evaluators").mkdir(parents=True, exist_ok=True)
    
    for domain_id in DOMAIN_CONFIGS:
        domain_dir = BASE_DIR / domain_id
        domain_dir.mkdir(parents=True, exist_ok=True)
        
        # Create level directories
        for level in range(1, 6):
            (domain_dir / f"level_{level}").mkdir(exist_ok=True)
    
    print("  Directory structure created.")


def create_evaluator_files():
    """Create evaluator JSON files"""
    print("Creating evaluator files...")
    
    evaluators_dir = BASE_DIR / "evaluators"
    
    for evaluator in EVALUATOR_CONFIGS:
        file_path = evaluators_dir / f"{evaluator['id']}.json"
        
        evaluator['created_at'] = datetime.now().isoformat()
        evaluator['updated_at'] = datetime.now().isoformat()
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(evaluator, f, indent=2, ensure_ascii=False)
        
        print(f"  Created: {file_path}")


def create_domain_files():
    """Create domain.json files"""
    print("Creating domain files...")
    
    for domain_id, config in DOMAIN_CONFIGS.items():
        domain_dir = BASE_DIR / domain_id
        file_path = domain_dir / "domain.json"
        
        domain_data = {
            "id": domain_id,
            "name": config["name"],
            "description": config["description"],
            "icon": config["icon"],
            "color": config["color"],
            "evaluator_id": config["evaluator_id"],
            "enabled": True,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(domain_data, f, indent=2, ensure_ascii=False)
        
        print(f"  Created: {file_path}")


def create_test_files():
    """Create test JSON files"""
    print("Creating test files...")
    
    for domain_id, levels in ALL_TESTS.items():
        for level, tests in levels.items():
            level_dir = BASE_DIR / domain_id / f"level_{level}"
            
            for test in tests:
                file_name = test["id"] + ".json"
                file_path = level_dir / file_name
                
                test_data = {
                    "id": test["id"],
                    "name": test["name"],
                    "description": test["description"],
                    "prompt": test["prompt"],
                    "expected": test["expected"],
                    "evaluator_id": DOMAIN_CONFIGS[domain_id]["evaluator_id"],
                    "timeout_ms": 30000,
                    "weight": 1.0,
                    "enabled": True,
                    "created_at": datetime.now().isoformat(),
                    "updated_at": datetime.now().isoformat()
                }
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(test_data, f, indent=2, ensure_ascii=False)
                
                print(f"  Created: {file_path}")


def verify_migration():
    """Verify the migration by counting files"""
    print("\nVerifying migration...")
    
    # Count evaluators
    evaluators = list((BASE_DIR / "evaluators").glob("*.json"))
    print(f"  Evaluators: {len(evaluators)}")
    
    # Count domains
    domains = [d for d in BASE_DIR.iterdir() if d.is_dir() and d.name != "evaluators"]
    print(f"  Domains: {len(domains)}")
    
    # Count tests
    total_tests = 0
    for domain in domains:
        for level in range(1, 6):
            level_dir = domain / f"level_{level}"
            if level_dir.exists():
                tests = list(level_dir.glob("*.json"))
                total_tests += len(tests)
    
    print(f"  Total tests: {total_tests}")
    
    return len(evaluators), len(domains), total_tests


def main():
    """Run the migration"""
    print("=" * 60)
    print("Migrating hardcoded tests to JSON format")
    print("=" * 60)
    
    create_directory_structure()
    create_evaluator_files()
    create_domain_files()
    create_test_files()
    
    evaluators, domains, tests = verify_migration()
    
    print("\n" + "=" * 60)
    print("Migration completed successfully!")
    print(f"  Created {evaluators} evaluators")
    print(f"  Created {domains} domains")
    print(f"  Created {tests} tests")
    print("=" * 60)


if __name__ == "__main__":
    main()