from flask import Flask, render_template, jsonify, request, Response, stream_with_context
import queue
import time
import json
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from evaluator.engine import evaluation_engine
from models.db import db
import config

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')

@app.route('/')
def index():
    """Main dashboard"""
    status = evaluation_engine.get_status()
    return render_template('index.html', status=status)

@app.route('/api/status')
def api_status():
    """Get evaluation status"""
    status = evaluation_engine.get_status()
    return jsonify(status)

@app.route('/api/start', methods=['POST'])
def api_start():
    """Start evaluation"""
    try:
        data = request.get_json()
        model_name = data.get('model_name', 'default')
        
        run_id = evaluation_engine.start_evaluation(model_name)
        return jsonify({
            'success': True, 
            'run_id': run_id,
            'message': 'Evaluation started'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400

@app.route('/api/stop', methods=['POST'])
def api_stop():
    """Stop evaluation"""
    try:
        evaluation_engine.stop_evaluation()
        return jsonify({
            'success': True,
            'message': 'Evaluation stopped'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400

@app.route('/api/reset', methods=['POST'])
def api_reset():
    """Reset engine state to idle"""
    try:
        evaluation_engine.reset_state()
        return jsonify({
            'success': True,
            'message': 'State reset'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400

@app.route('/api/test_matrix')
def api_test_matrix():
    """Get test matrix for current run"""
    run_id = request.args.get('run_id')
    matrix = evaluation_engine.get_test_matrix(run_id)
    return jsonify(matrix)

@app.route('/history')
def history():
    """Evaluation history page"""
    runs = db.get_all_runs()
    return render_template('history.html', runs=runs)

@app.route('/history/<run_id>')
def history_detail(run_id):
    """Evaluation detail page - frozen result view"""
    run_info = db.get_evaluation_run(run_id)
    test_results = db.get_test_results(run_id)
    stats = db.get_run_stats(run_id)
    
    if not run_info:
        return "Run not found", 404
    
    return render_template('history_detail.html', 
                          run_info=run_info, 
                          test_results=test_results,
                          stats=stats)

@app.route('/api/run/<run_id>')
def api_run_details(run_id):
    """Get details for a specific run"""
    run_info = db.get_evaluation_run(run_id)
    test_results = db.get_test_results(run_id)
    stats = db.get_run_stats(run_id)
    
    return jsonify({
        'run_info': run_info,
        'test_results': test_results,
        'stats': stats
    })

@app.route('/api/run/<run_id>/matrix')
def api_run_matrix(run_id):
    """Get test matrix for a specific run (same format as /api/test_matrix)"""
    import json
    
    test_results = db.get_test_results(run_id)
    run_info = db.get_evaluation_run(run_id)
    model_name = run_info.get("model_name") if run_info else None
    
    # Organize by domain and level
    matrix = {}
    for domain in ["conversation", "math", "sql", "tool_calling", "reasoning"]:
        matrix[domain] = {}
        for level in range(1, 6):
            matrix[domain][level] = {
                "status": "pending",
                "score": None,
                "details": None,
                "prompt": None,
                "response": None,
                "expected": None,
                "duration_ms": None,
                "model_name": None
            }
    
    # Fill with actual results
    for result in test_results:
        domain = result["domain"]
        level = result["level"]
        
        if domain in matrix and level in matrix[domain]:
            matrix[domain][level] = {
                "status": result["status"],
                "score": result["score"],
                "details": json.loads(result["details"]) if result["details"] else None,
                "prompt": result.get("prompt"),
                "response": result.get("response"),
                "expected": json.loads(result["expected"]) if result.get("expected") else None,
                "duration_ms": result.get("duration_ms"),
                "model_name": result.get("model_name")
            }
    
    return jsonify({
        "domains": matrix,
        "run_id": run_id,
        "model_name": model_name,
        "status": "completed"
    })

@app.route('/api/config')
def api_config():
    """Get current configuration"""
    return jsonify({
        'llm_base_url': config.LLM_BASE_URL,
        'llm_model': config.LLM_MODEL,
        'debug': config.DEBUG
    })

@app.route('/api/config/model')
def api_config_model():
    """Get ONLY the model name (safe for client-side)"""
    from evaluator.llm_client import llm_client
    actual_model = llm_client.get_actual_model_name()
    return jsonify({
        'model': actual_model,
        'config_model': config.LLM_MODEL  # Also return config for comparison
    })

@app.route('/api/log_stream')
def log_stream():
    @stream_with_context
    def generate():
        yield "data: [SYSTEM] Log stream connected.\n\n"
        last_message_time = time.time()
        heartbeat_interval = 15  # Send heartbeat every 15 seconds
        last_heartbeat = time.time()
        
        while True:
            try:
                message = evaluation_engine.log_queue.get(timeout=0.5)  # Shorter timeout for responsiveness
                yield f"data: {message}\n\n"
                last_message_time = time.time()
                if message == "EVAL_COMPLETE":
                    break
            except queue.Empty:
                # Send heartbeat to keep connection alive
                if time.time() - last_heartbeat > heartbeat_interval:
                    yield ": heartbeat\n\n"  # SSE comment (ignored by client but keeps connection alive)
                    last_heartbeat = time.time()
                
                if not evaluation_engine.is_running and time.time() - last_message_time > 2:
                    # Drain any remaining messages in queue before closing
                    while not evaluation_engine.log_queue.empty():
                        try:
                            message = evaluation_engine.log_queue.get_nowait()
                            yield f"data: {message}\n\n"
                        except queue.Empty:
                            break
                    yield "data: [SYSTEM] Evaluation stopped. Closing stream.\n\n"
                    break
    
    response = Response(generate(), mimetype='text/event-stream')
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['X-Accel-Buffering'] = 'no'  # Disable nginx buffering
    response.headers['Connection'] = 'keep-alive'
    return response


# ==================== Settings API ====================

@app.route('/settings')
def settings():
    """Settings page - manage tests"""
    return render_template('settings.html')


# Domain operations
@app.route('/api/settings/domains', methods=['GET'])
def api_list_domains():
    """List all domains"""
    from evaluator.test_manager import test_manager
    domains = test_manager.list_domains()
    return jsonify({'domains': domains})


@app.route('/api/settings/domains/<domain_id>', methods=['GET'])
def api_get_domain(domain_id):
    """Get a single domain"""
    from evaluator.test_manager import test_manager
    domain = test_manager.get_domain(domain_id)
    if not domain:
        return jsonify({'error': 'Domain not found'}), 404
    return jsonify(domain)


@app.route('/api/settings/domains', methods=['POST'])
def api_create_domain():
    """Create a new domain"""
    from evaluator.test_manager import test_manager
    data = request.get_json()
    try:
        domain = test_manager.create_domain(data, is_custom=True)
        return jsonify({'success': True, 'domain': domain})
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/settings/domains/<domain_id>', methods=['PUT'])
def api_update_domain(domain_id):
    """Update a domain"""
    from evaluator.test_manager import test_manager
    data = request.get_json()
    try:
        domain = test_manager.update_domain(domain_id, data)
        return jsonify({'success': True, 'domain': domain})
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/settings/domains/<domain_id>', methods=['DELETE'])
def api_delete_domain(domain_id):
    """Delete a domain"""
    from evaluator.test_manager import test_manager
    try:
        success = test_manager.delete_domain(domain_id)
        return jsonify({'success': success})
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400


# Test operations
@app.route('/api/settings/tests', methods=['GET'])
def api_list_tests():
    """List tests"""
    from evaluator.test_manager import test_manager
    domain_id = request.args.get('domain')
    level = request.args.get('level', type=int)
    tests = test_manager.list_tests(domain_id=domain_id, level=level)
    return jsonify({'tests': tests})


@app.route('/api/settings/tests/<test_id>', methods=['GET'])
def api_get_test(test_id):
    """Get a single test"""
    from evaluator.test_manager import test_manager
    test = test_manager.get_test(test_id)
    if not test:
        return jsonify({'error': 'Test not found'}), 404
    return jsonify(test)


@app.route('/api/settings/tests', methods=['POST'])
def api_create_test():
    """Create a new test"""
    from evaluator.test_manager import test_manager
    data = request.get_json()
    domain_id = data.get('domain_id')
    level = data.get('level', 1)
    
    if not domain_id:
        return jsonify({'success': False, 'error': 'domain_id is required'}), 400
    
    try:
        test = test_manager.create_test(domain_id, level, data)
        return jsonify({'success': True, 'test': test})
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/settings/tests/<test_id>', methods=['PUT'])
def api_update_test(test_id):
    """Update a test"""
    from evaluator.test_manager import test_manager
    data = request.get_json()
    try:
        test = test_manager.update_test(test_id, data)
        return jsonify({'success': True, 'test': test})
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/settings/tests/<test_id>', methods=['DELETE'])
def api_delete_test(test_id):
    """Delete a test"""
    from evaluator.test_manager import test_manager
    try:
        success = test_manager.delete_test(test_id)
        return jsonify({'success': success})
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/settings/tests/<test_id>/move', methods=['POST'])
def api_move_test(test_id):
    """Move a test to different domain/level"""
    from evaluator.test_manager import test_manager
    data = request.get_json()
    new_domain = data.get('domain_id')
    new_level = data.get('level')
    
    if not new_domain or not new_level:
        return jsonify({'success': False, 'error': 'domain_id and level are required'}), 400
    
    try:
        test = test_manager.move_test(test_id, new_domain, new_level)
        return jsonify({'success': True, 'test': test})
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400


# Evaluator operations
@app.route('/api/settings/evaluators', methods=['GET'])
def api_list_evaluators():
    """List all evaluators"""
    from evaluator.test_manager import test_manager
    evaluators = test_manager.list_evaluators()
    return jsonify({'evaluators': evaluators})


@app.route('/api/settings/evaluators/<evaluator_id>', methods=['GET'])
def api_get_evaluator(evaluator_id):
    """Get a single evaluator"""
    from evaluator.test_manager import test_manager
    evaluator = test_manager.get_evaluator(evaluator_id)
    if not evaluator:
        return jsonify({'error': 'Evaluator not found'}), 404
    return jsonify(evaluator)


@app.route('/api/settings/evaluators', methods=['POST'])
def api_create_evaluator():
    """Create a new custom evaluator"""
    from evaluator.test_manager import test_manager
    data = request.get_json()
    try:
        evaluator = test_manager.create_evaluator(data, is_custom=True)
        return jsonify({'success': True, 'evaluator': evaluator})
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/settings/evaluators/<evaluator_id>', methods=['PUT'])
def api_update_evaluator(evaluator_id):
    """Update an evaluator"""
    from evaluator.test_manager import test_manager
    data = request.get_json()
    try:
        evaluator = test_manager.update_evaluator(evaluator_id, data)
        return jsonify({'success': True, 'evaluator': evaluator})
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/settings/evaluators/<evaluator_id>', methods=['DELETE'])
def api_delete_evaluator(evaluator_id):
    """Delete a custom evaluator"""
    from evaluator.test_manager import test_manager
    try:
        success = test_manager.delete_evaluator(evaluator_id)
        return jsonify({'success': success})
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400


# Import/Export operations
@app.route('/api/settings/export', methods=['GET'])
def api_export_tests():
    """Export all test definitions"""
    from evaluator.test_manager import test_manager
    data = test_manager.export_all()
    return jsonify(data)


@app.route('/api/settings/import', methods=['POST'])
def api_import_tests():
    """Import test definitions"""
    from evaluator.test_manager import test_manager
    data = request.get_json()
    merge = data.get('merge', True)
    result = test_manager.import_all(data, merge=merge)
    return jsonify(result)


@app.route('/api/settings/sync', methods=['POST'])
def api_sync_tests():
    """Sync test definitions to database"""
    from evaluator.test_manager import test_manager
    test_manager.sync_to_db()
    return jsonify({'success': True})


if __name__ == '__main__':
    app.run(
        host=config.HOST,
        port=config.PORT,
        debug=config.DEBUG,
        use_reloader=False  # Disable reloader to prevent killing evaluation thread
    )
