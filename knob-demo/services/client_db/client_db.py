from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import os

app = Flask(__name__)
CORS(app)

# In-memory client database
clients = {
    "client1": {
        "password": "pw1",
        "approved": True,
        "current_gk": "1234567890123456"
    },
    "client2": {
        "password": "pw2",
        "approved": True,
        "current_gk": "1234567890123456"
    }
}

@app.route('/login', methods=['POST'])
def login():
    """Authenticate client and return their current GK"""
    client_id = request.form.get('client_id', '')
    password = request.form.get('password', '')
    
    if not client_id or not password:
        return jsonify({'error': 'Missing client_id or password'}), 400
    
    if client_id not in clients:
        return jsonify({'error': 'Invalid client'}), 404
    
    client = clients[client_id]
    if client['password'] != password:
        return jsonify({'error': 'Invalid password'}), 401
    
    return jsonify({
        'client_id': client_id,
        'approved': client['approved'],
        'current_gk': client['current_gk']
    }), 200

@app.route('/clients/<client_id>', methods=['GET'])
def get_client(client_id):
    """Get client info (approval status and current GK)"""
    if client_id not in clients:
        return jsonify({'error': 'Client not found'}), 404
    
    client = clients[client_id]
    return jsonify({
        'client_id': client_id,
        'approved': client['approved'],
        'current_gk': client['current_gk']
    }), 200

@app.route('/admin/sync_gk', methods=['POST'])
def sync_gk():
    """Update approved clients with new GK (called after re-encryption)"""
    new_gk = request.form.get('new_gk', '')
    
    if not new_gk or len(new_gk) != 16:
        return jsonify({'error': 'Invalid GK (must be 16 chars)'}), 400
    
    updated = []
    for client_id, client in clients.items():
        if client['approved']:
            client['current_gk'] = new_gk
            updated.append(client_id)
    
    return jsonify({
        'status': 'ok',
        'new_gk': new_gk,
        'updated_clients': updated
    }), 200

@app.route('/admin/clients', methods=['GET'])
def admin_list_clients():
    """Admin: List all clients"""
    result = []
    for client_id, client in clients.items():
        result.append({
            'client_id': client_id,
            'approved': client['approved'],
            'current_gk': client['current_gk']
        })
    return jsonify({'clients': result}), 200

@app.route('/admin/approve/<client_id>', methods=['POST'])
def admin_approve(client_id):
    """Admin: Approve a client"""
    if client_id not in clients:
        return jsonify({'error': 'Client not found'}), 404
    
    clients[client_id]['approved'] = True
    return jsonify({'status': 'ok', 'client_id': client_id}), 200

@app.route('/admin/revoke/<client_id>', methods=['POST'])
def admin_revoke(client_id):
    """Admin: Revoke a client"""
    if client_id not in clients:
        return jsonify({'error': 'Client not found'}), 404
    
    clients[client_id]['approved'] = False
    return jsonify({'status': 'ok', 'client_id': client_id}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5004, debug=True)
