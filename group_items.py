import sqlite3
import re
import uuid

DB_PATH = 'inventory.db'

def get_connection():
    return sqlite3.connect(DB_PATH)

def normalize_name(name):
    """
    Removes variant keywords to find the 'Base Name'.
    Ex: '1 Rose Dozen Red Deluxe' -> '1 Rose Dozen Red'
    """
    # Case insensitive replace
    pattern = re.compile(r'\s+(Standard|Deluxe|Premium)$', re.IGNORECASE)
    base_name = pattern.sub('', name)
    return base_name.strip()

def fix_groups():
    conn = get_connection()
    cursor = conn.cursor()
    
    # 1. Fetch all active products
    cursor.execute("SELECT product_id, display_name, variant_group_id FROM products WHERE active = 1")
    products = cursor.fetchall()
    
    print(f"🧐 Analyzing {len(products)} products for grouping...")
    
    # 2. Group by Base Name
    groups = {}
    for p_id, name, current_gid in products:
        base = normalize_name(name)
        if base not in groups:
            groups[base] = []
        groups[base].append({'id': p_id, 'name': name, 'gid': current_gid})
    
    updates = 0
    linked_count = 0
    
    # 3. Assign Shared IDs
    for base_name, items in groups.items():
        # If there are multiple items (e.g. Std, Dlx) sharing a base name
        if len(items) > 1:
            # Pick a consistent Group ID (use the first one found, or generate new if all null)
            shared_gid = items[0]['gid']
            if not shared_gid:
                shared_gid = str(uuid.uuid4())
            
            print(f"🔗 Linking Group: '{base_name}' ({len(items)} variants)")
            
            for item in items:
                # Update everyone in this group to use the shared_gid
                if item['gid'] != shared_gid:
                    cursor.execute("UPDATE products SET variant_group_id = ? WHERE product_id = ?", (shared_gid, item['id']))
                    updates += 1
            linked_count += 1
            
    conn.commit()
    conn.close()
    
    print(f"\n✅ Finished! Linked {linked_count} product families.")
    print(f"📝 Total Database Updates: {updates}")

if __name__ == "__main__":
    fix_groups()