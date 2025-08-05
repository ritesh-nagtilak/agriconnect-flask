import os
from dotenv import load_dotenv
load_dotenv()

from flask import Flask, render_template, request, redirect, session, flash
from flask_mysqldb import MySQL
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from config import Config

app = Flask(__name__)
app.config.from_object(Config)
app.config['UPLOAD_FOLDER'] = 'static/uploads'

mysql = MySQL(app)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/about')
def about():
    return render_template('about.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        whatsapp = request.form['whatsapp']
        password = request.form['password']
        role = request.form['role']

        hashed_password = generate_password_hash(password)

        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM users WHERE email = %s", (email,))
        existing_user = cur.fetchone()
        if existing_user:
            flash("Email already registered!", "danger")
            return render_template('register.html')

        cur.execute("""
            INSERT INTO users (username, email, password, whatsapp, role)
            VALUES (%s, %s, %s, %s, %s)
        """, (username, email, hashed_password, whatsapp, role))
        mysql.connection.commit()
        flash("Registration successful! Please login.", "success")
        return redirect('/login')

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password_input = request.form['password']
        
        cur = mysql.connection.cursor()
        cur.execute("SELECT id, username, email, password, role FROM users WHERE email = %s", (email,))
        user = cur.fetchone()
        cur.close()
        
        if user and check_password_hash(user[3], password_input):
            session['user_id'] = user[0]
            session['username'] = user[1]
            session['role'] = user[4]

            if user[4] == 'admin':
                return redirect('/dashboard/admin')
            elif user[4] == 'farmer':
                return redirect('/dashboard/farmer')
            else:
                return redirect('/dashboard/customer')
        else:
            flash('Invalid email or password.', 'danger')

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect('/login')

@app.route('/dashboard/farmer')
def farmer_dashboard():
    if session.get('role') != 'farmer': return redirect('/login')
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM products WHERE farmer_id = %s", (session['user_id'],))
    products = cur.fetchall()
    cur.close()
    return render_template('dashboard_farmer.html', products=products)

@app.route('/add-product', methods=['GET', 'POST'])
def add_product():
    if session.get('role') != 'farmer': return redirect('/login')
    if request.method == 'POST':
        name = request.form['name']
        category = request.form['category']
        price = request.form['price']
        stock = request.form['stock']
        location = request.form['location']
        description = request.form['description']
        image = request.files['image']
        if image and allowed_file(image.filename):
            filename = secure_filename(image.filename)
            image.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            cur = mysql.connection.cursor()
            cur.execute("""
                INSERT INTO products (farmer_id, name, category, price, stock, location, description, image)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (session['user_id'], name, category, price, stock, location, description, filename))
            mysql.connection.commit()
            cur.close()
            flash('Product added!', 'success')
            return redirect('/dashboard/farmer')
        else:
            flash('Invalid image format!', 'danger')
    return render_template('add_product.html')

@app.route('/edit-product/<int:id>', methods=['GET', 'POST'])
def edit_product(id):
    if session.get('role') != 'farmer':
        return redirect('/login')

    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM products WHERE id = %s AND farmer_id = %s", (id, session['user_id']))
    product = cur.fetchone()

    if not product:
        flash("Product not found or unauthorized", "danger")
        return redirect('/dashboard/farmer')

    if request.method == 'POST':
        name = request.form['name']
        category = request.form['category']
        price = request.form['price']
        stock = request.form['stock']
        location = request.form['location']
        description = request.form['description']

        image_file = request.files.get('image')
        if image_file and image_file.filename != '':
            filename = secure_filename(image_file.filename)
            image_path = os.path.join('static/uploads', filename)
            image_file.save(image_path)

            cur.execute("""
                UPDATE products SET name=%s, category=%s, price=%s, stock=%s, location=%s,    description=%s, image=%s
                WHERE id=%s AND farmer_id=%s
            """, (name, category, price, stock, location, description, filename, id, session['user_id']))
        else:
            cur.execute("""
                UPDATE products SET name=%s, category=%s, price=%s, stock=%s, location=%s, description=%s
                WHERE id=%s AND farmer_id=%s
            """, (name, category, price, stock, location, description, id, session['user_id']))

        mysql.connection.commit()
        flash('✅ Product updated successfully!', 'success')
        return redirect('/dashboard/farmer')

    return render_template('edit_product.html', product=product)


@app.route('/delete-product/<int:id>')
def delete_product(id):
    if session.get('role') != 'farmer':
        return redirect('/login')

    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM products WHERE id = %s AND farmer_id = %s", (id, session['user_id']))
    mysql.connection.commit()
    cur.close()

    flash('Product deleted permanently!', 'info')
    return redirect('/dashboard/farmer')


@app.route('/dashboard/customer')
def customer_dashboard():
    if session.get('role') != 'customer': return redirect('/login')
    q = request.args.get('q', '')
    category = request.args.get('category', '')
    location = request.args.get('location')
    cur = mysql.connection.cursor()
    query = "SELECT * FROM products WHERE 1"
    values = []
    if q:
        query += " AND (name LIKE %s OR category LIKE %s)"
        values += [f"%{q}%", f"%{q}%"]
    if category:
        query += " AND category = %s"
        values.append(category)
    if location:
        query += " AND location = %s"
        values.append(location)
    cur.execute(query, tuple(values))
    products = cur.fetchall()
    cur.close()
    return render_template('dashboard_customer.html', products=products)

@app.route('/add-to-cart/<int:product_id>', methods=['POST'])
def add_to_cart(product_id):
    if session.get('role') != 'customer':
        return redirect('/login')

    quantity = int(request.form.get('quantity', 1))
    cart = session.get('cart', [])
    for item in cart:
        if item['product_id'] == product_id:
            item['quantity'] += quantity
            break
    else:
        cart.append({'product_id': product_id, 'quantity': quantity})

    session['cart'] = cart
    session.modified = True
    flash('Added to cart!', 'success')
    return redirect('/dashboard/customer')


@app.route('/remove-from-cart/<int:product_id>')
def remove_from_cart(product_id):
    if session.get('role') != 'customer': return redirect('/login')

    cart = session.get('cart', [])
    cart = [item for item in cart if item['product_id'] != product_id]
    session['cart'] = cart
    session.modified = True
    flash('Item removed from cart.', 'info')
    return redirect('/cart')


@app.route('/cart')
def cart():
    if session.get('role') != 'customer':
        return redirect('/login')

    cart_items = session.get('cart', [])
    detailed_cart = []
    grand_total = 0

    cur = mysql.connection.cursor()
    for item in cart_items:
        cur.execute("SELECT id, name, price, image FROM products WHERE id = %s", (item['product_id'],))
        product = cur.fetchone()
        if product:
            subtotal = product[2] * item['quantity']
            grand_total += subtotal
            detailed_cart.append({
                'id': product[0],
                'name': product[1],
                'price': product[2],
                'image': product[3],
                'quantity': item['quantity'],
                'subtotal': subtotal
            })

    cur.close()
    return render_template('cart.html', cart=detailed_cart, grand_total=grand_total)


@app.route('/checkout', methods=['GET', 'POST'])
def checkout():
    if session.get('role') != 'customer':
        return redirect('/login')

    cart = session.get('cart', [])
    if not cart:
        flash('Your cart is empty.', 'warning')
        return redirect('/cart')

    if request.method == 'POST':
        address = request.form.get('address')
        note = request.form.get('note', '')
        customer_id = session['user_id']

        try:
            cur = mysql.connection.cursor()

            for item in cart:
                product_id = item['product_id']
                quantity = item['quantity']

                cur.execute("SELECT farmer_id, price, stock FROM products WHERE id = %s", (product_id,))
                result = cur.fetchone()
                if not result:
                    continue
                farmer_id, price, stock = result

                if stock < quantity:
                    flash(f'❌ Not enough stock for product ID {product_id}', 'danger')
                    continue

                total_price = price * quantity

                cur.execute("""
                    INSERT INTO orders (customer_id, farmer_id, product_id, quantity, total_price, address, note)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (customer_id, farmer_id, product_id, quantity, total_price, address, note))

                cur.execute("""
                    UPDATE products SET stock = stock - %s
                    WHERE id = %s
                """, (quantity, product_id))

            mysql.connection.commit()
            session['cart'] = []
            flash('✅ Order placed successfully! The respected farmer will contact you.', 'success')

        except Exception as e:
            mysql.connection.rollback()
            flash(f'❌ Order failed: {str(e)}', 'danger')

        finally:
            cur.close()

        return redirect('/orders')

    return render_template('checkout.html', cart_items=cart)


@app.route('/place-order')
def place_order():
    if session.get('role') != 'customer':
        return redirect('/login')
    
    cart = session.get('cart', [])
    cur = mysql.connection.cursor()
    
    for item in cart:
        cur.execute("SELECT farmer_id FROM products WHERE id = %s", (item['product_id'],))
        farmer = cur.fetchone()
        if not farmer:
            continue

        farmer_id = farmer[0]
        cur.execute("""
            INSERT INTO orders (customer_id, product_id, quantity, farmer_id)
            VALUES (%s, %s, %s, %s)
        """, (session['user_id'], item['product_id'], item['quantity'], farmer_id))

        cur.execute("""
            UPDATE products SET stock = stock - %s 
            WHERE id = %s AND stock >= %s
        """, (item['quantity'], item['product_id'], item['quantity']))

    mysql.connection.commit()
    cur.close()
    session['cart'] = []
    flash('Order placed successfully!', 'success')
    return redirect('/orders')

@app.route('/orders')
def orders():
    if session.get('role') != 'customer': return redirect('/login')

    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT o.quantity, o.order_date,
               p.name, p.price, o.status
        FROM orders o
        JOIN products p ON o.product_id = p.id
        WHERE o.customer_id = %s
        ORDER BY o.order_date DESC
    """, (session['user_id'],))
    raw_orders = cur.fetchall()
    cur.close()

    orders = []
    for row in raw_orders:
        order = {
            'quantity': row[0],
            'order_date': row[1],
            'product': {
                'name': row[2],
                'price': row[3]
            },
            'status': row[4]
        }
        orders.append(order)
    return render_template('orders.html', orders=orders)

@app.route('/farmer-orders')
def farmer_orders():
    if session.get('role') != 'farmer':
        return redirect('/login')

    farmer_id = session['user_id']
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT 
            o.id, u.username, u.email, p.name, o.quantity, 
            o.order_date, u.whatsapp, o.status
        FROM orders o
        JOIN users u ON o.customer_id = u.id
        JOIN products p ON o.product_id = p.id
        WHERE o.farmer_id = %s
        ORDER BY o.order_date DESC
    """, (farmer_id,))
    orders = cur.fetchall()
    cur.close()
    return render_template('farmer_orders.html', orders=orders)

@app.route('/order/deliver/<int:order_id>', methods=['POST'])
def mark_order_delivered(order_id):
    if session.get('role') != 'farmer':
        return redirect('/login')
    cur = mysql.connection.cursor()
    cur.execute("UPDATE orders SET status = 'delivered' WHERE id = %s", (order_id,))
    mysql.connection.commit()
    cur.close()
    flash('Order marked as delivered.', 'success')
    return redirect('/farmer-orders')

@app.route('/dashboard/admin')
def admin_dashboard():
    if session.get('role') != 'admin': return redirect('/login')
    cur = mysql.connection.cursor()
    cur.execute("SELECT id, username, email, whatsapp, role FROM users WHERE role != 'admin'")
    users = cur.fetchall()
    cur.execute("SELECT p.id, p.name, p.category, p.price, u.username FROM products p JOIN users u ON p.farmer_id = u.id")
    products = cur.fetchall()
    cur.execute("""
        SELECT o.id, p.name, u.username, o.quantity, o.order_date, o.status
        FROM orders o
        JOIN products p ON o.product_id = p.id
        JOIN users u ON o.customer_id = u.id
        ORDER BY o.order_date DESC
    """)
    orders = cur.fetchall()
    cur.close()
    return render_template("dashboard_admin.html", users=users, products=products, orders=orders)

@app.route('/delete-user/<int:id>')
def delete_user(id):
    if session.get('role') != 'admin':
        return redirect('/login')

    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM users WHERE id = %s AND role != 'admin'", (id,))
    mysql.connection.commit()

    session['message'] = ("info", "✅ User deleted successfully.")
    cur.close()
    return redirect('/dashboard/admin')

@app.route('/delete-product-admin/<int:id>')
def delete_product_admin(id):
    if session.get('role') != 'admin':
        return redirect('/login')

    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM products WHERE id = %s", (id,))
    mysql.connection.commit()

    flash("✅ Product deleted successfully.", "info")
    cur.close()
    return redirect('/dashboard/admin')



if __name__ == '__main__':
    app.run(debug=True)