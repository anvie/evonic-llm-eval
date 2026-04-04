/**
 * Test Modal Component - Shared between index.html and history_detail.html
 * Two-column layout: test list on left, test details on right
 */

// Global state for modal
let currentModalTests = [];
let currentSelectedTestIndex = 0;

/**
 * Show modal with multiple tests (two-column layout)
 * @param {string} domain - Domain name
 * @param {number} level - Test level
 * @param {Array} tests - Array of test results
 * @param {Object} summaryData - Summary data with overall status
 */
function showModalWithTests(domain, level, tests, summaryData) {
    const modal = document.getElementById('test-modal');
    const header = document.getElementById('modal-header');
    const title = document.getElementById('modal-title');
    const body = document.getElementById('modal-body');
    
    currentModalTests = tests;
    currentSelectedTestIndex = 0;
    
    // Calculate summary stats
    const passed = tests.filter(t => t.status === 'passed').length;
    const total = tests.length;
    const overallStatus = summaryData?.status || (passed === total ? 'passed' : 'failed');
    
    const headerClass = overallStatus === 'passed' ? 'modal-header-success' : 'modal-header-error';
    header.className = 'modal-header ' + headerClass;
    title.innerHTML = `${domain.replace(/_/g, ' ').toUpperCase()} Level ${level} — ${passed}/${total} Passed`;
    
    // Two-column layout
    body.innerHTML = `
        <div class="modal-two-col">
            <div class="modal-test-list">
                <div class="test-list-header">Tests <span class="pass-count">${passed}/${total}</span></div>
                <div class="test-list-items" id="test-list-items">
                    ${tests.map((t, i) => `
                        <div class="test-list-item ${i === 0 ? 'active' : ''} ${t.status}" 
                             data-index="${i}" onclick="selectTest(${i})">
                            <span class="test-status-icon">${t.status === 'passed' ? '✓' : '✗'}</span>
                            <span class="test-name">${escapeHtml(t.test_id || t.name || 'Test ' + (i+1))}</span>
                        </div>
                    `).join('')}
                </div>
            </div>
            <div class="modal-test-detail" id="modal-test-detail">
                ${renderTestDetail(tests[0], domain)}
            </div>
        </div>
    `;
    
    modal.style.display = 'flex';
}

/**
 * Select a test from the list
 * @param {number} index - Test index
 */
function selectTest(index) {
    currentSelectedTestIndex = index;
    
    // Update active state in list
    document.querySelectorAll('.test-list-item').forEach((el, i) => {
        el.classList.toggle('active', i === index);
    });
    
    // Update detail view
    const detailDiv = document.getElementById('modal-test-detail');
    const test = currentModalTests[index];
    detailDiv.innerHTML = renderTestDetail(test, test.domain);
}

/**
 * Render test detail panel
 * @param {Object} test - Test result object
 * @param {string} domain - Domain name (for training data)
 * @returns {string} HTML string
 */
function renderTestDetail(test, domain) {
    if (!test) return '<div class="no-test">No test data</div>';
    
    const details = test.details || {};
    const scoreDisplay = test.score !== null ? (test.score * 100).toFixed(1) + '%' : 'N/A';
    const scoreClass = test.status === 'passed' ? 'score-passed' : 'score-failed';

    let html = `
        <div class="test-detail-header">
            <h3>${escapeHtml(test.test_id || test.name || 'Test')}</h3>
            <div class="test-meta">
                <span class="score ${scoreClass}">${scoreDisplay}</span>
                <span class="status-badge status-badge-${test.status}">${test.status.toUpperCase()}</span>
                ${test.duration_ms ? `<span class="duration">${test.duration_ms}ms</span>` : ''}
            </div>
        </div>
    `;
    
    // Tools Available section - compact inline format
    if (details.tools_available && details.tools_available.length > 0) {
        const toolsText = details.tools_available.map(t => {
            const params = t.parameters?.properties 
                ? Object.keys(t.parameters.properties).join(', ')
                : '';
            return `<span class="tool-name">${escapeHtml(t.name)}</span>(<span class="tool-params-inline">${params}</span>)`;
        }).join(' • ');
        
        html += `
            <div class="test-detail-section">
                <div class="section-header">🔧 AVAILABLE TOOLS (${details.tools_available.length})</div>
                <div class="section-content tools-box">${toolsText}</div>
            </div>
        `;
    }

    html += `
        <div class="test-detail-section">
            <div class="section-header">📥 PROMPT</div>
            <div class="section-content prompt-box">${escapeHtml(test.prompt || '')}</div>
        </div>
        
        <div class="test-detail-section">
            <div class="section-header">🎯 EXPECTED</div>
            <div class="section-content expected-box">${formatExpected(test.expected)}</div>
        </div>
    `;

    // Conversation Log (multi-turn)
    if (details.conversation_log && details.conversation_log.length > 0) {
        html += `
            <div class="test-detail-section">
                <div class="section-header">TURNS (${details.conversation_log.length})</div>
                <div class="space-y-2">
                    ${details.conversation_log.map((turn, i) => `
                        <div class="border border-gray-200 rounded text-xs">
                            <div class="bg-gray-100 px-2 py-1 font-semibold text-gray-600 border-b border-gray-200">Turn ${turn.turn || i+1}</div>
                            ${turn.thinking ? `
                                <div class="px-2 py-1 bg-purple-50 border-b border-gray-100">
                                    <span class="text-purple-600 font-medium">💭 [thinking]</span><br />
                                    <pre class="text-gray-700 ml-1 overflow-wrap text-wrap max-h-full overflow-y-auto">${escapeHtml(turn.thinking)}</pre>
                                </div>
                            ` : ''}
                            ${turn.tool_calls && turn.tool_calls.length > 0 ? `
                                <div class="px-2 py-1 bg-blue-50 border-b border-gray-100 font-mono">
                                    <span class="text-blue-600">🔧</span>
                                    ${turn.tool_calls.map(tc => `<span class="text-indigo-600 font-semibold ml-1">${escapeHtml(tc.name)}</span><span class="text-gray-500">(${escapeHtml(JSON.stringify(tc.arguments || {})).substring(0, 60)})</span>`).join(' ')}
                                </div>
                            ` : ''}
                            ${turn.tool_results && turn.tool_results.length > 0 ? `
                                <div class="px-2 py-1 bg-green-50 border-b border-gray-100 font-mono text-gray-600">
                                    <span class="text-green-600">📥</span>
                                    <span class="ml-1">${escapeHtml(JSON.stringify(turn.tool_results[0]?.result || {}, null, 0)).substring(0, 120)}${JSON.stringify(turn.tool_results[0]?.result || {}).length > 120 ? '...' : ''}</span>
                                </div>
                            ` : ''}
                            ${turn.response ? `
                                <div class="px-2 py-1 bg-amber-50 font-semibold text-md md:text-lg">
                                    <p class="text-amber-600">💬 [response]</p>
                                    <p class="text-gray-700 ml-1">${escapeHtml(turn.response)}</p>
                                </div>
                            ` : ''}
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
    } else if (details.thinking) {
        // Single-turn thinking
        html += `
            <div class="test-detail-section">
                <div class="section-header">🧠 THINKING</div>
                <div class="section-content thinking-box">
                    <pre>${escapeHtml(details.thinking)}</pre>
                </div>
            </div>
        `;
    }
    
    // Evaluation Details
    if (details.evaluator || details.called_tools || details.missing_tools) {
        html += `
            <div class="test-detail-section">
                <div class="section-header">🔍 EVALUATION</div>
                <div class="section-content eval-box">
                    ${details.evaluator ? `<div><strong>Evaluator:</strong> ${escapeHtml(details.evaluator)}</div>` : ''}
                    ${details.called_tools ? `<div><strong>Called:</strong> ${details.called_tools.map(t => `<code>${escapeHtml(t)}</code>`).join(', ')}</div>` : ''}
                    ${details.missing_tools && details.missing_tools.length > 0 ? `<div style="color: #dc2626;"><strong>Missing:</strong> ${details.missing_tools.map(t => `<code>${escapeHtml(t)}</code>`).join(', ')}</div>` : ''}
                </div>
            </div>
        `;
    }
    
    // Generate Training Data button
    if (details.conversation_log && details.conversation_log.length > 0) {
        html += `
            <div class="test-detail-section" style="margin-top: 1.5rem; padding-top: 1rem; border-top: 2px dashed #e5e7eb;">
                <button onclick="onGenerateTrainingDataClick(currentSelectedTestIndex)" 
                        style="width: 100%; padding: 0.6rem 1rem; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                               color: white; border: none; border-radius: 6px; font-size: 0.9rem; font-weight: 600; 
                               cursor: pointer; display: flex; align-items: center; justify-content: center; gap: 0.5rem;
                               transition: transform 0.2s, box-shadow 0.2s;"
                        onmouseover="this.style.transform='translateY(-2px)'; this.style.boxShadow='0 4px 12px rgba(102, 126, 234, 0.4)';"
                        onmouseout="this.style.transform='translateY(0)'; this.style.boxShadow='none';">
                    📋 Generate Training Data
                </button>
            </div>
        `;
    }
    
    return html;
}

/**
 * Show modal with no data (pending state)
 * @param {string} domain - Domain name
 * @param {number} level - Test level
 */
function showModalNoData(domain, level) {
    const modal = document.getElementById('test-modal');
    const header = document.getElementById('modal-header');
    const title = document.getElementById('modal-title');
    const body = document.getElementById('modal-body');
    
    header.className = 'modal-header';
    title.innerHTML = `${domain.toUpperCase()} Level ${level}`;
    
    body.innerHTML = `
        <div style="text-align: center; padding: 2rem; color: #666;">
            <div style="font-size: 3rem; margin-bottom: 1rem;">⏳</div>
            <p>No test data available yet.</p>
            <p style="font-size: 0.9rem;">This test has not been executed or is still pending.</p>
        </div>
    `;
    
    modal.style.display = 'flex';
}

/**
 * Close the test modal
 */
function closeModal() {
    document.getElementById('test-modal').style.display = 'none';
}

/**
 * Escape HTML special characters
 * @param {string} text - Text to escape
 * @returns {string} Escaped text
 */
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Format expected output for display
 * @param {*} expected - Expected value (can be string, object, etc.)
 * @returns {string} HTML string
 */
function formatExpected(expected) {
    if (!expected) {
        return '<em style="color: #999;">No expected output defined</em>';
    }
    
    try {
        const parsed = typeof expected === 'string' ? JSON.parse(expected) : expected;
        
        if (typeof parsed === 'object') {
            // Tool calling format
            if (parsed.tools && Array.isArray(parsed.tools)) {
                return `<strong>Expected Tools:</strong> ${parsed.tools.map(t => `<code style="background: #e0e7ff; padding: 0.25rem 0.5rem; border-radius: 4px;">${escapeHtml(t)}</code>`).join(' → ')}`;
            }
            
            if (parsed.tool) {
                let html = `<strong>Expected Tool:</strong> <code style="background: #e0e7ff; padding: 0.25rem 0.5rem; border-radius: 4px;">${escapeHtml(parsed.tool)}</code>`;
                if (parsed.result !== undefined) {
                    html += `<br><strong>Expected Result:</strong> ${escapeHtml(String(parsed.result))}`;
                }
                return html;
            }
            
            if (parsed.keywords) {
                let html = '<strong>Expected Keywords:</strong><br>';
                html += '<div style="display: flex; flex-wrap: wrap; gap: 0.5rem;">';
                parsed.keywords.forEach(kw => {
                    html += `<span style="background: #d1fae5; padding: 0.25rem 0.5rem; border-radius: 4px; font-size: 0.85rem;">${escapeHtml(kw)}</span>`;
                });
                html += '</div>';
                return html;
            }
            
            // Default: show as JSON
            return `<pre style="background: #f1f5f9; padding: 0.75rem; border-radius: 4px; overflow-x: auto; font-size: 0.85rem;">${escapeHtml(JSON.stringify(parsed, null, 2))}</pre>`;
        }
        
        return escapeHtml(String(parsed));
    } catch (e) {
        return escapeHtml(String(expected));
    }
}

// Handle escape key and click-outside for test modal
document.addEventListener('DOMContentLoaded', function() {
    document.addEventListener('keydown', function(event) {
        if (event.key === 'Escape') {
            const trainingModal = document.getElementById('training-modal');
            // Close training modal first if visible, otherwise close test modal
            if (trainingModal && trainingModal.style.display === 'flex') {
                // Training modal escape is handled by training-data.js
                return;
            }
            closeModal();
        }
    });
    
    window.addEventListener('click', function(event) {
        const testModal = document.getElementById('test-modal');
        if (event.target === testModal) {
            closeModal();
        }
    });
});
