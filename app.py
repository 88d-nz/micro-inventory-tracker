#!/usr/bin/env python3
"""
Micro Inventory Tracker
A simple inventory management system for tracking raw materials, BOMs, and production.
"""

from flask import Flask, render_template_string, request, redirect, url_for, flash, jsonify, Response
import sqlite3
import os
import csv
from io import StringIO
from datetime import datetime
from functools import wraps

app = Flask(__name__)
app.secret_key = 'micro-inventory-key-2024'

DB_PATH = os.path.join(os.path.dirname(__file__), 'inventory.db')

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS product_groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS raw_materials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            unit TEXT DEFAULT 'pcs',
            quantity REAL DEFAULT 0,
            cost_per_unit REAL DEFAULT 0,
            group_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (group_id) REFERENCES product_groups (id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS finished_goods (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            sku TEXT,
            unit TEXT DEFAULT 'pcs',
            quantity REAL DEFAULT 0,
            group_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (group_id) REFERENCES product_groups (id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS boms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            finished_good_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            version INTEGER DEFAULT 1,
            active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (finished_good_id) REFERENCES finished_goods (id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bom_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bom_id INTEGER NOT NULL,
            item_type TEXT CHECK(item_type IN ('material', 'labor')) NOT NULL,
            raw_material_id INTEGER,
            name TEXT,
            quantity REAL NOT NULL,
            cost_per_unit REAL DEFAULT 0,
            FOREIGN KEY (bom_id) REFERENCES boms (id),
            FOREIGN KEY (raw_material_id) REFERENCES raw_materials (id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS production_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            finished_good_id INTEGER NOT NULL,
            bom_id INTEGER NOT NULL,
            quantity_produced REAL NOT NULL,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (finished_good_id) REFERENCES finished_goods (id),
            FOREIGN KEY (bom_id) REFERENCES boms (id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS stock_adjustments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_type TEXT CHECK(item_type IN ('material', 'finished')) NOT NULL,
            item_id INTEGER NOT NULL,
            old_quantity REAL NOT NULL,
            new_quantity REAL NOT NULL,
            reason TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    conn.commit()
    conn.close()

init_db()

TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Micro Inventory Tracker</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        :root {
            --primary: #2c3e50;
            --secondary: #3498db;
            --success: #27ae60;
            --warning: #f39c12;
            --danger: #e74c3c;
            --light: #ecf0f1;
            --dark: #2c3e50;
        }
        .sidebar {
            position: fixed;
            top: 0;
            left: 0;
            height: 100vh;
            width: 250px;
            background: var(--primary);
            color: white;
            padding-top: 20px;
            overflow-y: auto;
        }
        .sidebar .nav-link {
            color: rgba(255,255,255,0.8);
            padding: 10px 20px;
            display: block;
            text-decoration: none;
            transition: all 0.3s;
        }
        .sidebar .nav-link:hover, .sidebar .nav-link.active {
            background: rgba(255,255,255,0.1);
            color: white;
        }
        .main-content {
            margin-left: 250px;
            padding: 20px;
        }
        .card {
            margin-bottom: 20px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.08);
        }
        .stat-card {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border-radius: 10px;
            padding: 20px;
            text-align: center;
            margin-bottom: 20px;
        }
        .stat-card h3 {
            font-size: 2rem;
            margin: 0;
        }
        .stat-card p {
            opacity: 0.9;
            margin: 0;
        }
        .table th {
            background: #f8f9fa;
        }
        .badge-group { background: var(--secondary); color: white; }
        .badge-warning { background: var(--warning); color: white; }
        .badge-danger { background: var(--danger); color: white; }
        .group-badge { background: var(--secondary); color: white; }
    </style>
</head>
<body>
    <div class="sidebar">
        <h4 class="text-center mb-4">Micro Inventory</h4>
        <a href="{{ url_for('dashboard') }}" class="nav-link {{ 'active' if active == 'dashboard' else '' }}">
            <i class="fas fa-tachometer-alt me-2"></i>Dashboard
        </a>
        <a href="{{ url_for('groups') }}" class="nav-link {{ 'active' if active == 'groups' else '' }}">
            <i class="fas fa-folder me-2"></i>Product Groups
        </a>
        <a href="{{ url_for('raw_materials') }}" class="nav-link {{ 'active' if active == 'materials' else '' }}">
            <i class="fas fa-boxes me-2"></i>Raw Materials
        </a>
        <a href="{{ url_for('finished_goods_view') }}" class="nav-link {{ 'active' if active == 'finished' else '' }}">
            <i class="fas fa-cube me-2"></i>Finished Goods
        </a>
        <a href="{{ url_for('boms') }}" class="nav-link {{ 'active' if active == 'boms' else '' }}">
            <i class="fas fa-sitemap me-2"></i>BOMs & Recipes
        </a>
        <a href="{{ url_for('production') }}" class="nav-link {{ 'active' if active == 'production' else '' }}">
            <i class="fas fa-industry me-2"></i>Production
        </a>
        <a href="{{ url_for('stock_adj') }}" class="nav-link {{ 'active' if active == 'adjustments' else '' }}">
            <i class="fas fa-sliders-h me-2"></i>Stock Adjustments
        </a>
        <a href="{{ url_for('export') }}" class="nav-link {{ 'active' if active == 'export' else '' }}">
            <i class="fas fa-file-export me-2"></i>Export Data
        </a>
        <a href="{{ url_for('about') }}" class="nav-link {{ 'active' if active == 'about' else '' }}">
            <i class="fas fa-info-circle me-2"></i>About
        </a>
    </div>
    <div class="main-content">
        {% with messages = get_flashed_messages() %}
            {% if messages %}
                <div class="alert alert-info alert-dismissible fade show" role="alert">
                    {% for message in messages %}
                        {{ message }}
                    {% endfor %}
                    <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                </div>
            {% endif %}
        {% endwith %}
        {% block content %}{% endblock %}
    </div>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
'''

def render_page(content, active='dashboard'):
    return render_template_string(TEMPLATE, active=active, content=content)

@app.route('/')
def dashboard():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) as count FROM raw_materials")
    materials_count = cursor.fetchone()['count']

    cursor.execute("SELECT COUNT(*) as count FROM finished_goods")
    finished_count = cursor.fetchone()['count']

    cursor.execute("SELECT COUNT(*) as count FROM boms")
    boms_count = cursor.fetchone()['count']

    cursor.execute("SELECT COUNT(*) as count FROM production_records")
    production_count = cursor.fetchone()['count']

    cursor.execute("SELECT COUNT(*) as count FROM product_groups")
    groups_count = cursor.fetchone()['count']

    cursor.execute("SELECT * FROM raw_materials WHERE quantity <= 0 ORDER BY name")
    low_stock = cursor.fetchall()

    cursor.execute("""
        SELECT p.created_at, f.name, p.quantity_produced 
        FROM production_records p 
        JOIN finished_goods f ON p.finished_good_id = f.id 
        ORDER BY p.created_at DESC LIMIT 5
    """)
    recent_production = cursor.fetchall()

    conn.close()

    content = '''
    <h2 class="mb-4">Dashboard</h2>
    <div class="row mb-4">
        <div class="col-md-2">
            <div class="stat-card"><h3>%d</h3><p>Product Groups</p></div>
        </div>
        <div class="col-md-2"><div class="stat-card" style="background:linear-gradient(135deg,#1abc9c,#16a085);"><h3>%d</h3><p>Raw Materials</p></div></div>
        <div class="col-md-2"><div class="stat-card" style="background:linear-gradient(135deg,#9b59b6,#8e44ad);"><h3>%d</h3><p>Finished Goods</p></div></div>
        <div class="col-md-2"><div class="stat-card" style="background:linear-gradient(135deg,#e74c3c,#c0392b);"><h3>%d</h3><p>BOMs</p></div></div>
        <div class="col-md-2"><div class="stat-card" style="background:linear-gradient(135deg,#f39c12,#d35400);"><h3>%d</h3><p>Productions</p></div></div>
        <div class="col-md-2"><div class="stat-card" style="background:linear-gradient(135deg,#3498db,#2980b9);"><h3>%d</h3><p>Low Stock</p></div></div>
    </div>
    <div class="row">
        <div class="col-md-6">
            <div class="card">
                <div class="card-header"><h5 class="mb-0"><i class="fas fa-exclamation-triangle text-warning me-2"></i>Low Stock Materials</h5></div>
                <div class="card-body">''' % (groups_count, materials_count, finished_count, boms_count, production_count, len(low_stock))

    if low_stock:
        content += '<table class="table table-sm"><thead><tr><th>Material</th><th>Quantity</th><th>Unit</th></tr></thead><tbody>'
        for m in low_stock:
            content += '<tr><td>%s</td><td><span class="text-danger fw-bold">%g</span></td><td>%s</td></tr>' % (m['name'], m['quantity'], m['unit'])
        content += '</tbody></table>'
    else:
        content += '<p class="text-success">All materials in stock!</p>'

    content += '''
                </div>
            </div>
        </div>
        <div class="col-md-6">
            <div class="card">
                <div class="card-header"><h5 class="mb-0"><i class="fas fa-history me-2"></i>Recent Production</h5></div>
                <div class="card-body">'''
    if recent_production:
        content += '<table class="table table-sm"><thead><tr><th>Date</th><th>Product</th><th>Qty</th></tr></thead><tbody>'
        for prod in recent_production:
            content += '<tr><td>%s</td><td>%s</td><td>%g</td></tr>' % (prod['created_at'][:10], prod['name'], prod['quantity_produced'])
        content += '</tbody></table>'
    else:
        content += '<p class="text-muted">No production records yet.</p>'

    content += '''
                </div>
            </div>
        </div>
    </div>'''

    return render_page(content)

@app.route('/groups')
def groups():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM product_groups ORDER BY name")
    groups_list = cursor.fetchall()
    
    # Get material counts per group
    group_materials = {}
    for g in groups_list:
        cursor.execute("SELECT COUNT(*) as count FROM raw_materials WHERE group_id = ?", (g['id'],))
        group_materials[g['id']] = cursor.fetchone()['count']
    
    cursor.execute("SELECT COUNT(*) as count FROM raw_materials WHERE group_id IS NULL")
    unassigned = cursor.fetchone()['count']
    conn.close()

    content = '<h2 class="mb-4">Product Groups</h2><div class="d-flex justify-content-between align-items-center mb-3"><a href="#" class="btn btn-primary" data-bs-toggle="modal" data-bs-target="#addGroupModal"><i class="fas fa-plus me-2"></i>Add Group</a></div>'
    
    if unassigned > 0:
        content += '<div class="alert alert-warning"><i class="fas fa-exclamation-triangle me-2"></i>%d materials are not assigned to any group</div>' % unassigned
    
    content += '<div class="card"><div class="card-body"><table class="table table-hover"><thead><tr><th>Name</th><th>Materials</th><th>Actions</th></tr></thead><tbody>'
    
    for g in groups_list:
        content += '''
        <tr>
            <td><span class="badge bg-info">%s</span></td>
            <td>%d items</td>
            <td>
                <form method="POST" action="/delete_group/%d" style="display:inline;" onsubmit="return confirm('Are you sure?');">
                    <button type="submit" class="btn btn-sm btn-outline-danger"><i class="fas fa-trash"></i></button>
                </form>
            </td>
        </tr>''' % (g['name'], group_materials.get(g['id'], 0), g['id'])
    
    content += '''
        </tbody>
        </table>
        </div>
    </div>
    <div class="modal fade" id="addGroupModal" tabindex="-1">
        <div class="modal-dialog">
            <div class="modal-content">
                <form method="POST" action="/add_group">
                    <div class="modal-content">
                        <div class="modal-header"><h5 class="modal-title">Add Product Group</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div>
                        <div class="modal-body">
                            <div class="mb-3"><label class="form-label">Group Name</label><input type="text" name="name" class="form-control" required></div>
                        </div>
                        <div class="modal-footer"><button type="submit" class="btn btn-primary">Add Group</button></div>
                    </div>
                </form>
            </div>
        </div>
    </div>'''

    return render_page(content, 'groups')

@app.route('/add_group', methods=['POST'])
def add_group():
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO product_groups (name) VALUES (?)", (request.form['name'],))
        conn.commit()
        flash('Group added successfully', 'success')
    except sqlite3.IntegrityError:
        flash('Group name already exists', 'error')
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
    conn.close()
    return redirect(url_for('groups'))

@app.route('/delete_group/<int:group_id>', methods=['POST'])
def delete_group(group_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM product_groups WHERE id = ?", (group_id,))
    conn.commit()
    conn.close()
    flash('Group deleted', 'success')
    return redirect(url_for('groups'))

@app.route('/raw_materials')
def raw_materials():
    group_id = request.args.get('group', type=int)
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Get all groups for filter
    cursor.execute("SELECT * FROM product_groups ORDER BY name")
    groups = cursor.fetchall()
    
    if group_id:
        cursor.execute("SELECT * FROM raw_materials WHERE group_id = ? ORDER BY name", (group_id,))
    else:
        cursor.execute("SELECT * FROM raw_materials ORDER BY group_id, name")
    
    materials = cursor.fetchall()
    
    # Get group names for display
    group_map = {g['id']: g['name'] for g in groups}
    
    conn.close()
    
    group_filter = '<select name="group" class="form-select" onchange="filterMaterials(this.value)"><option value="">All Groups</option>'
    for g in groups:
        selected = 'selected' if g['id'] == group_id else ''
        group_filter += '<option value="%d" %s>%s</option>' % (g['id'], selected, g['name'])
    group_filter += '</select>'
    
    content = '''
    <h2 class="mb-4">Raw Materials</h2>
    <div class="d-flex justify-content-between align-items-center mb-3">
        <div style="width: 200px;">
            %s
        </div>
        <a href="#" class="btn btn-primary" data-bs-toggle="modal" data-bs-target="#addMaterialModal">
            <i class="fas fa-plus me-2"></i>Add Material
        </a>
    </div>
    
    <div class="card">
        <div class="card-body">
            <table class="table table-hover">
                <thead>
                    <tr>
                        <th>Material</th>
                        <th>Group</th>
                        <th>Quantity</th>
                        <th>Unit</th>
                        <th>Cost/Unit</th>
                        <th>Value</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>''' % group_filter
    
    for m in materials:
        value = m['quantity'] * m['cost_per_unit']
        group_name = group_map.get(m['group_id'], '<span class="text-muted">Unassigned</span>')
        content += '''
                    <tr>
                        <td><strong>%s</strong></td>
                        <td>%s</td>
                        <td>%g</td>
                        <td>%s</td>
                        <td>$%g</td>
                        <td>$%g</td>
                        <td>
                            <a href="#" class="btn btn-sm btn-outline-primary" data-bs-toggle="modal" data-bs-target="#adjustModal%s"><i class="fas fa-edit"></i></a>
                        </td>
                    </tr>''' % (m['name'], group_name, m['quantity'], m['unit'], m['cost_per_unit'], value, m['id'])
    
    content += '''
                </tbody>
            </table>
        </div>
    </div>
    ''' + _material_modals(materials, groups)
    
    return render_page(content, 'materials')

def _material_modals(materials, groups):
    modals = ''
    for m in materials:
        group_options = '<option value="">No Group</option>'
        for g in groups:
            selected = 'selected' if m['group_id'] == g['id'] else ''
            group_options += '<option value="%d" %s>%s</option>' % (g['id'], selected, g['name'])
        
        modals += '''
    <div class="modal fade" id="adjustModal%d" tabindex="-1">
        <div class="modal-dialog">
            <div class="modal-content">
                <form method="POST" action="/adjust_material/%d">
                    <div class="modal-dialog"><div class="modal-content">
                        <div class="modal-header"><h5 class="modal-title">Adjust %s</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div>
                        <div class="modal-body">
                            <div class="mb-3"><label class="form-label">Name</label><input type="text" name="name" class="form-control" value="%s"></div>
                            <div class="mb-3"><label class="form-label">Quantity</label><input type="number" step="0.01" name="quantity" class="form-control" value="%g"></div>
                            <div class="mb-3"><label class="form-label">Unit</label><input type="text" name="unit" class="form-control" value="%s"></div>
                            <div class="mb-3"><label class="form-label">Cost Per Unit</label><input type="number" step="0.01" name="cost_per_unit" class="form-control" value="%g"></div>
                            <div class="mb-3"><label class="form-label">Group</label><select name="group_id" class="form-select">%s</select></div>
                        </div>
                        <div class="modal-footer"><button type="submit" class="btn btn-primary">Update</button></div>
                    </div></div>
                </form>
            </div>
        </div>
    </div>''' % (m['id'], m['id'], m['name'], m['name'], m['quantity'], m['unit'], m['cost_per_unit'], group_options)
    
    return modals

@app.route('/add_material', methods=['POST'])
def add_material():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO raw_materials (name, unit, quantity, cost_per_unit, group_id) VALUES (?, ?, ?, ?, ?)", (
        request.form['name'],
        request.form.get('unit', 'pcs'),
        float(request.form.get('quantity', 0)),
        float(request.form.get('cost_per_unit', 0)),
        request.form.get('group_id') or None
    ))
    conn.commit()
    conn.close()
    flash('Material added', 'success')
    return redirect(url_for('raw_materials'))

@app.route('/adjust_material/<int:material_id>', methods=['POST'])
def adjust_material(material_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM raw_materials WHERE id = ?", (material_id,))
    old = cursor.fetchone()
    
    # Log the adjustment
    cursor.execute("INSERT INTO stock_adjustments (item_type, item_id, old_quantity, new_quantity, reason) VALUES (?, ?, ?, ?, ?)", (
        'material', material_id, float(old['quantity']), float(request.form['quantity']),
        'Manual adjustment via material edit'
    ))
    
    cursor.execute("UPDATE raw_materials SET name = ?, unit = ?, quantity = ?, cost_per_unit = ?, group_id = ? WHERE id = ?", (
        request.form['name'],
        request.form.get('unit', 'pcs'),
        float(request.form.get('quantity', 0)),
        float(request.form.get('cost_per_unit', 0)),
        request.form.get('group_id') or None,
        material_id
    ))
    conn.commit()
    conn.close()
    flash('Material updated', 'success')
    return redirect(url_for('raw_materials'))

@app.route('/finished_goods')
def finished_goods_view():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM finished_goods ORDER BY name")
    goods = cursor.fetchall()
    cursor.execute("SELECT * FROM product_groups ORDER BY name")
    groups = cursor.fetchall()
    conn.close()
    
    group_map = {g['id']: g['name'] for g in groups}
    
    content = '''
    <h2 class="mb-4">Finished Goods</h2>
    <div class="d-flex justify-content-between align-items-center mb-3">
        <div></div>
        <a href="#" class="btn btn-primary" data-bs-toggle="modal" data-bs-target="#addFinishedModal">
            <i class="fas fa-plus me-2"></i>Add Finished Good
        </a>
    </div>
    
    <div class="card">
        <div class="card-body">
            <table class="table table-hover">
                <thead>
                    <tr>
                        <th>Name</th>
                        <th>SKU</th>
                        <th>Group</th>
                        <th>Quantity</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>'''
    
    for f in goods:
        group_name = group_map.get(f['group_id'], '<span class="text-muted">Unassigned</span>')
        content += '''
                    <tr>
                        <td><strong>%s</strong></td>
                        <td>%s</td>
                        <td>%s</td>
                        <td>%g</td>
                        <td>
                            <a href="#" class="btn btn-sm btn-outline-primary" data-bs-toggle="modal" data-bs-target="#adjustFinishedModal%d"><i class="fas fa-edit"></i></a>
                        </td>
                    </tr>''' % (f['name'], f['sku'] or '', group_name, f['quantity'], f['id'])
    
    content += '''
                </tbody>
            </table>
        </div>
    </div>''' + _finished_good_modals(goods, groups)
    
    return render_page(content, 'finished')

def _finished_good_modals(goods, groups):
    group_options = '<option value="">No Group</option>'
    for g in groups:
        group_options += '<option value="%d">%s</option>' % (g['id'], g['name'])
    
    mod = ''
    for f in goods:
        selected_group = f['group_id'] or ''
        mod += '''
    <div class="modal fade" id="adjustFinishedModal%d" tabindex="-1">
        <div class="modal-dialog">
            <div class="modal-content">
                <form method="POST" action="/adjust_finished/%d">
                    <div class="modal-header"><h5 class="modal-title">Adjust %s</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div>
                    <div class="modal-body">
                        <div class="mb-3"><label class="form-label">Name</label><input type="text" name="name" class="form-control" value="%s"></div>
                        <div class="mb-3"><label class="form-label">SKU</label><input type="text" name="sku" class="form-control" value="%s"></div>
                        <div class="mb-3"><label class="form-label">Quantity</label><input type="number" step="0.01" name="quantity" class="form-control" value="%g"></div>
                        <div class="mb-3"><label class="form-label">Group</label><select name="group_id" class="form-select">%s</select></div>
                    </div>
                    <div class="modal-footer"><button type="submit" class="btn btn-primary">Update</button></div>
                </form>
            </div>
        </div>
    </div>''' % (f['id'], f['id'], f['name'], f['name'], f['sku'] or '', f['quantity'], group_options)
    
    mod += '''
    <div class="modal fade" id="addFinishedModal" tabindex="-1">
        <div class="modal-dialog">
            <div class="modal-content">
                <form method="POST" action="/add_finished">
                    <div class="modal-header"><h5 class="modal-title">Add Finished Good</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div>
                    <div class="modal-body">
                        <div class="mb-3"><label class="form-label">Name</label><input type="text" name="name" class="form-control" required></div>
                        <div class="mb-3"><label class="form-label">SKU</label><input type="text" name="sku" class="form-control"></div>
                        <div class="mb-3"><label class="form-label">Group</label><select name="group_id" class="form-select">%s</select></div>
                    </div>
                    <div class="modal-footer"><button type="submit" class="btn btn-primary">Add</button></div>
                </form>
            </div>
        </div>
    </div>''' % group_options
    
    return mod

@app.route('/add_finished', methods=['POST'])
def add_finished():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO finished_goods (name, sku, group_id) VALUES (?, ?, ?)", (
        request.form['name'],
        request.form.get('sku') or None,
        request.form.get('group_id') or None
    ))
    conn.commit()
    conn.close()
    flash('Finished good added', 'success')
    return redirect(url_for('finished_goods_view'))

@app.route('/adjust_finished/<int:good_id>', methods=['POST'])
def adjust_finished(good_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM finished_goods WHERE id = ?", (good_id,))
    old = cursor.fetchone()
    
    cursor.execute("INSERT INTO stock_adjustments (item_type, item_id, old_quantity, new_quantity, reason) VALUES (?, ?, ?, ?, ?)", (
        'finished', good_id, float(old['quantity']), float(request.form['quantity']),
        'Manual adjustment'
    ))
    
    cursor.execute("UPDATE finished_goods SET name = ?, sku = ?, quantity = ?, group_id = ? WHERE id = ?", (
        request.form['name'],
        request.form.get('sku') or None,
        float(request.form.get('quantity', 0)),
        request.form.get('group_id') or None,
        good_id
    ))
    conn.commit()
    conn.close()
    flash('Finished good updated', 'success')
    return redirect(url_for('finished_goods_view'))

@app.route('/boms')
def boms():
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM finished_goods ORDER BY name")
    finished = cursor.fetchall()
    
    cursor.execute("SELECT * FROM boms ORDER BY name")
    boms_list = cursor.fetchall()
    
    cursor.execute("""
        SELECT b.id, b.name as bom_name, b.version, b.active, 
               f.name as finished_name, b.created_at
        FROM boms b JOIN finished_goods f ON b.finished_good_id = f.id
        ORDER BY f.name, b.version DESC
    """)
    boms_data = cursor.fetchall()
    
    conn.close()
    
    content = '''
    <div class="d-flex justify-content-between align-items-center mb-4">
        <h2 class="mb-0">BOMs & Recipes</h2>
        <a href="#" class="btn btn-primary" data-bs-toggle="modal" data-bs-target="#addBomModal">
            <i class="fas fa-plus me-2"></i>Create BOM
        </a>
    </div>
    
    <div class="card">
        <div class="card-body">
            <table class="table table-hover">
                <thead>
                    <tr>
                        <th>BOM Name</th>
                        <th>Product</th>
                        <th>Version</th>
                        <th>Status</th>
                        <th>Items</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>'''
    
    for bom in boms_data:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM bom_items WHERE bom_id = ?", (bom['id'],))
        item_count = cursor.fetchone()['count']
        conn.close()
        
        status_badge = '<span class="badge bg-success">Active</span>' if bom['active'] else '<span class="badge bg-secondary">Draft</span>'
        
        content += '''
                    <tr>
                        <td><strong>%s</strong></td>
                        <td>%s</td>
                        <td>v%s</td>
                        <td>%s</td>
                        <td>%d items</td>
                        <td>
                            <a href="/bom/%d" class="btn btn-sm btn-outline-primary"><i class="fas fa-edit"></i></a>
                        </td>
                    </tr>''' % (bom['bom_name'], bom['finished_name'], bom['version'], status_badge, item_count, bom['id'])
    
    content += '''
                </tbody>
            </table>
        </div>
    </div>''' + _bom_modal(finished)
    
    return render_page(content, 'boms')

@app.route('/bom/<int:bom_id>')
def view_bom(bom_id):
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT b.*, f.name as finished_name, f.id as finished_id
        FROM boms b JOIN finished_goods f ON b.finished_good_id = f.id
        WHERE b.id = ?
    """, (bom_id,))
    bom = cursor.fetchone()
    
    cursor.execute("SELECT * FROM raw_materials ORDER BY name")
    materials = cursor.fetchall()
    
    cursor.execute("SELECT * FROM bom_items WHERE bom_id = ? ORDER BY item_type, name", (bom_id,))
    bom_items = cursor.fetchall()
    
    if not bom:
        conn.close()
        flash('BOM not found', 'error')
        return redirect(url_for('boms'))
    
    # Calculate total material cost
    total_material_cost = sum(item['quantity'] * item['cost_per_unit'] for item in bom_items if item['item_type'] == 'material')
    total_labor_cost = sum(item['quantity'] * item['cost_per_unit'] for item in bom_items if item['item_type'] == 'labor')
    total_cost = total_material_cost + total_labor_cost
    
    content = '''
    <div class="d-flex justify-content-between align-items-center mb-4">
        <h2>%s</h2>
        <a href="/boms" class="btn btn-secondary">Back to BOMs</a>
    </div>
    
    <div class="card mb-4">
        <div class="card-header">
            <h5 class="mb-0">BOM Details</h5>
        </div>
        <div class="card-body">
            <p><strong>Product:</strong> %s</p>
            <p><strong>Version:</strong> %s</p>
            <p><strong>Status:</strong> %s</p>
            <p><strong>Total Cost:</strong> $%.2f</p>
        </div>
    </div>
    
    <div class="card">
        <div class="card-header">
            <h5 class="mb-0">BOM Items</h5>
        </div>
        <div class="card-body">
            <table class="table table-hover">
                <thead>
                    <tr>
                        <th>Type</th>
                        <th>Item</th>
                        <th>Quantity</th>
                        <th>Cost/Unit</th>
                        <th>Total</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>''' % (bom['name'], bom['finished_name'], bom['version'], 
                               'Active' if bom['active'] else 'Draft', total_cost)
    
    for item in bom_items:
        total = item['quantity'] * item['cost_per_unit']
        item_type = 'Material' if item['item_type'] == 'material' else 'Labor'
        item_name = item['name']
        if item['item_type'] == 'material':
            cursor.execute("SELECT name, unit FROM raw_materials WHERE id = ?", (item['raw_material_id'],))
            mat = cursor.fetchone()
            if mat:
                item_name = '%s (%s)' % (mat['name'], mat['unit'])
        
        content += '''
                    <tr>
                        <td><span class="badge %s">%s</span></td>
                        <td>%s</td>
                        <td>%g</td>
                        <td>$%g</td>
                        <td>$%.2f</td>
                        <td>
                            <form method="POST" action="/delete_bom_item/%d" onsubmit="return confirm('Delete this item?');">
                                <button class="btn btn-sm btn-outline-danger"><i class="fas fa-trash"></i></button>
                            </form>
                        </td>
                    </tr>''' % (
            'bg-info' if item['item_type'] == 'material' else 'bg-warning',
            item_type, item_name, item['quantity'], item['cost_per_unit'], total, item['id']
        )
    
    content += '''
                </tbody>
            </table>
        </div>
    </div>
    
    <div class="card mb-4">
        <div class="card-header"><h5 class="mb-0">Add BOM Item</h5></div>
        <div class="card-body">
            <form method="POST" action="/add_bom_item" class="row g-3">
                <input type="hidden" name="bom_id" value="%d">
                <div class="col-md-2">
                    <label class="form-label">Type</label>
                    <select name="item_type" class="form-select" onchange="toggleItemFields()">
                        <option value="material">Material</option>
                        <option value="labor">Labor</option>
                    </select>
                </div>
                <div class="col-md-5">
                    <label class="form-label">Material</label>
                    <select name="raw_material_id" class="form-select">
                        <option value="">Select Material</option>''' % bom_id
    
    for m in materials:
        content += '<option value="%d">%s (%s)</option>' % (m['id'], m['name'], m['unit'])
    
    content += '''
                    </select>
                </div>
                <div class="col-md-5">
                    <label class="form-label">Description (if labor)</label>
                    <input type="text" name="name" class="form-control" placeholder="e.g., Assembly labor">
                </div>
                <div class="col-md-3">
                    <label class="form-label">Quantity</label>
                    <input type="number" step="0.01" name="quantity" class="form-control" required>
                </div>
                <div class="col-md-3">
                    <label class="form-label">Cost/Unit ($)</label>
                    <input type="number" step="0.01" name="cost_per_unit" class="form-control" required>
                </div>
                <div class="col-12">
                    <button type="submit" class="btn btn-primary">Add Item</button>
                </div>
            </form>
        </div>
    </div>'''
    
    conn.close()
    return render_page(content, 'boms')

@app.route('/add_bom_item', methods=['POST'])
def add_bom_item():
    conn = get_db()
    cursor = conn.cursor()
    
    item_type = request.form.get('item_type', 'material')
    raw_material_id = request.form.get('raw_material_id') or None
    name = request.form.get('name') or None
    
    cursor.execute("INSERT INTO bom_items (bom_id, item_type, raw_material_id, name, quantity, cost_per_unit) VALUES (?, ?, ?, ?, ?, ?)", (
        request.form['bom_id'],
        item_type,
        raw_material_id,
        name,
        float(request.form['quantity']),
        float(request.form['cost_per_unit'])
    ))
    conn.commit()
    conn.close()
    flash('BOM item added', 'success')
    return redirect(url_for('view_bom', bom_id=request.form['bom_id']))

@app.route('/delete_bom_item/<int:item_id>', methods=['POST'])
def delete_bom_item(item_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT bom_id FROM bom_items WHERE id = ?", (item_id,))
    bom = cursor.fetchone()
    if bom:
        cursor.execute("DELETE FROM bom_items WHERE id = ?", (item_id,))
        conn.commit()
        conn.close()
        flash('Item deleted', 'success')
        return redirect(url_for('view_bom', bom_id=bom['bom_id']))
    conn.close()
    return redirect(url_for('boms'))

def _bom_modal(finished_goods):
    options = ''
    for f in finished_goods:
        options += '<option value="%d">%s</option>' % (f['id'], f['name'])
    
    return '''
    <div class="modal fade" id="addBomModal" tabindex="-1">
        <div class="modal-dialog">
            <div class="modal-content">
                <form method="POST" action="/add_bom">
                    <div class="modal-header"><h5 class="modal-title">Create New BOM</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div>
                    <div class="modal-body">
                        <div class="mb-3"><label class="form-label">Product</label><select name="finished_good_id" class="form-select" required>%s</select></div>
                        <div class="mb-3"><label class="form-label">BOM Name</label><input type="text" name="name" class="form-control" required></div>
                    </div>
                    <div class="modal-footer"><button type="submit" class="btn btn-primary">Create BOM</button></div>
                </form>
            </div>
        </div>
    </div>''' % options

@app.route('/add_bom', methods=['POST'])
def add_bom():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO boms (finished_good_id, name) VALUES (?, ?)", (
        request.form['finished_good_id'],
        request.form['name']
    ))
    conn.commit()
    bom_id = cursor.lastrowid
    conn.close()
    flash('BOM created, add items below', 'success')
    return redirect(url_for('view_bom', bom_id=bom_id))

@app.route('/production')
def production():
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM finished_goods ORDER BY name")
    finished = cursor.fetchall()
    
    cursor.execute("""
        SELECT p.*, f.name as finished_name, b.name as bom_name
        FROM production_records p
        JOIN finished_goods f ON p.finished_good_id = f.id
        JOIN boms b ON p.bom_id = b.id
        ORDER BY p.created_at DESC
    """)
    records = cursor.fetchall()
    
    conn.close()
    
    content = '''
    <h2 class="mb-4">Production Records</h2>
    
    <div class="card mb-4">
        <div class="card-header"><h5 class="mb-0">Record Production</h5></div>
        <div class="card-body">
            <form method="POST" action="/record_production" class="row g-3">
                <div class="col-md-5">
                    <label class="form-label">Product</label>
                    <select name="finished_good_id" class="form-select" required onchange="loadBoms(this.value)">
                        <option value="">Select Product</option>'''
    
    for f in finished:
        content += '<option value="%d">%s</option>' % (f['id'], f['name'])
    
    content += '''
                    </select>
                </div>
                <div class="col-md-5">
                    <label class="form-label">BOM</label>
                    <select name="bom_id" class="form-select" required id="bomSelect">
                        <option value="">Select a product first</option>
                    </select>
                </div>
                <div class="col-md-2">
                    <label class="form-label">Quantity</label>
                    <input type="number" step="0.01" name="quantity" class="form-control" required>
                </div>
                <div class="col-12">
                    <label class="form-label">Notes (optional)</label>
                    <input type="text" name="notes" class="form-control">
                </div>
                <div class="col-12">
                    <button type="submit" class="btn btn-success">Record Production</button>
                </div>
            </form>
        </div>
    </div>
    
    <div class="card">
        <div class="card-header"><h5 class="mb-0">Production History</h5></div>
        <div class="card-body">'''
    
    if records:
        content += '<table class="table table-hover"><thead><tr><th>Date</th><th>Product</th><th>BOM</th><th>Qty</th><th>Notes</th></tr></thead><tbody>'
        for r in records:
            content += '<tr><td>%s</td><td>%s</td><td>%s</td><td>%g</td><td>%s</td></tr>' % (
                r['created_at'][:10], r['finished_name'], r['bom_name'], 
                r['quantity_produced'], r['notes'] or ''
            )
        content += '</tbody></table>'
    else:
        content += '<p class="text-muted">No production records yet.</p>'
    
    content += '''
        </div>
    </div>
    
    <script>
        function loadBoms(finishedGoodId) {
            const bomSelect = document.getElementById('bomSelect');
            bomSelect.innerHTML = '<option value="">Loading...</option>';
            
            fetch('/api/boms_for_product/' + finishedGoodId)
                .then(r => r.json())
                .then(boms => {
                    let html = '<option value="">Select BOM</option>';
                    boms.forEach(bom => {
                        html += '<option value="' + bom.id + '">' + bom.name + ' (v' + bom.version + ')</option>';
                    });
                    bomSelect.innerHTML = html;
                });
        }
    </script>'''
    
    return render_page(content, 'production')

@app.route('/api/boms_for_product/<int:product_id>')
def api_boms_for_product(product_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM boms WHERE finished_good_id = ? ORDER BY version DESC", (product_id,))
    boms = cursor.fetchall()
    conn.close()
    return jsonify([dict(b) for b in boms])

@app.route('/record_production', methods=['POST'])
def record_production():
    quantity = float(request.form['quantity'])
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Get BOM items and check if enough materials
    cursor.execute("SELECT * FROM bom_items WHERE bom_id = ?", (request.form['bom_id'],))
    bom_items = cursor.fetchall()
    
    # Calculate material usage
    insufficient = []
    for item in bom_items:
        if item['item_type'] == 'material' and item['raw_material_id']:
            required = item['quantity'] * quantity
            cursor.execute("SELECT quantity FROM raw_materials WHERE id = ?", (item['raw_material_id'],))
            current = cursor.fetchone()
            if current and current['quantity'] < required:
                cursor.execute("SELECT name FROM raw_materials WHERE id = ?", (item['raw_material_id'],))
                mat_name = cursor.fetchone()['name']
                insufficient.append((mat_name, current['quantity'], required))
    
    if insufficient:
        for name, current_qty, required_qty in insufficient:
            flash(f'Insufficient: {name} ({current_qty} < {required_qty})', 'error')
        conn.close()
        return redirect(url_for('production'))
    
    # Record production
    cursor.execute("INSERT INTO production_records (finished_good_id, bom_id, quantity_produced, notes) VALUES (?, ?, ?, ?)", (
        request.form['finished_good_id'],
        request.form['bom_id'],
        quantity,
        request.form.get('notes') or None
    ))
    
    # Increase finished goods quantity
    cursor.execute("UPDATE finished_goods SET quantity = quantity + ? WHERE id = ?", (quantity, request.form['finished_good_id']))
    
    # Deduct materials
    for item in bom_items:
        if item['item_type'] == 'material' and item['raw_material_id']:
            usage = item['quantity'] * quantity
            # Log the adjustment
            cursor.execute("SELECT quantity FROM raw_materials WHERE id = ?", (item['raw_material_id'],))
            old_qty = cursor.fetchone()['quantity']
            cursor.execute("INSERT INTO stock_adjustments (item_type, item_id, old_quantity, new_quantity, reason) VALUES (?, ?, ?, ?, ?)", (
                'material', item['raw_material_id'], old_qty, old_qty - usage, 'Production: %g units' % quantity
            ))
            cursor.execute("UPDATE raw_materials SET quantity = quantity - ? WHERE id = ?", (usage, item['raw_material_id']))
    
    conn.commit()
    conn.close()
    flash(f'Production recorded: %g units' % quantity, 'success')
    return redirect(url_for('production'))

@app.route('/stock_adjustments')
def stock_adj():
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT s.*, 
               CASE WHEN s.item_type = 'material' THEN m.name ELSE f.name END as item_name
        FROM stock_adjustments s
        LEFT JOIN raw_materials m ON (s.item_type = 'material' AND s.item_id = m.id)
        LEFT JOIN finished_goods f ON (s.item_type = 'finished' AND s.item_id = f.id)
        ORDER BY s.created_at DESC
    """)
    adjustments = cursor.fetchall()
    
    conn.close()
    
    content = '''
    <h2 class="mb-4">Stock Adjustments</h2>
    
    <div class="card">
        <div class="card-header"><h5 class="mb-0">Adjustment History</h5></div>
        <div class="card-body">'''
    
    if adjustments:
        content += '<table class="table table-hover"><thead><tr><th>Date</th><th>Type</th><th>Item</th><th>From</th><th>To</th><th>Reason</th></tr></thead><tbody>'
        for adj in adjustments:
            badge = '<span class="badge bg-info">Material</span>' if adj['item_type'] == 'material' else '<span class="badge bg-success">Finished Goods</span>'
            content += '<tr><td>%s</td><td>%s</td><td>%s</td><td>%g</td><td>%g</td><td>%s</td></tr>' % (
                adj['created_at'][:10], badge, adj['item_name'],
                adj['old_quantity'], adj['new_quantity'], adj['reason'] or ''
            )
        content += '</tbody></table>'
    else:
        content += '<p class="text-muted">No adjustments recorded.</p>'
    
    content += '        </div>\n    </div>'
    
    return render_page(content, 'adjustments')

@app.route('/export')
def export():
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) as count FROM raw_materials")
    materials_count = cursor.fetchone()['count']
    
    cursor.execute("SELECT COUNT(*) as count FROM finished_goods")
    finished_count = cursor.fetchone()['count']
    
    cursor.execute("SELECT COUNT(*) as count FROM boms")
    boms_count = cursor.fetchone()['count']
    
    cursor.execute("SELECT COUNT(*) as count FROM production_records")
    production_count = cursor.fetchone()['count']
    
    conn.close()
    
    content = '''
    <h2 class="mb-4">Export Data</h2>
    
    <div class="row mb-4">
        <div class="col-md-3"><div class="stat-card"><h3>%d</h3><p>Raw Materials</p></div></div>
        <div class="col-md-3"><div class="stat-card" style="background:linear-gradient(135deg,#9b59b6,#8e44ad);"><h3>%d</h3><p>Finished Goods</p></div></div>
        <div class="col-md-3"><div class="stat-card" style="background:linear-gradient(135deg,#e74c3c,#c0392b);"><h3>%d</h3><p>BOMs</p></div></div>
        <div class="col-md-3"><div class="stat-card" style="background:linear-gradient(135deg,#f39c12,#d35400);"><h3>%d</h3><p>Productions</p></div></div>
    </div>
    
    <div class="card">
        <div class="card-header"><h5 class="mb-0">Download CSV Exports</h5></div>
        <div class="card-body">
            <div class="row">
                <div class="col-md-3 mb-3">
                    <a href="/export/raw_materials" class="btn btn-outline-primary d-block">
                        <i class="fas fa-download me-2"></i>Export Raw Materials
                    </a>
                </div>
                <div class="col-md-3 mb-3">
                    <a href="/export/finished_goods" class="btn btn-outline-success d-block">
                        <i class="fas fa-download me-2"></i>Export Finished Goods
                    </a>
                </div>
                <div class="col-md-3 mb-3">
                    <a href="/export/boms" class="btn btn-outline-warning d-block">
                        <i class="fas fa-download me-2"></i>Export BOMs
                    </a>
                </div>
                <div class="col-md-3 mb-3">
                    <a href="/export/production" class="btn btn-outline-info d-block">
                        <i class="fas fa-download me-2"></i>Export Production
                    </a>
                </div>
            </div>
        </div>
    </div>''' % (materials_count, finished_count, boms_count, production_count)
    
    return render_page(content, 'export')

@app.route('/export/raw_materials')
def export_raw_materials():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT rm.*, g.name as group_name FROM raw_materials rm LEFT JOIN product_groups g ON rm.group_id = g.id ORDER BY g.name, rm.name")
    rows = cursor.fetchall()
    conn.close()
    
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', 'Name', 'Unit', 'Quantity', 'Cost/Unit', 'Value', 'Group'])
    for row in rows:
        writer.writerow([row['id'], row['name'], row['unit'], row['quantity'], 
                         row['cost_per_unit'], row['quantity'] * row['cost_per_unit'], row['group_name']])
    
    response = Response(output.getvalue(), mimetype='text/csv')
    response.headers["Content-Disposition"] = "attachment; filename=raw_materials.csv"
    return response

@app.route('/export/finished_goods')
def export_finished_goods():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT fg.*, g.name as group_name FROM finished_goods fg LEFT JOIN product_groups g ON fg.group_id = g.id ORDER BY g.name, fg.name")
    rows = cursor.fetchall()
    conn.close()
    
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', 'Name', 'SKU', 'Unit', 'Quantity', 'Group'])
    for row in rows:
        writer.writerow([row['id'], row['name'], row['sku'], row['unit'], row['quantity'], row['group_name']])
    
    response = Response(output.getvalue(), mimetype='text/csv')
    response.headers["Content-Disposition"] = "attachment; filename=finished_goods.csv"
    return response

@app.route('/export/boms')
def export_boms():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT b.name as bom_name, f.name as product, bi.item_type, 
               bi.name as item_name, m.name as material_name, bi.quantity, bi.cost_per_unit
        FROM boms b
        JOIN finished_goods f ON b.finished_good_id = f.id
        JOIN bom_items bi ON b.id = bi.bom_id
        LEFT JOIN raw_materials m ON bi.raw_material_id = m.id
        ORDER BY b.name, bi.item_type, bi.name
    """)
    rows = cursor.fetchall()
    conn.close()
    
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['BOM Name', 'Product', 'Item Type', 'Item Name', 'Quantity', 'Cost/Unit'])
    for row in rows:
        item_name = row['item_name'] or row['material_name'] or 'Unknown'
        writer.writerow([row['bom_name'], row['product'], row['item_type'], item_name, row['quantity'], row['cost_per_unit']])
    
    response = Response(output.getvalue(), mimetype='text/csv')
    response.headers["Content-Disposition"] = "attachment; filename=boms.csv"
    return response

@app.route('/export/production')
def export_production():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT p.created_at, f.name as product, b.name as bom, p.quantity_produced, p.notes
        FROM production_records p
        JOIN finished_goods f ON p.finished_good_id = f.id
        JOIN boms b ON p.bom_id = b.id
        ORDER BY p.created_at DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['Date', 'Product', 'BOM', 'Quantity Produced', 'Notes'])
    for row in rows:
        writer.writerow([row['created_at'][:10], row['product'], row['bom'], row['quantity_produced'], row['notes'] or ''])
    
    response = Response(output.getvalue(), mimetype='text/csv')
    response.headers["Content-Disposition"] = "attachment; filename=production.csv"
    return response

@app.route('/about')
def about():
    content = '''
    <h2 class="mb-4">About Micro Inventory Tracker</h2>
    <div class="card">
        <div class="card-body">
            <h5 class="card-title">Micro Inventory Tracker v1.0</h5>
            <p class="card-text">A simple, lightweight inventory management system designed for small producers who need to track raw materials and production without the complexity and cost of enterprise ERP systems.</p>
            
            <h6 class="mt-4">Features:</h6>
            <ul>
                <li>Raw materials tracking with quantities and costs</li>
                <li>Finished goods inventory management</li>
                <li>BOM (Bill of Materials) creation with materials and labor</li>
                <li>Production recording with automatic stock adjustments</li>
                <li>Stock adjustment history</li>
                <li>CSV export for all data</li>
                <li>Product grouping (Yule Folk, Candles, Decorations, etc.)</li>
            </ul>
            
            <h6 class="mt-4">Usage:</h6>
            <p>1. Create product groups (e.g., "Candles", "Yule Folk")</p>
            <p>2. Add raw materials with quantities and costs</p>
            <p>3. Add finished goods/SKUs</p>
            <p>4. Create BOMs with raw material requirements and labor costs</p>
            <p>5. Record production runs - the system will automatically deduct raw materials</p>
            <p>6. Export data anytime via CSV</p>
            
            <h6 class="mt-4">Technical Details:</h6>
            <p>Built with Flask and SQLite. No external dependencies except Bootstrap CSS.</p>
            <p>Runs locally on your computer - no internet connection required after setup.</p>
        </div>
    </div>'''
    return render_page(content, 'about')

@app.errorhandler(404)
def not_found(e):
    return '<h2>404 - Page Not Found</h2>', 404

if __name__ == '__main__':
    print("Starting Micro Inventory Tracker...")
    print("Access the app at: http://localhost:8000")
    print("Press Ctrl+C to stop the server")
    app.run(host='0.0.0.0', port=8000, debug=False)