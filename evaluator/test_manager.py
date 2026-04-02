"""
Test Manager - CRUD operations for test definitions.

Manages both file system (JSON files) and database cache.
"""

import json
import os
import re
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime

from .test_loader import TestLoader, TestDefinition, DomainDefinition, EvaluatorDefinition
from models.db import db


class TestManager:
    """Manage test definitions with file and database sync"""
    
    def __init__(self, 
                 tests_dir: str = "test_definitions",
                 custom_dir: str = "custom_tests",
                 evaluators_dir: str = "test_definitions/evaluators",
                 custom_evaluators_dir: str = "custom_evaluators"):
        self.loader = TestLoader(tests_dir, custom_dir, evaluators_dir, custom_evaluators_dir)
        # Use absolute paths based on project root
        base_dir = Path(__file__).parent.parent
        self.tests_dir = base_dir / tests_dir
        self.custom_dir = base_dir / custom_dir
        self.evaluators_dir = base_dir / evaluators_dir
        self.custom_evaluators_dir = base_dir / custom_evaluators_dir
        
        # Ensure directories exist
        self.tests_dir.mkdir(parents=True, exist_ok=True)
        self.custom_dir.mkdir(parents=True, exist_ok=True)
        self.evaluators_dir.mkdir(parents=True, exist_ok=True)
        self.custom_evaluators_dir.mkdir(parents=True, exist_ok=True)
    
    # ==================== Domain Operations ====================
    
    def list_domains(self, include_disabled: bool = False) -> List[Dict[str, Any]]:
        """List all domains"""
        domains = self.loader.scan_domains()
        result = []
        for domain in domains:
            d = domain.to_dict()
            # Add test counts
            total_tests = 0
            for level in range(1, 6):
                tests = self.loader.load_tests_by_level(domain.id, level)
                total_tests += len(tests)
            d['total_tests'] = total_tests
            d['levels'] = {}
            for level in range(1, 6):
                tests = self.loader.load_tests_by_level(domain.id, level)
                d['levels'][level] = len(tests)
            
            if include_disabled or domain.enabled:
                result.append(d)
        return result
    
    def get_domain(self, domain_id: str) -> Optional[Dict[str, Any]]:
        """Get a single domain with test counts"""
        domain = self.loader.load_domain(domain_id)
        if not domain:
            return None
        
        result = domain.to_dict()
        total_tests = 0
        result['levels'] = {}
        for level in range(1, 6):
            tests = self.loader.load_tests_by_level(domain_id, level)
            count = len(tests)
            total_tests += count
            result['levels'][level] = count
        result['total_tests'] = total_tests
        
        return result
    
    def create_domain(self, data: Dict[str, Any], is_custom: bool = False) -> Dict[str, Any]:
        """Create a new domain
        
        Args:
            data: Domain data dictionary
            is_custom: If True, create in custom_tests directory
            
        Returns:
            Created domain data
        """
        # Generate ID from name if not provided
        if 'id' not in data or not data['id']:
            data['id'] = self._generate_id(data.get('name', 'new_domain'))
        
        domain_id = data['id']
        
        # Validate
        domain = DomainDefinition.from_dict(data, "")
        errors = self.loader.validate_domain(domain)
        if errors:
            raise ValueError(f"Validation errors: {', '.join(errors)}")
        
        # Check if domain already exists
        if self.loader.load_domain(domain_id):
            raise ValueError(f"Domain '{domain_id}' already exists")
        
        # Determine base directory
        base_dir = self.custom_dir if is_custom else self.tests_dir
        domain_path = base_dir / domain_id
        
        # Create domain directory
        domain_path.mkdir(parents=True, exist_ok=True)
        
        # Create level directories
        for level in range(1, 6):
            (domain_path / f"level_{level}").mkdir(exist_ok=True)
        
        # Add timestamps
        now = datetime.now().isoformat()
        data['created_at'] = now
        data['updated_at'] = now
        
        # Write domain.json
        domain_file = domain_path / "domain.json"
        with open(domain_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        # Sync to database
        db_data = data.copy()
        db_data['path'] = str(domain_path)
        db.upsert_domain(db_data)
        
        # Clear cache
        self.loader.clear_cache()
        
        return self.get_domain(domain_id)
    
    def update_domain(self, domain_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing domain"""
        domain = self.loader.load_domain(domain_id)
        if not domain:
            raise ValueError(f"Domain '{domain_id}' not found")
        
        # Update fields
        domain_path = Path(domain.path)
        domain_file = domain_path / "domain.json"
        
        # Load existing data
        with open(domain_file, 'r', encoding='utf-8') as f:
            existing = json.load(f)
        
        # Merge updates
        existing.update(data)
        existing['updated_at'] = datetime.now().isoformat()
        
        # Write back
        with open(domain_file, 'w', encoding='utf-8') as f:
            json.dump(existing, f, indent=2, ensure_ascii=False)
        
        # Sync to database
        db_data = existing.copy()
        db_data['path'] = str(domain_path)
        db.upsert_domain(db_data)
        
        # Clear cache
        self.loader.clear_cache()
        
        return self.get_domain(domain_id)
    
    def delete_domain(self, domain_id: str) -> bool:
        """Delete a domain and all its tests"""
        domain = self.loader.load_domain(domain_id)
        if not domain:
            return False
        
        domain_path = Path(domain.path)
        
        # Delete from filesystem
        if domain_path.exists():
            shutil.rmtree(domain_path)
        
        # Delete from database
        db.delete_domain(domain_id)
        
        # Clear cache
        self.loader.clear_cache()
        
        return True
    
    # ==================== Test Operations ====================
    
    def list_tests(self, domain_id: str = None, level: int = None) -> List[Dict[str, Any]]:
        """List tests, optionally filtered by domain and level"""
        if domain_id and level:
            tests = self.loader.load_tests_by_level(domain_id, level)
        elif domain_id:
            tests = self.loader.load_all_tests(domain_id)
        else:
            tests = self.loader.load_all_tests()
        
        return [t.to_dict() for t in tests]
    
    def get_test(self, test_id: str) -> Optional[Dict[str, Any]]:
        """Get a single test by ID"""
        test = self.loader.get_test(test_id)
        return test.to_dict() if test else None
    
    def create_test(self, domain_id: str, level: int, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new test in a domain/level"""
        # Validate domain exists
        domain = self.loader.load_domain(domain_id)
        if not domain:
            raise ValueError(f"Domain '{domain_id}' not found")
        
        # Generate ID if not provided
        if 'id' not in data or not data['id']:
            base_name = data.get('name', 'test')
            data['id'] = self._generate_id(f"{domain_id}_{level}_{base_name}")
        
        test_id = data['id']
        
        # Create test definition
        test = TestDefinition.from_dict(data, domain_id, level, "")
        
        # Validate
        errors = self.loader.validate_test(test)
        if errors:
            raise ValueError(f"Validation errors: {', '.join(errors)}")
        
        # Check if test already exists
        if self.loader.get_test(test_id):
            raise ValueError(f"Test '{test_id}' already exists")
        
        # Determine path
        domain_path = Path(domain.path)
        level_path = domain_path / f"level_{level}"
        level_path.mkdir(parents=True, exist_ok=True)
        
        test_file = level_path / f"{test_id}.json"
        
        # Add timestamps
        now = datetime.now().isoformat()
        data['created_at'] = now
        data['updated_at'] = now
        
        # Write test file
        with open(test_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        # Sync to database
        db_data = data.copy()
        db_data['domain_id'] = domain_id
        db_data['level'] = level
        db_data['path'] = str(test_file)
        db.upsert_test(db_data)
        
        # Clear cache
        self.loader.clear_cache()
        
        return self.get_test(test_id)
    
    def update_test(self, test_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing test"""
        test = self.loader.get_test(test_id)
        if not test:
            raise ValueError(f"Test '{test_id}' not found")
        
        test_file = Path(test.path)
        
        # Load existing data
        with open(test_file, 'r', encoding='utf-8') as f:
            existing = json.load(f)
        
        # Merge updates (don't allow changing domain/level via update)
        data.pop('domain_id', None)
        data.pop('level', None)
        data.pop('id', None)  # Don't allow changing ID
        
        existing.update(data)
        existing['updated_at'] = datetime.now().isoformat()
        
        # Write back
        with open(test_file, 'w', encoding='utf-8') as f:
            json.dump(existing, f, indent=2, ensure_ascii=False)
        
        # Sync to database
        db_data = existing.copy()
        db_data['domain_id'] = test.domain_id
        db_data['level'] = test.level
        db_data['path'] = str(test_file)
        db.upsert_test(db_data)
        
        # Clear cache
        self.loader.clear_cache()
        
        return self.get_test(test_id)
    
    def delete_test(self, test_id: str) -> bool:
        """Delete a test"""
        test = self.loader.get_test(test_id)
        if not test:
            return False
        
        test_file = Path(test.path)
        
        # Delete from filesystem
        if test_file.exists():
            test_file.unlink()
        
        # Delete from database
        db.delete_test(test_id)
        
        # Clear cache
        self.loader.clear_cache()
        
        return True
    
    def move_test(self, test_id: str, new_domain: str, new_level: int) -> Dict[str, Any]:
        """Move a test to a different domain/level"""
        test = self.loader.get_test(test_id)
        if not test:
            raise ValueError(f"Test '{test_id}' not found")
        
        # Validate new domain
        domain = self.loader.load_domain(new_domain)
        if not domain:
            raise ValueError(f"Domain '{new_domain}' not found")
        
        if test.domain_id == new_domain and test.level == new_level:
            return self.get_test(test_id)  # No change needed
        
        old_path = Path(test.path)
        new_domain_path = Path(domain.path)
        new_level_path = new_domain_path / f"level_{new_level}"
        new_level_path.mkdir(parents=True, exist_ok=True)
        
        new_path = new_level_path / f"{test_id}.json"
        
        # Read existing test data
        with open(old_path, 'r', encoding='utf-8') as f:
            test_data = json.load(f)
        
        # Update metadata
        test_data['domain_id'] = new_domain
        test_data['level'] = new_level
        test_data['updated_at'] = datetime.now().isoformat()
        
        # Write to new location
        with open(new_path, 'w', encoding='utf-8') as f:
            json.dump(test_data, f, indent=2, ensure_ascii=False)
        
        # Delete old file
        old_path.unlink()
        
        # Sync to database
        db_data = test_data.copy()
        db_data['path'] = str(new_path)
        db.upsert_test(db_data)
        
        # Clear cache
        self.loader.clear_cache()
        
        return self.get_test(test_id)
    
    # ==================== Evaluator Operations ====================
    
    def list_evaluators(self) -> List[Dict[str, Any]]:
        """List all evaluators"""
        evaluators = self.loader.load_evaluators()
        return [e.to_dict() for e in evaluators]
    
    def get_evaluator(self, evaluator_id: str) -> Optional[Dict[str, Any]]:
        """Get a single evaluator by ID"""
        evaluator = self.loader.get_evaluator(evaluator_id)
        return evaluator.to_dict() if evaluator else None
    
    def create_evaluator(self, data: Dict[str, Any], is_custom: bool = True) -> Dict[str, Any]:
        """Create a new custom evaluator"""
        # Generate ID if not provided
        if 'id' not in data or not data['id']:
            data['id'] = self._generate_id(data.get('name', 'new_evaluator'))
        
        evaluator_id = data['id']
        
        # Check if evaluator already exists
        if self.loader.get_evaluator(evaluator_id):
            raise ValueError(f"Evaluator '{evaluator_id}' already exists")
        
        # Determine path
        base_dir = self.custom_evaluators_dir if is_custom else self.evaluators_dir
        base_dir.mkdir(parents=True, exist_ok=True)
        
        eval_file = base_dir / f"{evaluator_id}.json"
        
        # Write evaluator file
        with open(eval_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        # Sync to database
        db_data = data.copy()
        db_data['path'] = str(eval_file)
        db.upsert_evaluator(db_data)
        
        # Clear cache
        self.loader.clear_cache()
        
        return self.get_evaluator(evaluator_id)
    
    def update_evaluator(self, evaluator_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing evaluator"""
        evaluator = self.loader.get_evaluator(evaluator_id)
        if not evaluator:
            raise ValueError(f"Evaluator '{evaluator_id}' not found")
        
        eval_file = Path(evaluator.path)
        
        # Load existing data
        with open(eval_file, 'r', encoding='utf-8') as f:
            existing = json.load(f)
        
        # Merge updates
        data.pop('id', None)  # Don't allow changing ID
        existing.update(data)
        
        # Write back
        with open(eval_file, 'w', encoding='utf-8') as f:
            json.dump(existing, f, indent=2, ensure_ascii=False)
        
        # Sync to database
        db_data = existing.copy()
        db_data['path'] = str(eval_file)
        db.upsert_evaluator(db_data)
        
        # Clear cache
        self.loader.clear_cache()
        
        return self.get_evaluator(evaluator_id)
    
    def delete_evaluator(self, evaluator_id: str) -> bool:
        """Delete a custom evaluator"""
        evaluator = self.loader.get_evaluator(evaluator_id)
        if not evaluator:
            return False
        
        # Don't allow deleting predefined evaluators
        if evaluator.type == 'predefined':
            raise ValueError("Cannot delete predefined evaluators")
        
        eval_file = Path(evaluator.path)
        
        # Delete from filesystem
        if eval_file.exists():
            eval_file.unlink()
        
        # Delete from database
        db.delete_evaluator(evaluator_id)
        
        # Clear cache
        self.loader.clear_cache()
        
        return True
    
    # ==================== Sync Operations ====================
    
    def sync_to_db(self):
        """Sync all test definitions to database cache"""
        # Sync domains
        for domain in self.loader.scan_domains():
            domain_data = domain.to_dict()
            db.upsert_domain(domain_data)
        
        # Sync tests
        for test in self.loader.load_all_tests():
            test_data = test.to_dict()
            db.upsert_test(test_data)
        
        # Sync evaluators
        for evaluator in self.loader.load_evaluators():
            eval_data = evaluator.to_dict()
            db.upsert_evaluator(eval_data)
    
    def sync_from_db(self):
        """Sync database cache to files (for import)"""
        # This is used when importing from database backup
        domains = db.get_domains()
        for domain in domains:
            domain_path = self.tests_dir / domain['id']
            domain_path.mkdir(parents=True, exist_ok=True)
            
            # Write domain.json
            domain_data = {
                'id': domain['id'],
                'name': domain['name'],
                'description': domain.get('description', ''),
                'icon': domain.get('icon', 'file'),
                'color': domain.get('color', '#3B82F6'),
                'evaluator_id': domain.get('evaluator_id', ''),
                'enabled': domain.get('enabled', True),
            }
            
            with open(domain_path / 'domain.json', 'w', encoding='utf-8') as f:
                json.dump(domain_data, f, indent=2, ensure_ascii=False)
    
    # ==================== Import/Export ====================
    
    def export_all(self) -> Dict[str, Any]:
        """Export all test definitions as a dictionary"""
        result = {
            'domains': [],
            'evaluators': [],
            'exported_at': datetime.now().isoformat(),
            'version': '1.0'
        }
        
        # Export domains with tests
        for domain in self.loader.scan_domains():
            domain_data = domain.to_dict()
            domain_data['tests'] = {}
            
            for level in range(1, 6):
                tests = self.loader.load_tests_by_level(domain.id, level)
                domain_data['tests'][str(level)] = [t.to_dict() for t in tests]
            
            result['domains'].append(domain_data)
        
        # Export evaluators
        for evaluator in self.loader.load_evaluators():
            result['evaluators'].append(evaluator.to_dict())
        
        return result
    
    def import_all(self, data: Dict[str, Any], merge: bool = True) -> Dict[str, Any]:
        """Import test definitions from a dictionary
        
        Args:
            data: Export data dictionary
            merge: If True, merge with existing. If False, replace.
            
        Returns:
            Import result summary
        """
        result = {
            'domains_imported': 0,
            'tests_imported': 0,
            'evaluators_imported': 0,
            'errors': []
        }
        
        # Import evaluators first
        for eval_data in data.get('evaluators', []):
            try:
                if merge and self.loader.get_evaluator(eval_data['id']):
                    self.update_evaluator(eval_data['id'], eval_data)
                else:
                    self.create_evaluator(eval_data, is_custom=True)
                result['evaluators_imported'] += 1
            except Exception as e:
                result['errors'].append(f"Evaluator {eval_data.get('id')}: {str(e)}")
        
        # Import domains and tests
        for domain_data in data.get('domains', []):
            try:
                domain_id = domain_data['id']
                
                # Create or update domain
                if merge and self.loader.load_domain(domain_id):
                    self.update_domain(domain_id, domain_data)
                else:
                    self.create_domain(domain_data, is_custom=True)
                
                result['domains_imported'] += 1
                
                # Import tests
                tests_by_level = domain_data.get('tests', {})
                for level_str, tests in tests_by_level.items():
                    level = int(level_str)
                    for test_data in tests:
                        try:
                            test_data['domain_id'] = domain_id
                            test_data['level'] = level
                            
                            if merge and self.loader.get_test(test_data['id']):
                                self.update_test(test_data['id'], test_data)
                            else:
                                self.create_test(domain_id, level, test_data)
                            
                            result['tests_imported'] += 1
                        except Exception as e:
                            result['errors'].append(f"Test {test_data.get('id')}: {str(e)}")
                            
            except Exception as e:
                result['errors'].append(f"Domain {domain_data.get('id')}: {str(e)}")
        
        # Clear cache
        self.loader.clear_cache()
        
        return result
    
    # ==================== Helpers ====================
    
    def _generate_id(self, name: str) -> str:
        """Generate a valid ID from a name"""
        # Convert to lowercase, replace spaces with underscores, remove special chars
        id_str = name.lower().strip()
        id_str = re.sub(r'[^a-z0-9_]', '_', id_str)
        id_str = re.sub(r'_+', '_', id_str)  # Remove duplicate underscores
        id_str = id_str.strip('_')
        
        # Add timestamp suffix for uniqueness
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        return f"{id_str}_{timestamp}"


# Global manager instance
test_manager = TestManager()